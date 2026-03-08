import re
from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.game_state import DATA_FLOOR_DATE, DATA_FLOOR_TS
from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
)
from app.hierarchy import build_derived_groups, apply_derived_rollup

router = APIRouter(prefix="/reports", tags=["reports"])

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def _iso_week_bounds(week_str: str):
    m = _WEEK_RE.match(week_str)
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid week format: '{week_str}'. Expected YYYY-WNN (e.g. 2026-W09).",
        )
    year = int(m.group(1))
    wk = int(m.group(2))
    if wk < 1 or wk > 53:
        raise HTTPException(status_code=400, detail=f"Week number must be 01-53, got {wk:02d}.")
    jan4 = date(year, 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = start_of_w1 + timedelta(weeks=wk - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _load_week_data(week: str, db: Session):
    monday, sunday = _iso_week_bounds(week)
    effective_monday = max(monday, DATA_FLOOR_DATE)
    sets = (
        db.query(LiftSet)
        .filter(LiftSet.performed_at >= effective_monday, LiftSet.performed_at <= sunday, LiftSet.created_at >= DATA_FLOOR_TS)
        .all()
    )

    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_map = {m.id: m.name for m in all_muscles}
    muscle_by_name = {m.name: m.id for m in all_muscles}

    exercise_ids = list({s.exercise_id for s in sets})
    ex_name_map = {}
    if exercise_ids:
        exs = db.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
        ex_name_map = {e.id: e.name for e in exs}

    act_lookup = {}
    role_lookup = {}
    if exercise_ids:
        act_rows = db.query(ActivationMatrixV2).filter(
            ActivationMatrixV2.exercise_id.in_(exercise_ids)
        ).all()
        for a in act_rows:
            act_lookup[(a.exercise_id, a.muscle_id)] = a.activation_value

        role_rows = db.query(RoleWeightedMatrixV2).filter(
            RoleWeightedMatrixV2.exercise_id.in_(exercise_ids)
        ).all()
        for r in role_rows:
            role_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight

    derived_groups = build_derived_groups(db)

    return sets, muscle_map, muscle_by_name, ex_name_map, act_lookup, role_lookup, derived_groups


def _compute_doses(sets, muscle_map, ex_name_map, act_lookup, role_lookup, topN, derived_groups=None):
    total_by_muscle = defaultdict(float)
    direct_by_muscle = defaultdict(float)
    total_by_muscle_ex = defaultdict(lambda: defaultdict(float))
    direct_by_muscle_ex = defaultdict(lambda: defaultdict(float))

    for s in sets:
        for mid in muscle_map:
            act = act_lookup.get((s.exercise_id, mid), 0)
            rw = role_lookup.get((s.exercise_id, mid), 0)
            t_dose = s.tonnage * (act / 5.0)
            d_dose = s.tonnage * rw
            if t_dose > 0:
                total_by_muscle[mid] += t_dose
                total_by_muscle_ex[mid][s.exercise_id] += t_dose
            if d_dose > 0:
                direct_by_muscle[mid] += d_dose
                direct_by_muscle_ex[mid][s.exercise_id] += d_dose

    if derived_groups:
        for group_id, child_ids in derived_groups.items():
            total_by_muscle[group_id] = sum(total_by_muscle.get(cid, 0) for cid in child_ids)
            direct_by_muscle[group_id] = sum(direct_by_muscle.get(cid, 0) for cid in child_ids)
            for cid in child_ids:
                for eid, dose in total_by_muscle_ex[cid].items():
                    total_by_muscle_ex[group_id][eid] += dose
                for eid, dose in direct_by_muscle_ex[cid].items():
                    direct_by_muscle_ex[group_id][eid] += dose

    results = []
    for mid in sorted(muscle_map.keys()):
        td = total_by_muscle.get(mid, 0)
        dd = direct_by_muscle.get(mid, 0)
        dr = dd / td if td > 0 else 0

        top_total = sorted(total_by_muscle_ex[mid].items(), key=lambda x: -x[1])[:topN]
        top_direct = sorted(direct_by_muscle_ex[mid].items(), key=lambda x: -x[1])[:topN]

        results.append({
            "muscle": muscle_map[mid],
            "total_dose": round(td, 4),
            "direct_dose": round(dd, 4),
            "directness_ratio": round(dr, 4),
            "top_exercises_total": [
                {"exercise": ex_name_map.get(eid, "?"), "dose": round(d, 4), "share": round(d / td, 4) if td > 0 else 0}
                for eid, d in top_total
            ],
            "top_exercises_direct": [
                {"exercise": ex_name_map.get(eid, "?"), "dose": round(d, 4), "share": round(d / dd, 4) if dd > 0 else 0}
                for eid, d in top_direct
            ],
        })

    results.sort(key=lambda x: -x["total_dose"])
    return results


@router.get("/weekly-muscle-dose", summary="Weekly muscle dose decomposition (total vs direct)")
def weekly_muscle_dose(
    week: str = Query(..., description="ISO week", examples=["2026-W09"]),
    topN: int = Query(5, ge=1, le=20, description="Top N contributing exercises per muscle"),
    db: Session = Depends(get_db),
):
    sets, muscle_map, _, ex_name_map, act_lookup, role_lookup, derived_groups = _load_week_data(week, db)
    total_tonnage = sum(s.tonnage for s in sets)

    if not sets:
        return {
            "week": week,
            "total_tonnage": 0,
            "muscles": [],
        }

    muscles = _compute_doses(sets, muscle_map, ex_name_map, act_lookup, role_lookup, topN, derived_groups)

    return {
        "week": week,
        "total_tonnage": round(total_tonnage, 2),
        "muscles": muscles,
    }


@router.get(
    "/weekly-muscle-dose/{muscle}",
    summary="Single muscle dose drilldown with optional set-level detail",
)
def weekly_muscle_dose_single(
    muscle: str,
    week: str = Query(..., description="ISO week", examples=["2026-W09"]),
    topN: int = Query(10, ge=1, le=50, description="Top N contributing exercises"),
    includeSets: bool = Query(False, description="Include top individual sets"),
    db: Session = Depends(get_db),
):
    sets, muscle_map, muscle_by_name, ex_name_map, act_lookup, role_lookup, derived_groups = _load_week_data(week, db)

    mid = muscle_by_name.get(muscle)
    if mid is None:
        valid = sorted(muscle_by_name.keys())
        raise HTTPException(status_code=404, detail=f"Unknown muscle: '{muscle}'. Valid muscles: {valid}")

    total_tonnage = sum(s.tonnage for s in sets)

    lookup_mids = [mid]
    if mid in derived_groups:
        lookup_mids = derived_groups[mid]

    total_dose = 0.0
    direct_dose = 0.0
    total_by_ex = defaultdict(float)
    direct_by_ex = defaultdict(float)
    set_doses_total = []
    set_doses_direct = []

    for s in sets:
        act = sum(act_lookup.get((s.exercise_id, lmid), 0) for lmid in lookup_mids)
        rw = sum(role_lookup.get((s.exercise_id, lmid), 0) for lmid in lookup_mids)
        t_dose = s.tonnage * (act / 5.0)
        d_dose = s.tonnage * rw

        if t_dose > 0:
            total_dose += t_dose
            total_by_ex[s.exercise_id] += t_dose
            set_doses_total.append({
                "performed_at": str(s.performed_at),
                "exercise": ex_name_map.get(s.exercise_id, "?"),
                "weight": s.weight,
                "reps": s.reps,
                "tonnage": s.tonnage,
                "dose": round(t_dose, 4),
            })
        if d_dose > 0:
            direct_dose += d_dose
            direct_by_ex[s.exercise_id] += d_dose
            set_doses_direct.append({
                "performed_at": str(s.performed_at),
                "exercise": ex_name_map.get(s.exercise_id, "?"),
                "weight": s.weight,
                "reps": s.reps,
                "tonnage": s.tonnage,
                "dose": round(d_dose, 4),
            })

    dr = direct_dose / total_dose if total_dose > 0 else 0

    top_total = sorted(total_by_ex.items(), key=lambda x: -x[1])[:topN]
    top_direct = sorted(direct_by_ex.items(), key=lambda x: -x[1])[:topN]

    result = {
        "week": week,
        "muscle": muscle,
        "total_tonnage": round(total_tonnage, 2),
        "total_dose": round(total_dose, 4),
        "direct_dose": round(direct_dose, 4),
        "directness_ratio": round(dr, 4),
        "top_exercises_total": [
            {"exercise": ex_name_map.get(eid, "?"), "dose": round(d, 4), "share": round(d / total_dose, 4) if total_dose > 0 else 0}
            for eid, d in top_total
        ],
        "top_exercises_direct": [
            {"exercise": ex_name_map.get(eid, "?"), "dose": round(d, 4), "share": round(d / direct_dose, 4) if direct_dose > 0 else 0}
            for eid, d in top_direct
        ],
    }

    if includeSets:
        set_doses_total.sort(key=lambda x: -x["dose"])
        set_doses_direct.sort(key=lambda x: -x["dose"])
        result["top_sets_total"] = set_doses_total[:topN]
        result["top_sets_direct"] = set_doses_direct[:topN]

    return result
