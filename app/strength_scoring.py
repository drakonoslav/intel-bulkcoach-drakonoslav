"""
Exercise-weighted strength scoring engine.

Computes session strength output index from individual exercise entries,
weighted by neural demand, hypertrophy stimulus, and compound status.
"""
from typing import List, Optional
from dataclasses import dataclass


# ── DEFAULT EXERCISE WEIGHTS (fallback when exercise not in ExerciseMaster) ───
_DEFAULT_NEURAL_DEMAND = 0.50
_DEFAULT_HYPERTROPHY_STIMULUS = 0.50
_DEFAULT_COMPOUND = True


@dataclass
class ExerciseContribution:
    exercise_name: str
    movement_pattern: Optional[str]
    top_set_e1rm_lbs: Optional[float]
    volume_load_lbs: Optional[float]
    neural_demand: float
    hypertrophy_stimulus: float
    compound: bool
    weighted_strength_index: float


def _epley_e1rm(load_lbs: float, reps: int) -> float:
    """Epley formula: E1RM = load * (1 + reps/30)"""
    if reps <= 0:
        return 0.0
    return load_lbs * (1 + reps / 30.0)


def compute_exercise_strength_index(
    load_lbs: float,
    sets: int,
    reps: int,
    rpe: Optional[float] = None,
    neural_demand: float = _DEFAULT_NEURAL_DEMAND,
    hypertrophy_stimulus: float = _DEFAULT_HYPERTROPHY_STIMULUS,
    compound: bool = True,
) -> float:
    """
    ExerciseStrengthIndex = E1RM * VolumeLoad_normalized
                          * NeuralDemand
                          * HypertrophyStimulus
                          * CompoundMultiplier

    E1RM: Epley estimated 1-rep max
    VolumeLoad: sets * reps * load_lbs
    NeuralDemand: 0.0–1.0 from ExerciseMaster (default 0.50)
    CompoundMultiplier: 1.15 for compound, 1.0 for isolation
    RPE adjustment: if rpe >= 8.5, boost by 1.05
    """
    if load_lbs <= 0 or sets <= 0 or reps <= 0:
        return 0.0

    e1rm = _epley_e1rm(load_lbs, reps)
    volume_load = sets * reps * load_lbs
    volume_load_normalized = volume_load / 1000.0  # normalize to per-1000lb-load

    compound_multiplier = 1.15 if compound else 1.0
    rpe_boost = 1.05 if (rpe is not None and rpe >= 8.5) else 1.0

    index = (
        e1rm
        * volume_load_normalized
        * neural_demand
        * hypertrophy_stimulus
        * compound_multiplier
        * rpe_boost
    )
    return round(index, 2)


def compute_session_strength_index(
    exercise_entries: list,
    fallback_strength_output_index: Optional[float] = None,
) -> dict:
    """
    Aggregates exercise-level strength indices into a session-level summary.

    exercise_entries: list of dicts with keys:
        exercise_name, load_lbs, sets, reps, rpe (optional),
        neural_demand (optional), hypertrophy_stimulus (optional), compound (optional),
        movement_pattern (optional)

    Returns:
        sessionStrengthOutputIndex: weighted sum
        primaryCompoundIndex: sum from compound exercises only
        accessoryIndex: sum from isolation/accessory exercises
        topExerciseContributors: ranked list of top 5 exercises by contribution
    """
    if not exercise_entries and fallback_strength_output_index is not None:
        return {
            "sessionStrengthOutputIndex": fallback_strength_output_index,
            "primaryCompoundIndex": None,
            "accessoryIndex": None,
            "topExerciseContributors": [],
            "source": "daily_log_fallback",
        }

    contributions: List[ExerciseContribution] = []

    for e in exercise_entries:
        load = float(e.get("load_lbs") or e.get("load_kg", 0) * 2.205 or 0)
        sets = int(e.get("sets_completed") or 0)
        reps = int(e.get("reps_per_set") or 0)
        rpe = float(e.get("rpe")) if e.get("rpe") is not None else None
        nd = float(e.get("neural_demand") or _DEFAULT_NEURAL_DEMAND)
        hs = float(e.get("hypertrophy_stimulus") or _DEFAULT_HYPERTROPHY_STIMULUS)
        compound = bool(e.get("compound", _DEFAULT_COMPOUND))
        name = e.get("exercise_name_raw") or e.get("exercise_name") or "Unknown"
        movement_pattern = e.get("movement_pattern")

        if load <= 0 or sets <= 0 or reps <= 0:
            continue

        e1rm = _epley_e1rm(load, reps)
        idx = compute_exercise_strength_index(load, sets, reps, rpe, nd, hs, compound)

        contributions.append(ExerciseContribution(
            exercise_name=name,
            movement_pattern=movement_pattern,
            top_set_e1rm_lbs=round(e1rm, 1),
            volume_load_lbs=round(sets * reps * load, 1),
            neural_demand=nd,
            hypertrophy_stimulus=hs,
            compound=compound,
            weighted_strength_index=idx,
        ))

    if not contributions:
        return {
            "sessionStrengthOutputIndex": fallback_strength_output_index or 0.0,
            "primaryCompoundIndex": None,
            "accessoryIndex": None,
            "topExerciseContributors": [],
            "source": "no_exercise_data",
        }

    session_index = round(sum(c.weighted_strength_index for c in contributions), 2)
    compound_index = round(sum(c.weighted_strength_index for c in contributions if c.compound), 2)
    accessory_index = round(sum(c.weighted_strength_index for c in contributions if not c.compound), 2)

    ranked = sorted(contributions, key=lambda c: c.weighted_strength_index, reverse=True)[:5]

    return {
        "sessionStrengthOutputIndex": session_index,
        "primaryCompoundIndex": compound_index,
        "accessoryIndex": accessory_index,
        "topExerciseContributors": [
            {
                "exerciseName": c.exercise_name,
                "movementPattern": c.movement_pattern,
                "topSetE1rmLbs": c.top_set_e1rm_lbs,
                "volumeLoadLbs": c.volume_load_lbs,
                "weightedStrengthIndex": c.weighted_strength_index,
            }
            for c in ranked
        ],
        "source": "exercise_entries",
    }
