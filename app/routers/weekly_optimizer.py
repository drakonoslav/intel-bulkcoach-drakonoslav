import logging
import math
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import (
    Exercise, Muscle, ActivationMatrixV2, BottleneckMatrixV4,
    StabilizationMatrixV5, CompositeMuscleIndex, Preset, ExerciseTag,
)
from app.equipment_filter import build_equipment_eligible, filter_candidates_by_equipment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

VALID_SLOTS = {"hinge", "squat", "push", "pull", "carry", "oly"}


def _normalize_vec(values):
    mn = min(values)
    mx = max(values)
    rng = mx - mn
    if rng == 0:
        return [0.0] * len(values)
    return [(v - mn) / rng for v in values]


def _cosine_sim(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _build_muscle_importance(preset_name: str, db: Session, muscle_ids: list):
    preset_row = db.query(Preset).filter(Preset.name == preset_name).first()
    if not preset_row:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset_name}")
    w = preset_row.weights
    wE = w.get("Exposure", 0)
    wH = w.get("Hierarchy", 0)
    wB = w.get("Bottleneck", 0)
    wS = w.get("Stability", 0)
    wP = w.get("Phase", 0)

    rows = db.query(CompositeMuscleIndex).all()
    mid_to_payload = {r.muscle_id: r.payload for r in rows}

    raw_exp = [mid_to_payload.get(mid, {}).get("V1_TotalExposure", 0) for mid in muscle_ids]
    raw_hier = [mid_to_payload.get(mid, {}).get("V2_RoleWeightedExposure", 0) for mid in muscle_ids]
    raw_bot = [mid_to_payload.get(mid, {}).get("Total_Bottleneck_Pressure", 0) for mid in muscle_ids]
    raw_stab = [mid_to_payload.get(mid, {}).get("Stabilization_Burden_Total", 0) for mid in muscle_ids]
    raw_phase = [mid_to_payload.get(mid, {}).get("V3_PeakPhaseShare", 0) for mid in muscle_ids]

    n_exp = _normalize_vec(raw_exp)
    n_hier = _normalize_vec(raw_hier)
    n_bot = _normalize_vec(raw_bot)
    n_stab = _normalize_vec(raw_stab)
    n_phase = _normalize_vec(raw_phase)

    scores = []
    for i in range(len(muscle_ids)):
        s = 100 * (
            n_exp[i] * wE +
            n_hier[i] * wH +
            n_bot[i] * wB +
            n_stab[i] * wS +
            n_phase[i] * wP
        )
        scores.append(s)

    total = sum(scores)
    if total == 0:
        return {mid: 1.0 / len(muscle_ids) for mid in muscle_ids}
    return {mid: scores[i] / total for i, mid in enumerate(muscle_ids)}


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


@router.get("/weekly-template", summary="Weekly template optimizer with slots, redundancy, and fatigue")
def weekly_template(
    preset: str = Query(..., description="Preset: hypertrophy, strength, or injury"),
    slots: Optional[str] = Query(None, description="Slot allocations e.g. hinge:2,squat:2,push:2,pull:2"),
    n: Optional[int] = Query(None, description="Total exercises (overrides sum of slots if provided)"),
    exclude: Optional[str] = Query(None, description="Comma-separated exercise names to exclude"),
    redundancyLambda: float = Query(0.35, description="Redundancy penalty coefficient"),
    bottleneckLambda: float = Query(0.25, description="Bottleneck penalty coefficient"),
    stabilityLambda: float = Query(0.20, description="Stability penalty coefficient"),
    bottleneckBudget: Optional[float] = Query(None, description="Hard cap on total bottleneck sum"),
    stabilityBudget: Optional[float] = Query(None, description="Hard cap on total stability sum"),
    available: Optional[str] = Query(None, description="Comma-separated equipment tags available", examples=["barbell,plates,dumbbell,bench,pullup_bar"]),
    db: Session = Depends(get_db),
):
    slot_counts = _parse_slots(slots)
    total_n = n if n is not None else sum(slot_counts.values())

    excluded_names = set()
    if exclude:
        excluded_names = {e.strip() for e in exclude.split(",") if e.strip()}

    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_ids = [m.id for m in all_muscles]
    muscle_name_map = {m.id: m.name for m in all_muscles}
    mid_index = {mid: i for i, mid in enumerate(muscle_ids)}
    n_muscles = len(muscle_ids)

    importance = _build_muscle_importance(preset, db, muscle_ids)

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

    stab_rows = (
        db.query(StabilizationMatrixV5)
        .filter(StabilizationMatrixV5.component == "stability")
        .all()
    )
    stab_vec = {}
    for r in stab_rows:
        if r.exercise_id not in stab_vec:
            stab_vec[r.exercise_id] = [0.0] * n_muscles
        stab_vec[r.exercise_id][mid_index[r.muscle_id]] = r.value

    available_tags = None
    equip_result = None
    equipment_active = False
    if available is not None:
        available_tags = set(t.strip() for t in available.split(",") if t.strip())
        if available_tags:
            equip_result = build_equipment_eligible(db, available_tags)
            equipment_active = True

    candidates_by_slot = {}
    candidate_counts_before = {}
    candidate_counts_after = {}
    for slot_name in slot_counts:
        eids = []
        for eid in slot_to_eids.get(slot_name, set()):
            ename = ex_name_map.get(eid, "")
            if ename not in excluded_names and eid in act_vec:
                eids.append(eid)
        candidate_counts_before[slot_name] = len(eids)
        if equip_result is not None:
            eligible_set, all_eids_with_reqs = equip_result
            eids = filter_candidates_by_equipment(eids, eligible_set, all_eids_with_reqs)
        candidate_counts_after[slot_name] = len(eids)
        candidates_by_slot[slot_name] = eids

    cand_summary = " ".join(f"{s}={len(candidates_by_slot.get(s, []))}" for s in sorted(slot_counts))
    print(f"Candidates: {cand_summary}")

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
                    gain += importance[muscle_ids[j]] * marginal

                red_penalty = 0.0
                if selected_vecs:
                    max_sim = max(_cosine_sim(avec, sv) for sv in selected_vecs)
                    red_penalty = redundancyLambda * max_sim

                bn_sum = sum(bn_vec.get(eid, [0.0] * n_muscles))
                stab_sum = sum(stab_vec.get(eid, [0.0] * n_muscles))

                bn_penalty = bottleneckLambda * bn_sum
                stab_penalty = stabilityLambda * stab_sum

                if bottleneckBudget is not None and total_bn_used + bn_sum > bottleneckBudget:
                    continue
                if stabilityBudget is not None and total_stab_used + stab_sum > stabilityBudget:
                    continue

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

    final_coverage = {
        muscle_name_map[muscle_ids[j]]: round(coverage[j], 6)
        for j in range(n_muscles)
    }
    final_coverage = dict(sorted(final_coverage.items(), key=lambda x: -x[1]))

    result = {
        "preset": preset,
        "slots_requested": slot_counts,
        "slots_filled": slot_filled,
        "total_selected": len(selected),
        "redundancyLambda": redundancyLambda,
        "bottleneckLambda": bottleneckLambda,
        "stabilityLambda": stabilityLambda,
        "selected": selected,
        "coverage": final_coverage,
        "total_bottleneck": round(total_bn_used, 6),
        "total_stability": round(total_stab_used, 6),
    }

    result["equipment_filter_applied"] = equipment_active
    if equipment_active:
        result["equipment_available"] = sorted(available_tags)
        result["candidates_by_slot"] = {
            slot: {"before": candidate_counts_before[slot], "after": candidate_counts_after[slot]}
            for slot in slot_counts
        }

    return result
