from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict
from app.database import get_db
from app.models import VolumeLog, Exercise, Muscle, ActivationMatrixV2

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
            .filter(ActivationMatrixV2.activation_value > 0)
            .all()
        )
        tonnage = log.tonnage
        for act_row, mu in activations:
            stim = tonnage * act_row.activation_value
            stimulus[mu.name] = stimulus.get(mu.name, 0.0) + stim

    return {k: round(v, 2) for k, v in sorted(stimulus.items(), key=lambda x: -x[1])}


@router.get("/weekly", summary="Weekly training report with muscle stimulus")
def weekly_report(
    week: str = Query(..., description="ISO week, e.g. 2026-W09", examples=["2026-W09"]),
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
        breakdown.append({
            "exercise": ex,
            "sets": sum(l.sets for l in ex_logs),
            "reps": sum(l.reps * l.sets for l in ex_logs),
            "tonnage_kg": round(sum(l.tonnage for l in ex_logs), 2),
            "top_estimated_1rm": round(max(l.estimated_1rm for l in ex_logs), 2),
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
