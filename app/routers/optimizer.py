from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from app.schemas import OptimizerResult
from app.data import v2, v3, v4, v5, composite

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

GOAL_DATASET_MAP = {
    "strength": v4,
    "hypertrophy": v3,
    "injury": v2,
    "conjugate": v5,
    "balanced": composite,
}

GOAL_PRESET_MAP = {
    "strength": "strength",
    "hypertrophy": "hypertrophy",
    "injury": "injury",
    "conjugate": "strength",
    "balanced": "strength",
}

EXERCISE_PRIORITY = {
    "strength":    ["squat", "deadlift", "bench_press", "overhead_press", "row"],
    "hypertrophy": ["bench_press", "row", "squat", "overhead_press", "deadlift"],
    "injury":      ["row", "overhead_press", "bench_press", "squat", "deadlift"],
    "conjugate":   ["squat", "bench_press", "deadlift", "overhead_press", "row"],
    "balanced":    ["squat", "bench_press", "deadlift", "row", "overhead_press"],
}

def _parse_constraints(raw: Optional[str]) -> dict:
    constraints = {}
    if not raw:
        return constraints
    for item in raw.split(","):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            constraints[k.strip()] = v.strip()
    return constraints


@router.get("", response_model=OptimizerResult, summary="Optimise exercise selection for a goal")
def optimizer(
    goal: str = Query("strength", description="strength | hypertrophy | injury | conjugate | balanced"),
    n: int = Query(8, ge=1, le=20, description="Number of exercise slots per week"),
    constraints: Optional[str] = Query(
        None,
        description="Comma-separated key=value constraints. Supported: exclude=squat,deadlift | focus=upper | max_frequency=3",
    ),
):
    if goal not in GOAL_DATASET_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown goal '{goal}'. Use: {list(GOAL_DATASET_MAP)}",
        )

    dataset = GOAL_DATASET_MAP[goal]
    preset = GOAL_PRESET_MAP[goal]
    priority = EXERCISE_PRIORITY[goal].copy()
    c = _parse_constraints(constraints)

    excluded = [e.strip() for e in c.get("exclude", "").split(",") if e.strip()]
    focus = c.get("focus", "all")
    max_freq = int(c.get("max_frequency", 99))

    UPPER = {"bench_press", "overhead_press", "row"}
    LOWER = {"squat", "deadlift"}

    if focus == "upper":
        priority = [e for e in priority if e in UPPER]
    elif focus == "lower":
        priority = [e for e in priority if e in LOWER]

    priority = [e for e in priority if e not in excluded]

    selected = []
    slot_count = 0
    for ex in priority:
        if slot_count >= n:
            break
        defaults = dataset.EXERCISE_DEFAULTS.get(ex, {})
        ex_config = defaults.get(preset) or (list(defaults.values())[0] if defaults else {})
        freq = ex_config.get("frequency", 1)
        freq = min(freq, max_freq)
        slots_needed = freq
        if slot_count + slots_needed > n:
            slots_needed = n - slot_count
        selected.append({
            "exercise": ex,
            "frequency_per_week": slots_needed,
            "config": ex_config,
            "dataset_version": dataset.DATASET_VERSION,
        })
        slot_count += slots_needed

    total_sets = sum(
        s["config"].get("sets", 0) * s["frequency_per_week"]
        for s in selected
        if isinstance(s["config"].get("sets"), int)
    )
    total_reps = sum(
        s["config"].get("sets", 0) * s["config"].get("reps", 0) * s["frequency_per_week"]
        for s in selected
        if isinstance(s["config"].get("sets"), int) and isinstance(s["config"].get("reps"), int)
    )

    notes = [
        f"Goal: {goal} | Dataset: {dataset.DATASET_VERSION} | Preset: {preset}",
        f"Slots allocated: {slot_count}/{n}",
    ]
    if excluded:
        notes.append(f"Excluded exercises: {', '.join(excluded)}")
    if focus != "all":
        notes.append(f"Focus: {focus} body only")

    return OptimizerResult(
        goal=goal,
        n_slots=n,
        selected_exercises=selected,
        weekly_volume={"estimated_sets": total_sets, "estimated_reps": total_reps},
        notes=notes,
    )
