import math
import re
from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
    BottleneckMatrixV4, StabilizationMatrixV5,
    ExerciseTag,
)

router = APIRouter(prefix="/coach", tags=["coach"])

VALID_SLOTS = {"hinge", "squat", "push", "pull", "carry", "oly"}
_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def _iso_week_bounds(week_str: str):
    m = _WEEK_RE.match(week_str)
    if not m:
        raise HTTPException(status_code=400, detail=f"Invalid week format: '{week_str}'. Expected YYYY-WNN (e.g. 2026-W09).")
    year, wk = int(m.group(1)), int(m.group(2))
    if wk < 1 or wk > 53:
        raise HTTPException(status_code=400, detail=f"Week number must be 01-53, got {wk:02d}.")
    jan4 = date(year, 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = start_of_w1 + timedelta(weeks=wk - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _date_to_iso_week(d: date) -> str:
    cal = d.isocalendar()
    return f"{cal[0]}-W{cal[1]:02d}"


def _normalize_01(values):
    mn = min(values)
    mx = max(values)
    rng = mx - mn
    if rng == 0:
        return [0.0] * len(values)
    return [(v - mn) / rng for v in values]


def _percentile_ranks(values):
    n = len(values)
    if n == 0:
        return []
    sorted_vals = sorted(values)
    result = []
    for v in values:
        count_below = sum(1 for sv in sorted_vals if sv < v)
        count_equal = sum(1 for sv in sorted_vals if sv == v)
        pr = (count_below + 0.5 * count_equal) / n
        result.append(pr * 100)
    return result


def _cosine_sim(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _compute_weekly_balance(week: str, db: Session, lookback_weeks: int = 1):
    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_ids = [m.id for m in all_muscles]
    muscle_map = {m.id: m.name for m in all_muscles}
    n_muscles = len(muscle_ids)

    monday, sunday = _iso_week_bounds(week)
    if lookback_weeks > 1:
        monday = monday - timedelta(weeks=lookback_weeks - 1)

    sets = (
        db.query(LiftSet)
        .filter(LiftSet.performed_at >= monday, LiftSet.performed_at <= sunday)
        .all()
    )

    exercise_ids = list({s.exercise_id for s in sets})

    act_lookup = {}
    role_lookup = {}
    bn_lookup = {}
    stab_lookup = {}

    if exercise_ids:
        for a in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id.in_(exercise_ids)).all():
            act_lookup[(a.exercise_id, a.muscle_id)] = a.activation_value
        for r in db.query(RoleWeightedMatrixV2).filter(RoleWeightedMatrixV2.exercise_id.in_(exercise_ids)).all():
            role_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight
        for b in db.query(BottleneckMatrixV4).filter(BottleneckMatrixV4.exercise_id.in_(exercise_ids)).all():
            bn_lookup[(b.exercise_id, b.muscle_id)] = b.bottleneck_coeff
        for s in db.query(StabilizationMatrixV5).filter(
            StabilizationMatrixV5.exercise_id.in_(exercise_ids),
            StabilizationMatrixV5.component == "stability",
        ).all():
            stab_lookup[(s.exercise_id, s.muscle_id)] = s.value

    total_dose = {mid: 0.0 for mid in muscle_ids}
    direct_dose = {mid: 0.0 for mid in muscle_ids}
    bn_pressure = {mid: 0.0 for mid in muscle_ids}
    stab_load = {mid: 0.0 for mid in muscle_ids}

    for s in sets:
        for mid in muscle_ids:
            act = act_lookup.get((s.exercise_id, mid), 0)
            rw = role_lookup.get((s.exercise_id, mid), 0)
            bn = bn_lookup.get((s.exercise_id, mid), 0)
            st = stab_lookup.get((s.exercise_id, mid), 0)
            total_dose[mid] += s.tonnage * (act / 5.0)
            direct_dose[mid] += s.tonnage * rw
            bn_pressure[mid] += s.tonnage * bn
            stab_load[mid] += s.tonnage * st

    total_tonnage = sum(s.tonnage for s in sets)

    dd_values = [direct_dose[mid] for mid in muscle_ids]
    max_dd = max(dd_values) if dd_values else 0
    underfed_raw = [max(0, max_dd - dd) for dd in dd_values]
    underfed_scores = _percentile_ranks(underfed_raw)

    td_values = [total_dose[mid] for mid in muscle_ids]
    bn_values = [bn_pressure[mid] for mid in muscle_ids]
    stab_values = [stab_load[mid] for mid in muscle_ids]

    n_td = _normalize_01(td_values)
    n_bn = _normalize_01(bn_values)
    n_stab = _normalize_01(stab_values)

    overtaxed_scores = [
        100 * (0.45 * n_bn[i] + 0.35 * n_stab[i] + 0.20 * n_td[i])
        for i in range(n_muscles)
    ]

    results = []
    for i, mid in enumerate(muscle_ids):
        us = underfed_scores[i]
        os_ = overtaxed_scores[i]
        if us >= 70 and os_ < 70:
            status = "underfed"
        elif os_ >= 70:
            status = "overtaxed"
        else:
            status = "balanced"
        results.append({
            "muscle": muscle_map[mid],
            "muscle_id": mid,
            "total_dose": round(total_dose[mid], 4),
            "direct_dose": round(direct_dose[mid], 4),
            "underfed_score": round(us, 2),
            "overtaxed_score": round(os_, 2),
            "status": status,
        })

    return results, total_tonnage, len(sets), muscle_ids, muscle_map


def _parse_slots(slots_str: Optional[str]):
    if not slots_str:
        return {"hinge": 2, "squat": 2, "push": 2, "pull": 2}
    result = {}
    for part in slots_str.split(","):
        part = part.strip()
        if ":" not in part:
            raise HTTPException(status_code=400, detail=f"Invalid slot format: {part}. Use slot:count")
        name, count = part.split(":", 1)
        name = name.strip().lower()
        if name not in VALID_SLOTS:
            raise HTTPException(status_code=400, detail=f"Unknown slot: {name}. Valid: {sorted(VALID_SLOTS)}")
        result[name] = int(count)
    return result


@router.get("/weekly-balance", summary="Weekly muscle balance: underfed vs overtaxed")
def weekly_balance(
    week: str = Query(..., description="ISO week", examples=["2026-W09"]),
    preset: str = Query("hypertrophy", description="Preset name (for context)", examples=["hypertrophy"]),
    lookbackWeeks: int = Query(1, ge=1, le=8, description="Number of weeks to look back"),
    db: Session = Depends(get_db),
):
    results, total_tonnage, n_sets, _, _ = _compute_weekly_balance(week, db, lookbackWeeks)

    sorted_underfed = sorted(
        [r for r in results if r["status"] == "underfed"],
        key=lambda x: -x["underfed_score"],
    )[:5]
    sorted_overtaxed = sorted(
        [r for r in results if r["status"] == "overtaxed"],
        key=lambda x: -x["overtaxed_score"],
    )[:5]

    clean_results = []
    for r in results:
        cr = dict(r)
        del cr["muscle_id"]
        clean_results.append(cr)

    return {
        "week": week,
        "preset": preset,
        "lookback_weeks": lookbackWeeks,
        "total_tonnage": round(total_tonnage, 2),
        "sets_included": n_sets,
        "muscles": clean_results,
        "top_underfed": [{"muscle": r["muscle"], "underfed_score": r["underfed_score"]} for r in sorted_underfed],
        "top_overtaxed": [{"muscle": r["muscle"], "overtaxed_score": r["overtaxed_score"]} for r in sorted_overtaxed],
    }


@router.get("/recommend-session", summary="Recommend a training session based on weekly balance")
def recommend_session(
    date_param: date = Query(..., alias="date", description="Session date", examples=["2026-02-28"]),
    mode: str = Query("compound", description="compound or isolation", examples=["compound", "isolation"]),
    preset: str = Query("hypertrophy", description="Preset name", examples=["hypertrophy"]),
    time: int = Query(45, ge=15, le=120, description="Session duration in minutes"),
    slots: Optional[str] = Query(None, description="Slot allocations", examples=["hinge:2,squat:2,push:2,pull:2"]),
    exclude: Optional[str] = Query(None, description="Comma-separated exercises to exclude"),
    db: Session = Depends(get_db),
):
    if mode not in ("compound", "isolation"):
        raise HTTPException(status_code=400, detail="mode must be 'compound' or 'isolation'")

    week_str = _date_to_iso_week(date_param)
    balance_results, total_tonnage, n_sets, muscle_ids, muscle_map = _compute_weekly_balance(week_str, db)

    no_history = n_sets == 0

    underfed_map = {}
    for r in balance_results:
        underfed_map[r["muscle_id"]] = r["underfed_score"]

    top_n_underfed = 6
    sorted_by_underfed = sorted(muscle_ids, key=lambda mid: -underfed_map.get(mid, 0))
    top_underfed_ids = set(sorted_by_underfed[:top_n_underfed])

    u_values = []
    for mid in muscle_ids:
        if mid in top_underfed_ids:
            u_values.append(underfed_map.get(mid, 0))
        else:
            u_values.append(0.0)
    u_sum = sum(u_values)
    if u_sum > 0:
        u_weights = {mid: u_values[i] / u_sum for i, mid in enumerate(muscle_ids)}
    else:
        u_weights = {mid: 1.0 / len(muscle_ids) for mid in muscle_ids}

    slot_counts = _parse_slots(slots)
    total_n = sum(slot_counts.values())

    excluded_names = set()
    if exclude:
        excluded_names = {e.strip() for e in exclude.split(",") if e.strip()}

    mid_index = {mid: i for i, mid in enumerate(muscle_ids)}
    n_muscles = len(muscle_ids)

    all_exercises = db.query(Exercise).all()
    ex_name_map = {e.id: e.name for e in all_exercises}

    tag_rows = db.query(ExerciseTag).all()
    slot_to_eids = defaultdict(set)
    for t in tag_rows:
        slot_to_eids[t.slot].add(t.exercise_id)

    act_rows = db.query(ActivationMatrixV2).all()
    act_vec = {}
    for r in act_rows:
        if r.exercise_id not in act_vec:
            act_vec[r.exercise_id] = [0.0] * n_muscles
        act_vec[r.exercise_id][mid_index[r.muscle_id]] = r.activation_value / 5.0

    bn_rows = db.query(BottleneckMatrixV4).all()
    bn_vec = {}
    for r in bn_rows:
        if r.exercise_id not in bn_vec:
            bn_vec[r.exercise_id] = [0.0] * n_muscles
        bn_vec[r.exercise_id][mid_index[r.muscle_id]] = r.bottleneck_coeff

    stab_rows = db.query(StabilizationMatrixV5).filter(
        StabilizationMatrixV5.component == "stability"
    ).all()
    stab_vec = {}
    for r in stab_rows:
        if r.exercise_id not in stab_vec:
            stab_vec[r.exercise_id] = [0.0] * n_muscles
        stab_vec[r.exercise_id][mid_index[r.muscle_id]] = r.value

    if mode == "compound":
        lambda_red, lambda_bn, lambda_stab = 0.35, 0.25, 0.20
        excluded_slot_types = set()
    else:
        lambda_red, lambda_bn, lambda_stab = 0.35, 0.45, 0.45
        excluded_slot_types = {"oly", "carry"}

    candidates_by_slot = {}
    for slot_name in slot_counts:
        if slot_name in excluded_slot_types:
            candidates_by_slot[slot_name] = []
            continue
        eids = []
        for eid in slot_to_eids.get(slot_name, set()):
            ename = ex_name_map.get(eid, "")
            if ename not in excluded_names and eid in act_vec:
                eids.append(eid)
        candidates_by_slot[slot_name] = eids

    coverage = [0.0] * n_muscles
    selected = []
    selected_vecs = []
    total_bn_used = 0.0
    total_stab_used = 0.0
    slot_filled = {s: 0 for s in slot_counts}

    slot_order = []
    for slot_name, count in slot_counts.items():
        for _ in range(count):
            slot_order.append(slot_name)
    remaining_slots = list(slot_order)

    for _ in range(total_n):
        if not remaining_slots:
            break

        best_result = None
        best_score = -float("inf")
        best_slot_idx = -1

        for si, slot_name in enumerate(remaining_slots):
            for eid in candidates_by_slot.get(slot_name, []):
                if any(s["exercise_id"] == eid for s in selected):
                    continue

                avec = act_vec.get(eid, [0.0] * n_muscles)

                gain = 0.0
                for j in range(n_muscles):
                    marginal = max(0, avec[j] - coverage[j])
                    gain += u_weights[muscle_ids[j]] * marginal

                red_penalty = 0.0
                if selected_vecs:
                    max_sim = max(_cosine_sim(avec, sv) for sv in selected_vecs)
                    red_penalty = lambda_red * max_sim

                bn_sum = sum(bn_vec.get(eid, [0.0] * n_muscles))
                stab_sum = sum(stab_vec.get(eid, [0.0] * n_muscles))

                bn_penalty = lambda_bn * bn_sum
                stab_penalty = lambda_stab * stab_sum

                score = gain - red_penalty - bn_penalty - stab_penalty

                if score > best_score:
                    best_score = score
                    best_slot_idx = si
                    best_result = {
                        "exercise_id": eid,
                        "exercise": ex_name_map[eid],
                        "slot": slot_name,
                        "gain": round(gain, 6),
                        "redundancy_penalty": round(red_penalty, 6),
                        "bottleneck_penalty": round(bn_penalty, 6),
                        "stability_penalty": round(stab_penalty, 6),
                        "final_score": round(score, 6),
                        "_avec": avec,
                        "_bn_sum": bn_sum,
                        "_stab_sum": stab_sum,
                    }

        if best_result is None:
            break

        eid = best_result["exercise_id"]
        avec = best_result.pop("_avec")
        bn_sum = best_result.pop("_bn_sum")
        stab_sum = best_result.pop("_stab_sum")

        top_muscles_for_ex = []
        for j in range(n_muscles):
            if avec[j] > 0:
                top_muscles_for_ex.append((muscle_map[muscle_ids[j]], u_weights[muscle_ids[j]] * avec[j]))
        top_muscles_for_ex.sort(key=lambda x: -x[1])
        best_result["feeds_underfed"] = [
            {"muscle": name, "weighted_activation": round(wa, 6)}
            for name, wa in top_muscles_for_ex[:3]
        ]

        for j in range(n_muscles):
            coverage[j] = max(coverage[j], avec[j])

        selected.append(best_result)
        selected_vecs.append(avec)
        total_bn_used += bn_sum
        total_stab_used += stab_sum
        slot_filled[best_result["slot"]] += 1
        remaining_slots.pop(best_slot_idx)

    for s in selected:
        del s["exercise_id"]

    return {
        "date": str(date_param),
        "week": week_str,
        "mode": mode,
        "preset": preset,
        "no_history": no_history,
        "slots_requested": slot_counts,
        "slots_filled": slot_filled,
        "total_selected": len(selected),
        "lambda_red": lambda_red,
        "lambda_bn": lambda_bn,
        "lambda_stab": lambda_stab,
        "selected": selected,
        "total_bottleneck": round(total_bn_used, 6),
        "total_stability": round(total_stab_used, 6),
    }
