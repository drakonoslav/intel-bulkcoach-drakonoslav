from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.database import get_db
from app.models import VolumeLog
from app.schemas import WeeklyReport

router = APIRouter(prefix="/reports", tags=["reports"])

PRESET_CONFIG = {
    "strength": {
        "min_intensity_pct": 80,
        "target_sets_range": (3, 6),
        "target_reps_range": (1, 6),
        "volume_unit": "relative",
        "recommendations": [
            "Keep intensity ≥ 80% 1RM for primary lifts.",
            "Limit total weekly sets per movement to 10–20.",
            "Prioritise rest 3–5 min between heavy sets.",
        ],
    },
    "hypertrophy": {
        "min_intensity_pct": 60,
        "target_sets_range": (3, 5),
        "target_reps_range": (6, 15),
        "volume_unit": "absolute",
        "recommendations": [
            "Target 10–20 working sets per muscle group per week.",
            "Keep rest 60–90 seconds for accessory work.",
            "Use progressive overload on weight or reps each session.",
        ],
    },
    "injury": {
        "min_intensity_pct": 40,
        "target_sets_range": (2, 4),
        "target_reps_range": (10, 20),
        "volume_unit": "absolute",
        "recommendations": [
            "Reduce load to RPE ≤ 6 until pain-free range of motion is restored.",
            "Prioritise unilateral and isolation movements.",
            "Increase frequency but reduce per-session volume.",
            "Consult a physiotherapist for persistent issues.",
        ],
    },
}


@router.get("/weekly", response_model=WeeklyReport, summary="Weekly training report")
def weekly_report(
    week: str = Query(..., description="ISO week string, e.g. 2026-W09"),
    preset: str = Query("strength", description="strength | hypertrophy | injury"),
    db: Session = Depends(get_db),
):
    if preset not in PRESET_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown preset '{preset}'. Use: {list(PRESET_CONFIG)}")

    logs = db.query(VolumeLog).filter(VolumeLog.week == week).all()

    if not logs:
        return WeeklyReport(
            week=week,
            preset=preset,
            exercises=[],
            total_sets=0,
            total_reps=0,
            total_tonnage_kg=0.0,
            avg_intensity_pct=None,
            breakdown=[],
            recommendations=PRESET_CONFIG[preset]["recommendations"],
        )

    exercises = sorted(set(l.exercise for l in logs))
    total_sets = sum(l.sets for l in logs)
    total_reps = sum(l.reps * l.sets for l in logs)
    total_tonnage = sum(l.tonnage for l in logs)

    e1rms = [l.estimated_1rm for l in logs]
    avg_1rm = sum(e1rms) / len(e1rms) if e1rms else None

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

    return WeeklyReport(
        week=week,
        preset=preset,
        exercises=exercises,
        total_sets=total_sets,
        total_reps=total_reps,
        total_tonnage_kg=round(total_tonnage, 2),
        avg_intensity_pct=round(avg_1rm, 2) if avg_1rm else None,
        breakdown=breakdown,
        recommendations=PRESET_CONFIG[preset]["recommendations"],
    )
