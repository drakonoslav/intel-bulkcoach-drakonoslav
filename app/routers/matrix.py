from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import Exercise, Muscle, ActivationMatrixV2, RoleWeightedMatrixV2, PhaseMatrixV3, BottleneckMatrixV4, StabilizationMatrixV5

router = APIRouter(prefix="/matrix", tags=["matrix"])


def _build_matrix_response(db, model, value_attr, exercise_filter, muscle_filter, default_val):
    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_names = [m.name for m in all_muscles]
    muscle_id_to_idx = {m.id: i for i, m in enumerate(all_muscles)}

    ex_q = db.query(Exercise).order_by(Exercise.id)
    if exercise_filter:
        ex_q = ex_q.filter(Exercise.name == exercise_filter.strip())
    all_exercises = ex_q.all()
    exercise_names = [e.name for e in all_exercises]
    exercise_ids = [e.id for e in all_exercises]

    q = db.query(model).filter(
        model.exercise_id.in_(exercise_ids)
    )
    if muscle_filter:
        mu = db.query(Muscle).filter(Muscle.name == muscle_filter.strip()).first()
        if mu:
            q = q.filter(model.muscle_id == mu.id)

    rows_raw = q.all()

    if muscle_filter and not exercise_filter:
        mu = db.query(Muscle).filter(Muscle.name == muscle_filter.strip()).first()
        if mu:
            q2 = db.query(model).filter(
                model.muscle_id == mu.id
            ).order_by(model.exercise_id)
            rows_raw = q2.all()
            ex_ids_in = sorted(set(r.exercise_id for r in rows_raw))
            all_exercises = db.query(Exercise).filter(Exercise.id.in_(ex_ids_in)).order_by(Exercise.id).all()
            exercise_names = [e.name for e in all_exercises]
            exercise_ids = [e.id for e in all_exercises]
            muscle_names = [mu.name]
            muscle_id_to_idx = {mu.id: 0}

    ex_id_to_idx = {eid: i for i, eid in enumerate(exercise_ids)}
    n_muscles = len(muscle_names)
    matrix = [[default_val] * n_muscles for _ in range(len(exercise_names))]

    for r in rows_raw:
        ei = ex_id_to_idx.get(r.exercise_id)
        mi = muscle_id_to_idx.get(r.muscle_id)
        if ei is not None and mi is not None:
            matrix[ei][mi] = getattr(r, value_attr)

    return {
        "exercises": exercise_names,
        "muscles": muscle_names,
        "matrix": matrix,
    }


@router.get("/v2", summary="Base activation matrix (92x26, int 0-5)")
def get_v2(
    exercise: Optional[str] = Query(None, description="Filter to a single exercise"),
    muscle: Optional[str] = Query(None, description="Filter to a single muscle"),
    db: Session = Depends(get_db),
):
    return _build_matrix_response(
        db, ActivationMatrixV2, "activation_value", exercise, muscle, 0
    )


@router.get("/role-weighted-v2", summary="Role-weighted matrix (92x26, float 0-1)")
def get_role_weighted_v2(
    exercise: Optional[str] = Query(None, description="Filter to a single exercise"),
    muscle: Optional[str] = Query(None, description="Filter to a single muscle"),
    db: Session = Depends(get_db),
):
    return _build_matrix_response(
        db, RoleWeightedMatrixV2, "role_weight", exercise, muscle, 0.0
    )


@router.get("/v3", summary="Phase matrix v3 (92x26, float 0-5, per phase)")
def get_v3(
    phase: str = Query(..., description="Phase: initiation, midrange, or lockout"),
    exercise: Optional[str] = Query(None, description="Filter to a single exercise"),
    muscle: Optional[str] = Query(None, description="Filter to a single muscle"),
    db: Session = Depends(get_db),
):
    phase = phase.strip().lower()
    if phase not in ("initiation", "midrange", "lockout"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="phase must be initiation, midrange, or lockout")

    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_names = [m.name for m in all_muscles]
    muscle_id_to_idx = {m.id: i for i, m in enumerate(all_muscles)}

    ex_q = db.query(Exercise).order_by(Exercise.id)
    if exercise:
        ex_q = ex_q.filter(Exercise.name == exercise.strip())
    all_exercises = ex_q.all()
    exercise_names = [e.name for e in all_exercises]
    exercise_ids = [e.id for e in all_exercises]

    q = db.query(PhaseMatrixV3).filter(
        PhaseMatrixV3.exercise_id.in_(exercise_ids),
        PhaseMatrixV3.phase == phase,
    )
    if muscle:
        mu = db.query(Muscle).filter(Muscle.name == muscle.strip()).first()
        if mu:
            q = q.filter(PhaseMatrixV3.muscle_id == mu.id)

    rows_raw = q.all()

    if muscle and not exercise:
        mu = db.query(Muscle).filter(Muscle.name == muscle.strip()).first()
        if mu:
            q2 = db.query(PhaseMatrixV3).filter(
                PhaseMatrixV3.muscle_id == mu.id,
                PhaseMatrixV3.phase == phase,
            ).order_by(PhaseMatrixV3.exercise_id)
            rows_raw = q2.all()
            ex_ids_in = sorted(set(r.exercise_id for r in rows_raw))
            all_exercises = db.query(Exercise).filter(Exercise.id.in_(ex_ids_in)).order_by(Exercise.id).all()
            exercise_names = [e.name for e in all_exercises]
            exercise_ids = [e.id for e in all_exercises]
            muscle_names = [mu.name]
            muscle_id_to_idx = {mu.id: 0}

    ex_id_to_idx = {eid: i for i, eid in enumerate(exercise_ids)}
    n_muscles = len(muscle_names)
    matrix = [[0.0] * n_muscles for _ in range(len(exercise_names))]

    for r in rows_raw:
        ei = ex_id_to_idx.get(r.exercise_id)
        mi = muscle_id_to_idx.get(r.muscle_id)
        if ei is not None and mi is not None:
            matrix[ei][mi] = r.phase_value

    return {
        "exercises": exercise_names,
        "muscles": muscle_names,
        "matrix": matrix,
    }


@router.get("/v4/bottleneck", summary="Bottleneck coefficient matrix (92x26, float 0-1)")
def get_v4_bottleneck(
    exercise: Optional[str] = Query(None, description="Filter to a single exercise"),
    muscle: Optional[str] = Query(None, description="Filter to a single muscle"),
    db: Session = Depends(get_db),
):
    return _build_matrix_response(
        db, BottleneckMatrixV4, "bottleneck_coeff", exercise, muscle, 0.0
    )


@router.get("/v5", summary="Dynamic/stability matrix v5 (92x26, float 0-1, per component)")
def get_v5(
    component: str = Query(..., description="Component: dynamic or stability"),
    exercise: Optional[str] = Query(None, description="Filter to a single exercise"),
    muscle: Optional[str] = Query(None, description="Filter to a single muscle"),
    db: Session = Depends(get_db),
):
    component = component.strip().lower()
    if component not in ("dynamic", "stability"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="component must be dynamic or stability")

    all_muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_names = [m.name for m in all_muscles]
    muscle_id_to_idx = {m.id: i for i, m in enumerate(all_muscles)}

    ex_q = db.query(Exercise).order_by(Exercise.id)
    if exercise:
        ex_q = ex_q.filter(Exercise.name == exercise.strip())
    all_exercises = ex_q.all()
    exercise_names = [e.name for e in all_exercises]
    exercise_ids = [e.id for e in all_exercises]

    q = db.query(StabilizationMatrixV5).filter(
        StabilizationMatrixV5.exercise_id.in_(exercise_ids),
        StabilizationMatrixV5.component == component,
    )
    if muscle:
        mu = db.query(Muscle).filter(Muscle.name == muscle.strip()).first()
        if mu:
            q = q.filter(StabilizationMatrixV5.muscle_id == mu.id)

    rows_raw = q.all()

    if muscle and not exercise:
        mu = db.query(Muscle).filter(Muscle.name == muscle.strip()).first()
        if mu:
            q2 = db.query(StabilizationMatrixV5).filter(
                StabilizationMatrixV5.muscle_id == mu.id,
                StabilizationMatrixV5.component == component,
            ).order_by(StabilizationMatrixV5.exercise_id)
            rows_raw = q2.all()
            ex_ids_in = sorted(set(r.exercise_id for r in rows_raw))
            all_exercises = db.query(Exercise).filter(Exercise.id.in_(ex_ids_in)).order_by(Exercise.id).all()
            exercise_names = [e.name for e in all_exercises]
            exercise_ids = [e.id for e in all_exercises]
            muscle_names = [mu.name]
            muscle_id_to_idx = {mu.id: 0}

    ex_id_to_idx = {eid: i for i, eid in enumerate(exercise_ids)}
    n_muscles = len(muscle_names)
    matrix = [[0.0] * n_muscles for _ in range(len(exercise_names))]

    for r in rows_raw:
        ei = ex_id_to_idx.get(r.exercise_id)
        mi = muscle_id_to_idx.get(r.muscle_id)
        if ei is not None and mi is not None:
            matrix[ei][mi] = r.value

    return {
        "exercises": exercise_names,
        "muscles": muscle_names,
        "matrix": matrix,
    }
