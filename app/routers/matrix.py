from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app.database import get_db
from app.models import (
    Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
    PhaseMatrixV3, BottleneckMatrixV4,
    StabilizationMatrixV5, CompositeIndex,
)

router = APIRouter(prefix="/matrix", tags=["matrix"])


def _apply_filters(q, model, exercise: Optional[str], muscle: Optional[str]):
    if exercise:
        q = q.join(Exercise, model.exercise_id == Exercise.id).filter(
            Exercise.name == exercise.lower().strip()
        )
    if muscle:
        q = q.join(Muscle, model.muscle_id == Muscle.id).filter(
            Muscle.name == muscle.lower().strip()
        )
    return q


@router.get("/v2", summary="Base activation matrix (93x26)")
def get_v2(
    exercise: Optional[str] = Query(None),
    muscle: Optional[str] = Query(None),
    include_roles: bool = Query(False, description="Include role-weighted values"),
    db: Session = Depends(get_db),
):
    q = db.query(ActivationMatrixV2).options(
        joinedload(ActivationMatrixV2.exercise),
        joinedload(ActivationMatrixV2.muscle),
    )
    q = _apply_filters(q, ActivationMatrixV2, exercise, muscle)
    rows = q.all()

    data = []
    for r in rows:
        entry = {
            "exercise": r.exercise.name,
            "muscle": r.muscle.name,
            "activation": r.activation,
        }
        if include_roles:
            rw = db.query(RoleWeightedMatrixV2).filter_by(
                exercise_id=r.exercise_id, muscle_id=r.muscle_id
            ).first()
            if rw:
                entry["role"] = rw.role
                entry["role_weight"] = rw.weight
                entry["weighted_activation"] = rw.weighted_activation
        data.append(entry)

    return {
        "version": "v2",
        "dimensions": {"rows": len(data)},
        "data": data,
    }


@router.get("/v3", summary="Phase-expanded matrices (initiation/mid/lockout)")
def get_v3(
    exercise: Optional[str] = Query(None),
    muscle: Optional[str] = Query(None),
    phase: Optional[str] = Query(None, description="initiation | mid | lockout"),
    db: Session = Depends(get_db),
):
    q = db.query(PhaseMatrixV3).options(
        joinedload(PhaseMatrixV3.exercise),
        joinedload(PhaseMatrixV3.muscle),
    )
    q = _apply_filters(q, PhaseMatrixV3, exercise, muscle)
    if phase:
        q = q.filter(PhaseMatrixV3.phase == phase.lower().strip())
    rows = q.all()

    data = [
        {
            "exercise": r.exercise.name,
            "muscle": r.muscle.name,
            "phase": r.phase,
            "activation": r.activation,
        }
        for r in rows
    ]
    return {"version": "v3", "dimensions": {"rows": len(data)}, "data": data}


@router.get("/v4", summary="Bottleneck coefficient matrix")
def get_v4(
    exercise: Optional[str] = Query(None),
    muscle: Optional[str] = Query(None),
    limiting_only: bool = Query(False, description="Return only limiting muscles"),
    db: Session = Depends(get_db),
):
    q = db.query(BottleneckMatrixV4).options(
        joinedload(BottleneckMatrixV4.exercise),
        joinedload(BottleneckMatrixV4.muscle),
    )
    q = _apply_filters(q, BottleneckMatrixV4, exercise, muscle)
    if limiting_only:
        q = q.filter(BottleneckMatrixV4.is_limiting == 1)
    rows = q.all()

    data = [
        {
            "exercise": r.exercise.name,
            "muscle": r.muscle.name,
            "bottleneck_coefficient": r.bottleneck_coefficient,
            "is_limiting": bool(r.is_limiting),
        }
        for r in rows
    ]
    return {"version": "v4", "dimensions": {"rows": len(data)}, "data": data}


@router.get("/v5", summary="Stabilization & dynamic matrices")
def get_v5(
    exercise: Optional[str] = Query(None),
    muscle: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(StabilizationMatrixV5).options(
        joinedload(StabilizationMatrixV5.exercise),
        joinedload(StabilizationMatrixV5.muscle),
    )
    q = _apply_filters(q, StabilizationMatrixV5, exercise, muscle)
    rows = q.all()

    data = [
        {
            "exercise": r.exercise.name,
            "muscle": r.muscle.name,
            "stabilization_score": r.stabilization_score,
            "dynamic_score": r.dynamic_score,
        }
        for r in rows
    ]
    return {"version": "v5", "dimensions": {"rows": len(data)}, "data": data}


@router.get("/composite", summary="Composite muscle profile index")
def get_composite(
    exercise: Optional[str] = Query(None),
    muscle: Optional[str] = Query(None),
    min_score: float = Query(0.0, description="Minimum composite score threshold"),
    db: Session = Depends(get_db),
):
    q = db.query(CompositeIndex).options(
        joinedload(CompositeIndex.exercise),
        joinedload(CompositeIndex.muscle),
    )
    q = _apply_filters(q, CompositeIndex, exercise, muscle)
    if min_score > 0:
        q = q.filter(CompositeIndex.composite_score >= min_score)
    rows = q.order_by(CompositeIndex.composite_score.desc()).all()

    data = [
        {
            "exercise": r.exercise.name,
            "muscle": r.muscle.name,
            "composite_score": r.composite_score,
            "activation_component": r.activation_component,
            "phase_component": r.phase_component,
            "bottleneck_component": r.bottleneck_component,
            "stabilization_component": r.stabilization_component,
        }
        for r in rows
    ]
    return {"version": "composite", "dimensions": {"rows": len(data)}, "data": data}
