import logging
import traceback
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from datetime import date
from app.game_state import DATA_FLOOR_DATE, DATA_FLOOR_TS

from app.database import get_db
from app.models import LiftSet, Exercise

logger = logging.getLogger(__name__)

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
    error_id = uuid.uuid4().hex[:12]

    try:
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

        logger.info("batch error_id=%s before_commit count=%d", error_id, len(rows))
        db.flush()
        pre_commit_ids = [r.id for r in rows]
        db.commit()
        logger.info("batch error_id=%s after_commit ids=%s", error_id, pre_commit_ids)

        persisted = db.execute(
            text("SELECT id, performed_at, exercise_id, weight, reps, tonnage FROM lift_sets WHERE id = ANY(:ids) ORDER BY id"),
            {"ids": pre_commit_ids},
        ).fetchall()

        persisted_rows = [
            {"id": r[0], "performed_at": str(r[1]), "exercise_id": r[2], "weight": float(r[3]), "reps": r[4], "tonnage": float(r[5])}
            for r in persisted
        ]

        result = {
            "inserted": len(persisted_rows),
            "rows": persisted_rows,
            "committed": True,
            "persisted_count": len(persisted_rows),
        }
        if bestEffort and inserted_errors:
            result["errors"] = inserted_errors
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("batch error_id=%s EXCEPTION\n%s", error_id, traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "detail": "internal_error",
                "error_id": error_id,
                "where": "lifts.batch",
                "hint": str(exc)[:200],
                "committed": False,
            },
        )


@router.get("/sets", summary="Query lift sets by date range")
def get_lift_sets(
    db: Session = Depends(get_db),
    from_date: Optional[date] = Query(None, alias="from", description="Start date YYYY-MM-DD", examples=["2026-02-23"]),
    to_date: Optional[date] = Query(None, alias="to", description="End date YYYY-MM-DD", examples=["2026-02-25"]),
    exercise: Optional[str] = Query(None, examples=["Conventional Deadlift"]),
    limit: int = Query(200, ge=1, le=1000),
):
    q = db.query(LiftSet).join(Exercise)
    q = q.filter(LiftSet.performed_at >= DATA_FLOOR_DATE, LiftSet.created_at >= DATA_FLOOR_TS)
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
