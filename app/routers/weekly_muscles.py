import re
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from collections import defaultdict

from app.database import get_db
from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2, PhaseMatrixV3,
    BottleneckMatrixV4, StabilizationMatrixV5,
)
from app.hierarchy import build_derived_groups, apply_derived_rollup

router = APIRouter(prefix="/reports", tags=["reports"])

VALID_LENSES = {"v2", "role", "v3", "v4", "v5"}

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
        raise HTTPException(
            status_code=400,
            detail=f"Week number must be 01-53, got {wk:02d}.",
        )
    jan4 = date(year, 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = start_of_w1 + timedelta(weeks=wk - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


@router.get("/weekly-muscles", summary="Weekly muscle stimulus report with configurable lens")
def weekly_muscles(
    week: str = Query(..., description="ISO week e.g. 2026-W09", examples=["2026-W09"]),
    lens: str = Query("v2", description="Matrix lens: v2, role, v3, v4, or v5", examples=["v2", "role", "v3", "v4", "v5"]),
    includeSets: bool = Query(False, description="Include individual sets in response"),
    db: Session = Depends(get_db),
):
    if lens not in VALID_LENSES:
        raise HTTPException(status_code=400, detail=f"Invalid lens: {lens}. Valid: {sorted(VALID_LENSES)}")

    monday, sunday = _iso_week_bounds(week)

    sets = (
        db.query(LiftSet)
        .filter(LiftSet.performed_at >= monday, LiftSet.performed_at <= sunday)
        .all()
    )

    if not sets:
        return {
            "week": week,
            "lens": lens,
            "total_tonnage": 0,
            "muscles": [],
            "extras": {},
            "sets_included": 0,
        }

    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_map = {m.id: m.name for m in all_muscles}
    derived_groups = build_derived_groups(db)

    total_tonnage = sum(s.tonnage for s in sets)

    if lens == "v2":
        stim = defaultdict(float)
        for s in sets:
            acts = db.query(ActivationMatrixV2).filter(
                ActivationMatrixV2.exercise_id == s.exercise_id
            ).all()
            for a in acts:
                stim[a.muscle_id] += s.tonnage * (a.activation_value / 5.0)
        apply_derived_rollup(stim, derived_groups)
        muscles = sorted(
            [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in stim.items()],
            key=lambda x: -x["value"],
        )
        result = {"week": week, "lens": lens, "total_tonnage": round(total_tonnage, 2),
                  "muscles": muscles, "extras": {}, "sets_included": len(sets)}

    elif lens == "role":
        stim = defaultdict(float)
        for s in sets:
            rows = db.query(RoleWeightedMatrixV2).filter(
                RoleWeightedMatrixV2.exercise_id == s.exercise_id
            ).all()
            for r in rows:
                stim[r.muscle_id] += s.tonnage * r.role_weight
        apply_derived_rollup(stim, derived_groups)
        muscles = sorted(
            [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in stim.items()],
            key=lambda x: -x["value"],
        )
        result = {"week": week, "lens": lens, "total_tonnage": round(total_tonnage, 2),
                  "muscles": muscles, "extras": {}, "sets_included": len(sets)}

    elif lens == "v3":
        phase_stim = {"initiation": defaultdict(float), "midrange": defaultdict(float), "lockout": defaultdict(float)}
        for s in sets:
            rows = db.query(PhaseMatrixV3).filter(
                PhaseMatrixV3.exercise_id == s.exercise_id
            ).all()
            for r in rows:
                phase_stim[r.phase][r.muscle_id] += s.tonnage * (r.phase_value / 5.0)
        for phase_dict in phase_stim.values():
            apply_derived_rollup(phase_dict, derived_groups)
        extras = {}
        for phase in ["initiation", "midrange", "lockout"]:
            extras[phase] = sorted(
                [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in phase_stim[phase].items()],
                key=lambda x: -x["value"],
            )
        all_stim = defaultdict(float)
        for phase_dict in phase_stim.values():
            for mid, v in phase_dict.items():
                all_stim[mid] += v
        muscles = sorted(
            [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in all_stim.items()],
            key=lambda x: -x["value"],
        )
        result = {"week": week, "lens": lens, "total_tonnage": round(total_tonnage, 2),
                  "muscles": muscles, "extras": extras, "sets_included": len(sets)}

    elif lens == "v4":
        pressure = defaultdict(float)
        for s in sets:
            rows = db.query(BottleneckMatrixV4).filter(
                BottleneckMatrixV4.exercise_id == s.exercise_id
            ).all()
            for r in rows:
                pressure[r.muscle_id] += s.tonnage * r.bottleneck_coeff
        apply_derived_rollup(pressure, derived_groups)
        muscles = sorted(
            [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in pressure.items()],
            key=lambda x: -x["value"],
        )
        result = {"week": week, "lens": lens, "total_tonnage": round(total_tonnage, 2),
                  "muscles": muscles, "extras": {}, "sets_included": len(sets)}

    elif lens == "v5":
        dyn = defaultdict(float)
        stab = defaultdict(float)
        for s in sets:
            rows = db.query(StabilizationMatrixV5).filter(
                StabilizationMatrixV5.exercise_id == s.exercise_id
            ).all()
            for r in rows:
                if r.component == "dynamic":
                    dyn[r.muscle_id] += s.tonnage * r.value
                else:
                    stab[r.muscle_id] += s.tonnage * r.value
        apply_derived_rollup(dyn, derived_groups)
        apply_derived_rollup(stab, derived_groups)
        all_stim = defaultdict(float)
        for mid in set(list(dyn.keys()) + list(stab.keys())):
            all_stim[mid] = dyn.get(mid, 0) + stab.get(mid, 0)
        muscles = sorted(
            [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in all_stim.items()],
            key=lambda x: -x["value"],
        )
        extras = {
            "dynamic": sorted(
                [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in dyn.items()],
                key=lambda x: -x["value"],
            ),
            "stability": sorted(
                [{"muscle": muscle_map[mid], "value": round(v, 4)} for mid, v in stab.items()],
                key=lambda x: -x["value"],
            ),
        }
        result = {"week": week, "lens": lens, "total_tonnage": round(total_tonnage, 2),
                  "muscles": muscles, "extras": extras, "sets_included": len(sets)}

    if includeSets:
        result["sets"] = [
            {
                "id": s.id,
                "performed_at": str(s.performed_at),
                "exercise": db.query(Exercise).get(s.exercise_id).name,
                "weight": s.weight,
                "reps": s.reps,
                "tonnage": s.tonnage,
            }
            for s in sets
        ]

    return result
