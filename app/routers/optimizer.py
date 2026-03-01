from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, List, Set
from app.database import get_db
from app.models import (
    Exercise, Muscle,
    ActivationMatrixV2, CompositeIndex,
    BottleneckMatrixV4, StabilizationMatrixV5,
)

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.get("", summary="Select exercises that maximise composite muscle coverage")
def optimize(
    goal: str = Query(
        "coverage",
        description=(
            "coverage = greedy set-cover maximising marginal muscle activation | "
            "bottleneck = prioritise exercises with most limiting muscles | "
            "stabilization = prioritise stabilization demand | "
            "composite = rank by composite index sum"
        ),
    ),
    n: int = Query(8, ge=1, le=30, description="Number of exercises to select"),
    constraints: Optional[str] = Query(
        None,
        description="Comma-separated constraints: exclude=exercise1;exercise2 | region=upper|lower|trunk | pattern=squat;hinge",
    ),
    target_muscles: Optional[str] = Query(
        None,
        description="Comma-separated muscle names to prioritise",
    ),
    db: Session = Depends(get_db),
):
    c = _parse_constraints(constraints)
    excluded = set(e.strip() for e in c.get("exclude", "").split(";") if e.strip())
    region = c.get("region", None)
    patterns = [p.strip() for p in c.get("pattern", "").split(";") if p.strip()]
    targets = set(m.strip().lower() for m in (target_muscles or "").split(",") if m.strip())

    ex_q = db.query(Exercise)
    if excluded:
        ex_q = ex_q.filter(~Exercise.name.in_(excluded))
    if region:
        muscle_ids_in_region = [
            m.id for m in db.query(Muscle).filter(Muscle.region == region).all()
        ]
        ex_ids_in_region = (
            db.query(ActivationMatrixV2.exercise_id)
            .filter(ActivationMatrixV2.muscle_id.in_(muscle_ids_in_region))
            .distinct()
            .all()
        )
        ex_q = ex_q.filter(Exercise.id.in_([eid[0] for eid in ex_ids_in_region]))
    if patterns:
        ex_q = ex_q.filter(Exercise.movement_pattern.in_(patterns))

    all_exercises = ex_q.all()
    if not all_exercises:
        raise HTTPException(status_code=404, detail="No exercises match the given constraints.")

    all_muscles = db.query(Muscle).all()
    muscle_name_map = {m.id: m.name for m in all_muscles}

    target_muscle_ids: Set[int] = set()
    if targets:
        for m in all_muscles:
            if m.name in targets:
                target_muscle_ids.add(m.id)

    ex_profiles = _build_profiles(db, all_exercises, goal, target_muscle_ids)

    if goal == "coverage":
        selected = _greedy_coverage(ex_profiles, n, target_muscle_ids)
    else:
        scored_list = sorted(ex_profiles.values(), key=lambda p: -p["score"])
        selected = scored_list[:n]

    covered: Dict[int, float] = {}
    for s in selected:
        for mid, act in s["_muscle_acts"].items():
            covered[mid] = max(covered.get(mid, 0.0), act)

    coverage = {
        muscle_name_map[mid]: round(val, 4)
        for mid, val in sorted(covered.items(), key=lambda x: -x[1])
    }

    notes = [
        f"Goal: {goal}",
        f"Candidates: {len(all_exercises)} exercises -> selected {len(selected)}",
        f"Muscles covered: {len(covered)}/{len(all_muscles)}",
    ]
    if targets:
        notes.append(f"Target muscles: {', '.join(targets)}")

    output = []
    for s in selected:
        entry = {k: v for k, v in s.items() if not k.startswith("_")}
        output.append(entry)

    return {
        "goal": goal,
        "n_slots": n,
        "selected": output,
        "coverage": coverage,
        "notes": notes,
    }


def _build_profiles(db: Session, exercises: list, goal: str, target_muscle_ids: Set[int]):
    profiles = {}
    for ex in exercises:
        acts = (
            db.query(ActivationMatrixV2)
            .filter(ActivationMatrixV2.exercise_id == ex.id)
            .all()
        )
        muscle_acts = {a.muscle_id: a.activation for a in acts}

        if goal == "coverage":
            score = 0.0
        elif goal == "bottleneck":
            bn_rows = (
                db.query(BottleneckMatrixV4)
                .filter(BottleneckMatrixV4.exercise_id == ex.id)
                .all()
            )
            n_limiting = sum(1 for r in bn_rows if r.is_limiting)
            score = float(n_limiting)
        elif goal == "stabilization":
            stab_rows = (
                db.query(StabilizationMatrixV5)
                .filter(StabilizationMatrixV5.exercise_id == ex.id)
                .all()
            )
            score = sum(r.stabilization_score for r in stab_rows)
        elif goal == "composite":
            comp_rows = (
                db.query(CompositeIndex)
                .filter(CompositeIndex.exercise_id == ex.id)
                .all()
            )
            score = sum(r.composite_score for r in comp_rows)
            if target_muscle_ids:
                for r in comp_rows:
                    if r.muscle_id in target_muscle_ids:
                        score += r.composite_score * 2.0
        else:
            raise HTTPException(status_code=400, detail=f"Unknown goal '{goal}'")

        profiles[ex.id] = {
            "exercise": ex.name,
            "category": ex.category,
            "movement_pattern": ex.movement_pattern,
            "score": round(score, 4),
            "muscles_activated": len(muscle_acts),
            "_muscle_acts": muscle_acts,
        }
    return profiles


def _greedy_coverage(profiles: dict, n: int, target_muscle_ids: Set[int]) -> list:
    selected = []
    covered: Dict[int, float] = {}
    remaining = set(profiles.keys())

    for _ in range(n):
        if not remaining:
            break
        best_id = None
        best_gain = -1.0
        for eid in remaining:
            p = profiles[eid]
            gain = 0.0
            for mid, act in p["_muscle_acts"].items():
                marginal = max(0.0, act - covered.get(mid, 0.0))
                if mid in target_muscle_ids:
                    marginal *= 3.0
                gain += marginal
            if gain > best_gain:
                best_gain = gain
                best_id = eid
        if best_id is None or best_gain <= 0:
            break
        selected_profile = profiles[best_id].copy()
        selected_profile["score"] = round(best_gain, 4)
        selected.append(selected_profile)
        for mid, act in profiles[best_id]["_muscle_acts"].items():
            covered[mid] = max(covered.get(mid, 0.0), act)
        remaining.discard(best_id)

    return selected


def _parse_constraints(raw: Optional[str]) -> dict:
    constraints = {}
    if not raw:
        return constraints
    for item in raw.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            constraints[k.strip()] = v.strip()
    return constraints
