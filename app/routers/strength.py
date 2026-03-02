import math
from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LiftSet, Exercise

router = APIRouter(prefix="/strength", tags=["strength"])

SCHEMA_VERSION = 1
LANE = "strength_index_v1"
ROLLING_WINDOW = 7
VELOCITY_WINDOW = 14
LOOKBACK_BUFFER = 30


def _gather_daily_stats(db: Session, start: date, end: date):
    sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= start,
        LiftSet.performed_at <= end,
    ).all()

    by_day = defaultdict(list)
    for s in sets:
        by_day[s.performed_at].append(s)

    daily = {}
    for d, day_sets in by_day.items():
        total_tonnage = sum(s.tonnage for s in day_sets)
        total_reps = sum(s.reps for s in day_sets)
        total_sets = len(day_sets)
        weights = [s.weight for s in day_sets if s.weight > 0]
        avg_weight = sum(weights) / len(weights) if weights else 0.0
        avg_reps = total_reps / total_sets if total_sets > 0 else 0.0
        max_weight = max(weights) if weights else 0.0

        daily[d] = {
            "tonnage": total_tonnage,
            "total_reps": total_reps,
            "total_sets": total_sets,
            "avg_weight": avg_weight,
            "avg_reps": avg_reps,
            "max_weight": max_weight,
        }

    return daily


def _detect_phase(avg_reps: float, tonnage: float, baseline_tonnage: float) -> str:
    if tonnage == 0:
        return "rest"
    tonnage_ratio = tonnage / baseline_tonnage if baseline_tonnage > 0 else 1.0
    if tonnage_ratio < 0.4:
        return "deload"
    if avg_reps <= 3:
        return "peaking"
    if avg_reps <= 6:
        return "strength"
    return "hypertrophy"


@router.get("/trend", summary="Strength index trend over a date range (dense, per-day)")
def strength_trend(
    from_date: date = Query(..., alias="from", examples=["2026-02-01"]),
    to_date: date = Query(..., alias="to", examples=["2026-03-01"]),
    db: Session = Depends(get_db),
):
    buffer_start = from_date - timedelta(days=LOOKBACK_BUFFER)

    daily_stats = _gather_daily_stats(db, buffer_start, to_date)

    training_days = [d for d in daily_stats if d >= buffer_start and daily_stats[d]["tonnage"] > 0]
    if training_days:
        baseline_tonnage = sum(daily_stats[d]["tonnage"] for d in training_days) / len(training_days)
    else:
        baseline_tonnage = 1.0

    all_dates = []
    d = buffer_start
    while d <= to_date:
        all_dates.append(d)
        d += timedelta(days=1)

    strength_index_series = {}
    for d in all_dates:
        stats = daily_stats.get(d)
        if stats and stats["tonnage"] > 0:
            strength_index_series[d] = stats["tonnage"] / baseline_tonnage
        else:
            strength_index_series[d] = 0.0

    rolling_avg_series = {}
    for d in all_dates:
        window_vals = []
        for i in range(ROLLING_WINDOW):
            wd = d - timedelta(days=i)
            if wd in strength_index_series:
                window_vals.append(strength_index_series[wd])
        rolling_avg_series[d] = sum(window_vals) / len(window_vals) if window_vals else 0.0

    velocity_series = {}
    for d in all_dates:
        prev_d = d - timedelta(days=VELOCITY_WINDOW)
        if prev_d in rolling_avg_series:
            velocity_series[d] = (rolling_avg_series[d] - rolling_avg_series[prev_d]) / VELOCITY_WINDOW
        else:
            velocity_series[d] = 0.0

    all_sets_by_day = defaultdict(list)
    all_sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= from_date - timedelta(days=VELOCITY_WINDOW),
        LiftSet.performed_at <= to_date,
    ).all()
    for s in all_sets:
        all_sets_by_day[s.performed_at].append(s)

    days = []
    d = from_date
    while d <= to_date:
        stats = daily_stats.get(d)
        si = round(strength_index_series.get(d, 0.0), 4)
        ra = round(rolling_avg_series.get(d, 0.0), 4)
        vel = round(velocity_series.get(d, 0.0), 6)

        trend_score = round(1.0 / (1.0 + math.exp(-vel * 200)), 4)

        if stats and stats["tonnage"] > 0:
            phase = _detect_phase(stats["avg_reps"], stats["tonnage"], baseline_tonnage)
        else:
            phase = "rest"

        prev_d = d - timedelta(days=1)
        prev_phase = None
        prev_stats = daily_stats.get(prev_d)
        if prev_stats and prev_stats["tonnage"] > 0:
            prev_phase = _detect_phase(prev_stats["avg_reps"], prev_stats["tonnage"], baseline_tonnage)

        phase_transition = None
        if prev_phase and prev_phase != phase and phase != "rest":
            phase_transition = f"{prev_phase}->{phase}"

        sessions_14d = 0
        exercises_14d = set()
        for i in range(VELOCITY_WINDOW):
            wd = d - timedelta(days=i)
            wd_stats = daily_stats.get(wd)
            if wd_stats and wd_stats["tonnage"] > 0:
                sessions_14d += 1
            for s in all_sets_by_day.get(wd, []):
                exercises_14d.add(s.exercise_id)

        unique_exercises_14d = len(exercises_14d)
        if sessions_14d >= 2 and unique_exercises_14d > 0:
            swap_penalty = min(1.0, (unique_exercises_14d / sessions_14d - 1.0) * 0.25)
            swap_penalty = max(0.0, swap_penalty)
        else:
            swap_penalty = 0.0

        days.append({
            "date": str(d),
            "day_strength_index": si,
            "rolling_avg_7d": ra,
            "velocity_14d": vel,
            "velocity_14d_unit": "index_delta_per_day",
            "trend_score": trend_score,
            "phase": phase,
            "phase_transition": phase_transition,
            "sessions_in_14d": sessions_14d,
            "swap_penalty_14d": round(swap_penalty, 4),
            "tonnage": round(stats["tonnage"], 2) if stats else 0.0,
            "sets": stats["total_sets"] if stats else 0,
            "avg_weight": round(stats["avg_weight"], 2) if stats else 0.0,
            "avg_reps": round(stats["avg_reps"], 2) if stats else 0.0,
        })

        d += timedelta(days=1)

    latest = days[-1] if days else None

    return {
        "source": "intel",
        "lane": LANE,
        "schema_version": SCHEMA_VERSION,
        "from": str(from_date),
        "to": str(to_date),
        "baseline_tonnage": round(baseline_tonnage, 2),
        "training_days_in_baseline": len(training_days),
        "days": days,
        "latest": latest,
    }


@router.get("/day", summary="Single-day strength breakdown with per-exercise contributors")
def strength_day(
    date_param: date = Query(..., alias="date", examples=["2026-03-01"]),
    db: Session = Depends(get_db),
):
    buffer_start = date_param - timedelta(days=LOOKBACK_BUFFER)

    daily_stats = _gather_daily_stats(db, buffer_start, date_param)

    training_days = [d for d in daily_stats if daily_stats[d]["tonnage"] > 0]
    baseline_tonnage = sum(daily_stats[d]["tonnage"] for d in training_days) / len(training_days) if training_days else 1.0

    stats = daily_stats.get(date_param)

    sets = db.query(LiftSet).filter(LiftSet.performed_at == date_param).all()
    ex_ids = list({s.exercise_id for s in sets})
    ex_map = {e.id: e.name for e in db.query(Exercise).filter(Exercise.id.in_(ex_ids)).all()} if ex_ids else {}

    by_exercise = defaultdict(list)
    for s in sets:
        by_exercise[s.exercise_id].append(s)

    contributors = []
    for ex_id, ex_sets in by_exercise.items():
        tonnage = sum(s.tonnage for s in ex_sets)
        reps = sum(s.reps for s in ex_sets)
        weights = [s.weight for s in ex_sets if s.weight > 0]
        contributors.append({
            "exercise": ex_map.get(ex_id, f"id:{ex_id}"),
            "exercise_id": ex_id,
            "sets": len(ex_sets),
            "total_tonnage": round(tonnage, 2),
            "total_reps": reps,
            "avg_weight": round(sum(weights) / len(weights), 2) if weights else 0.0,
            "max_weight": max(weights) if weights else 0.0,
            "contribution_pct": round(tonnage / stats["tonnage"] * 100, 2) if stats and stats["tonnage"] > 0 else 0.0,
        })

    contributors.sort(key=lambda c: c["total_tonnage"], reverse=True)

    si = stats["tonnage"] / baseline_tonnage if stats and stats["tonnage"] > 0 else 0.0
    phase = _detect_phase(stats["avg_reps"], stats["tonnage"], baseline_tonnage) if stats else "rest"

    return {
        "source": "intel",
        "lane": LANE,
        "schema_version": SCHEMA_VERSION,
        "date": str(date_param),
        "baseline_tonnage": round(baseline_tonnage, 2),
        "day_strength_index": round(si, 4),
        "phase": phase,
        "tonnage": round(stats["tonnage"], 2) if stats else 0.0,
        "total_sets": stats["total_sets"] if stats else 0,
        "total_reps": stats["total_reps"] if stats else 0,
        "avg_weight": round(stats["avg_weight"], 2) if stats else 0.0,
        "avg_reps": round(stats["avg_reps"], 2) if stats else 0.0,
        "max_weight": stats["max_weight"] if stats else 0.0,
        "contributors": contributors,
    }
