from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import Exercise, Muscle, ActivationMatrixV2

router = APIRouter(prefix="/matrix", tags=["matrix"])


@router.get("/v2", summary="Base activation matrix (92x26)")
def get_v2(
    exercise: Optional[str] = Query(None, description="Filter to a single exercise"),
    muscle: Optional[str] = Query(None, description="Filter to a single muscle"),
    db: Session = Depends(get_db),
):
    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_names = [m.name for m in all_muscles]
    muscle_id_to_idx = {m.id: i for i, m in enumerate(all_muscles)}

    ex_q = db.query(Exercise).order_by(Exercise.id)
    if exercise:
        ex_q = ex_q.filter(Exercise.name == exercise.strip())
    all_exercises = ex_q.all()
    exercise_names = [e.name for e in all_exercises]
    exercise_ids = [e.id for e in all_exercises]

    act_q = db.query(ActivationMatrixV2).filter(
        ActivationMatrixV2.exercise_id.in_(exercise_ids)
    )
    if muscle:
        mu = db.query(Muscle).filter(Muscle.name == muscle.strip()).first()
        if mu:
            act_q = act_q.filter(ActivationMatrixV2.muscle_id == mu.id)

    rows_raw = act_q.all()

    if muscle and not exercise:
        mu = db.query(Muscle).filter(Muscle.name == muscle.strip()).first()
        if mu:
            act_q2 = db.query(ActivationMatrixV2).filter(
                ActivationMatrixV2.muscle_id == mu.id
            ).order_by(ActivationMatrixV2.exercise_id)
            rows_raw = act_q2.all()
            ex_ids_in = sorted(set(r.exercise_id for r in rows_raw))
            all_exercises = db.query(Exercise).filter(Exercise.id.in_(ex_ids_in)).order_by(Exercise.id).all()
            exercise_names = [e.name for e in all_exercises]
            exercise_ids = [e.id for e in all_exercises]
            muscle_names = [mu.name]
            muscle_id_to_idx = {mu.id: 0}

    ex_id_to_idx = {eid: i for i, eid in enumerate(exercise_ids)}
    n_muscles = len(muscle_names)
    matrix = [[0] * n_muscles for _ in range(len(exercise_names))]

    for r in rows_raw:
        ei = ex_id_to_idx.get(r.exercise_id)
        mi = muscle_id_to_idx.get(r.muscle_id)
        if ei is not None and mi is not None:
            matrix[ei][mi] = r.activation_value

    return {
        "exercises": exercise_names,
        "muscles": muscle_names,
        "matrix": matrix,
    }
