from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
import isoweek

from app.database import get_db
from app.models import VolumeLog
from app.schemas import VolumeIngest, VolumeLogOut

router = APIRouter(prefix="/volume", tags=["volume"])


def _week_label(d: date) -> str:
    w = isoweek.Week.withdate(d)
    return f"{w.year}-W{str(w.week).zfill(2)}"


@router.post("/ingest", summary="Log a set of work")
def ingest_volume(payload: VolumeIngest, db: Session = Depends(get_db)):
    week = _week_label(payload.date)
    log = VolumeLog(
        exercise=payload.exercise.lower().strip(),
        weight_kg=payload.weight_kg,
        reps=payload.reps,
        sets=payload.sets,
        date=payload.date,
        week=week,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "id": log.id,
        "exercise": log.exercise,
        "weight_kg": log.weight_kg,
        "reps": log.reps,
        "sets": log.sets,
        "date": str(log.date),
        "week": log.week,
        "tonnage": log.tonnage,
        "estimated_1rm": round(log.estimated_1rm, 2),
        "notes": log.notes,
    }


@router.get("/logs", summary="Query logged volume entries")
def get_logs(
    exercise: Optional[str] = Query(None),
    week: Optional[str] = Query(None),
    since: Optional[date] = Query(None),
    until: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(VolumeLog)
    if exercise:
        q = q.filter(VolumeLog.exercise == exercise.lower().strip())
    if week:
        q = q.filter(VolumeLog.week == week)
    if since:
        q = q.filter(VolumeLog.date >= since)
    if until:
        q = q.filter(VolumeLog.date <= until)
    logs = q.order_by(VolumeLog.date.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "exercise": l.exercise,
            "weight_kg": l.weight_kg,
            "reps": l.reps,
            "sets": l.sets,
            "date": str(l.date),
            "week": l.week,
            "tonnage": l.tonnage,
            "estimated_1rm": round(l.estimated_1rm, 2),
            "notes": l.notes,
        }
        for l in logs
    ]
