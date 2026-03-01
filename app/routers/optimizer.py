from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, Set
from app.database import get_db
from app.models import Exercise, Muscle, ActivationMatrixV2

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.get("", summary="Greedy set-cover exercise selection using activation matrix")
def optimize(
    goal: str = Query(
        "coverage",
        description="coverage = maximise marginal muscle activation across selections",
    ),
    n: int = Query(8, ge=1, le=30, description="Number of exercises to select"),
    target_muscles: Optional[str] = Query(
        None, description="Comma-separated muscle names to prioritise",
    ),
    exclude: Optional[str] = Query(
        None, description="Comma-separated exercise names to exclude",
    ),
    db: Session = Depends(get_db),
):
    if goal != "coverage":
        raise HTTPException(status_code=400, detail="Only 'coverage' goal available for v2 matrix.")

    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_name_map = {m.id: m.name for m in all_muscles}

    targets: Set[int] = set()
    if target_muscles:
        for name in target_muscles.split(","):
            name = name.strip()
            mu = db.query(Muscle).filter(Muscle.name == name).first()
            if mu:
                targets.add(mu.id)

    ex_q = db.query(Exercise)
    if exclude:
        excluded = [e.strip() for e in exclude.split(",") if e.strip()]
        ex_q = ex_q.filter(~Exercise.name.in_(excluded))
    all_exercises = ex_q.all()

    profiles = {}
    for ex in all_exercises:
        acts = (
            db.query(ActivationMatrixV2)
            .filter(ActivationMatrixV2.exercise_id == ex.id)
            .filter(ActivationMatrixV2.activation_value > 0)
            .all()
        )
        profiles[ex.id] = {
            "name": ex.name,
            "acts": {a.muscle_id: a.activation_value for a in acts},
        }

    selected = []
    covered: Dict[int, int] = {}
    remaining = set(profiles.keys())

    for _ in range(n):
        if not remaining:
            break
        best_id = None
        best_gain = -1.0
        for eid in remaining:
            gain = 0.0
            for mid, val in profiles[eid]["acts"].items():
                marginal = max(0, val - covered.get(mid, 0))
                if mid in targets:
                    marginal *= 3.0
                gain += marginal
            if gain > best_gain:
                best_gain = gain
                best_id = eid
        if best_id is None or best_gain <= 0:
            break
        p = profiles[best_id]
        selected.append({
            "exercise": p["name"],
            "marginal_gain": round(best_gain, 2),
            "muscles_activated": len(p["acts"]),
        })
        for mid, val in p["acts"].items():
            covered[mid] = max(covered.get(mid, 0), val)
        remaining.discard(best_id)

    coverage = {
        muscle_name_map[mid]: val
        for mid, val in sorted(covered.items(), key=lambda x: -x[1])
    }

    notes = [
        f"Goal: {goal}",
        f"Candidates: {len(all_exercises)} -> selected {len(selected)}",
        f"Muscles covered: {len(covered)}/{len(all_muscles)}",
    ]
    if targets:
        target_names = [muscle_name_map[mid] for mid in targets]
        notes.append(f"Target muscles: {', '.join(target_names)}")

    return {
        "goal": goal,
        "n_slots": n,
        "selected": selected,
        "coverage": coverage,
        "notes": notes,
    }
