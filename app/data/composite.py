"""
Dataset composite — Weighted blend across v2–v5.
Averages intensity tables and merges exercise defaults from all versions.
"""

from app.data import v2, v3, v4, v5

DATASET_VERSION = "composite"
DATASET_NAME = "Composite Blended Dataset"
DATASET_DESCRIPTION = (
    "Composite dataset: weighted average of v2–v5 intensity tables. "
    "Provides a balanced middle-ground prescription usable across experience levels."
)

_VERSIONS = [v2, v3, v4, v5]
_WEIGHTS = [1, 1, 1, 1]


def _blend_intensity_table():
    rep_keys = set()
    for v in _VERSIONS:
        rep_keys |= set(v.INTENSITY_TABLE.keys())
    blended = {}
    for reps in sorted(rep_keys):
        total_pct = 0
        total_rpe = 0
        count = 0
        for v, w in zip(_VERSIONS, _WEIGHTS):
            if reps in v.INTENSITY_TABLE:
                total_pct += v.INTENSITY_TABLE[reps]["pct_1rm"] * w
                total_rpe += v.INTENSITY_TABLE[reps]["rpe"] * w
                count += w
        blended[reps] = {
            "pct_1rm": round(total_pct / count, 1),
            "rpe": round(total_rpe / count, 1),
        }
    return blended


def _merge_exercise_defaults():
    all_exercises = set()
    for v in _VERSIONS:
        all_exercises |= set(v.EXERCISE_DEFAULTS.keys())
    merged = {}
    for ex in all_exercises:
        merged[ex] = {"sources": {}}
        for v in _VERSIONS:
            if ex in v.EXERCISE_DEFAULTS:
                merged[ex]["sources"][v.DATASET_VERSION] = v.EXERCISE_DEFAULTS[ex]
    return merged


INTENSITY_TABLE = _blend_intensity_table()
EXERCISE_DEFAULTS = _merge_exercise_defaults()


def get_matrix(exercise: str = None):
    if exercise:
        ex = exercise.lower().replace(" ", "_")
        return {
            "version": DATASET_VERSION,
            "exercise": ex,
            "intensity_table": INTENSITY_TABLE,
            "exercise_defaults": EXERCISE_DEFAULTS.get(ex),
        }
    return {
        "version": DATASET_VERSION,
        "name": DATASET_NAME,
        "description": DATASET_DESCRIPTION,
        "intensity_table": INTENSITY_TABLE,
        "exercise_defaults": EXERCISE_DEFAULTS,
    }
