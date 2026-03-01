from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from app.database import get_db
from app.models import LiftSet, Exercise

router = APIRouter(prefix="/lifts", tags=["lifts"])


class LiftSetIn(BaseModel):
    performed_at: date = Field(..., examples=["2026-02-28"])
    exercise: str = Field(..., examples=["Conventional Deadlift"])
    weight: float = Field(..., ge=0, examples=[225])
    reps: int = Field(..., ge=0, examples=[5])
    notes: Optional[str] = Field(None, examples=["felt strong"])
    source: Optional[str] = Field(None, examples=["expo"])


class BatchIn(BaseModel):
    sets: List[LiftSetIn] = Field(..., min_length=1)


@router.post("/sets", summary="Log a lift set")
def create_lift_set(payload: LiftSetIn, db: Session = Depends(get_db)):
    ex = db.query(Exercise).filter(Exercise.name == payload.exercise).first()
    if not ex:
        raise HTTPException(status_code=404, detail=f"Unknown exercise: {payload.exercise}")

    tonnage = payload.weight * payload.reps

    row = LiftSet(
        performed_at=payload.performed_at,
        exercise_id=ex.id,
        weight=payload.weight,
        reps=payload.reps,
        tonnage=tonnage,
        notes=payload.notes,
        source=payload.source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "performed_at": str(row.performed_at),
        "exercise": ex.name,
        "weight": row.weight,
        "reps": row.reps,
        "tonnage": row.tonnage,
        "notes": row.notes,
        "source": row.source,
    }


@router.post("/sets/batch", summary="Batch-log multiple lift sets")
def create_lift_sets_batch(
    payload: BatchIn,
    bestEffort: bool = Query(False, description="If true, insert valid sets and return errors for invalid ones"),
    db: Session = Depends(get_db),
):
    ex_cache = {}
    all_exercises = db.query(Exercise).all()
    for e in all_exercises:
        ex_cache[e.name] = e

    if not bestEffort:
        errors = []
        for i, s in enumerate(payload.sets):
            if s.exercise not in ex_cache:
                errors.append({"index": i, "exercise": s.exercise, "error": "Unknown exercise"})
        if errors:
            raise HTTPException(status_code=400, detail={"message": "Batch rejected: unknown exercises", "errors": errors})

    rows = []
    inserted_errors = []
    for i, s in enumerate(payload.sets):
        ex = ex_cache.get(s.exercise)
        if not ex:
            if bestEffort:
                inserted_errors.append({"index": i, "exercise": s.exercise, "error": "Unknown exercise"})
                continue
        tonnage = s.weight * s.reps
        row = LiftSet(
            performed_at=s.performed_at,
            exercise_id=ex.id,
            weight=s.weight,
            reps=s.reps,
            tonnage=tonnage,
            notes=s.notes,
            source=s.source,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for row in rows:
        db.refresh(row)

    result = {
        "inserted": len(rows),
        "rows": [{"id": r.id, "tonnage": r.tonnage} for r in rows],
    }
    if bestEffort and inserted_errors:
        result["errors"] = inserted_errors
    return result


@router.get("/sets", summary="Query lift sets by date range")
def get_lift_sets(
    db: Session = Depends(get_db),
    from_date: Optional[date] = Query(None, alias="from", description="Start date YYYY-MM-DD", examples=["2026-02-23"]),
    to_date: Optional[date] = Query(None, alias="to", description="End date YYYY-MM-DD", examples=["2026-02-25"]),
    exercise: Optional[str] = Query(None, examples=["Conventional Deadlift"]),
    limit: int = Query(200, ge=1, le=1000),
):
    q = db.query(LiftSet).join(Exercise)
    if from_date:
        q = q.filter(LiftSet.performed_at >= from_date)
    if to_date:
        q = q.filter(LiftSet.performed_at <= to_date)
    if exercise:
        q = q.filter(Exercise.name == exercise)
    rows = q.order_by(LiftSet.performed_at.desc(), LiftSet.id.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "performed_at": str(r.performed_at),
            "exercise": r.exercise.name,
            "weight": r.weight,
            "reps": r.reps,
            "tonnage": r.tonnage,
            "notes": r.notes,
            "source": r.source,
        }
        for r in rows
    ]
