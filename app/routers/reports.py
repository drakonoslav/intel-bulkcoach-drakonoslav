from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, List
from app.database import get_db
from app.models import (
    VolumeLog, Exercise, Muscle,
    ActivationMatrixV2, CompositeIndex,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _compute_muscle_stimulus(db: Session, logs: list) -> Dict[str, float]:
    stimulus: Dict[str, float] = {}
    exercise_names = set(l.exercise for l in logs)

    exercises = db.query(Exercise).filter(Exercise.name.in_(exercise_names)).all()
    ex_id_map = {e.name: e.id for e in exercises}

    for log in logs:
        ex_id = ex_id_map.get(log.exercise)
        if not ex_id:
            continue
        activations = (
            db.query(ActivationMatrixV2, Muscle)
            .join(Muscle, ActivationMatrixV2.muscle_id == Muscle.id)
            .filter(ActivationMatrixV2.exercise_id == ex_id)
            .all()
        )
        tonnage = log.tonnage
        for act_row, mu in activations:
            stim = tonnage * act_row.activation
            stimulus[mu.name] = stimulus.get(mu.name, 0.0) + stim

    return {k: round(v, 2) for k, v in sorted(stimulus.items(), key=lambda x: -x[1])}


@router.get("/weekly", summary="Weekly training report with muscle stimulus analysis")
def weekly_report(
    week: str = Query(..., description="ISO week, e.g. 2026-W09"),
    db: Session = Depends(get_db),
):
    logs = db.query(VolumeLog).filter(VolumeLog.week == week).all()

    if not logs:
        return {
            "week": week,
            "exercises": [],
            "total_sets": 0,
            "total_reps": 0,
            "total_tonnage_kg": 0.0,
            "muscle_stimulus": {},
            "breakdown": [],
        }

    exercises = sorted(set(l.exercise for l in logs))
    total_sets = sum(l.sets for l in logs)
    total_reps = sum(l.reps * l.sets for l in logs)
    total_tonnage = sum(l.tonnage for l in logs)

    muscle_stimulus = _compute_muscle_stimulus(db, logs)

    breakdown = []
    for ex in exercises:
        ex_logs = [l for l in logs if l.exercise == ex]
        ex_sets = sum(l.sets for l in ex_logs)
        ex_reps = sum(l.reps * l.sets for l in ex_logs)
        ex_tonnage = sum(l.tonnage for l in ex_logs)
        ex_top_1rm = max(l.estimated_1rm for l in ex_logs)
        breakdown.append({
            "exercise": ex,
            "sets": ex_sets,
            "reps": ex_reps,
            "tonnage_kg": round(ex_tonnage, 2),
            "top_estimated_1rm": round(ex_top_1rm, 2),
            "entries": len(ex_logs),
        })

    return {
        "week": week,
        "exercises": exercises,
        "total_sets": total_sets,
        "total_reps": total_reps,
        "total_tonnage_kg": round(total_tonnage, 2),
        "muscle_stimulus": muscle_stimulus,
        "breakdown": breakdown,
    }
