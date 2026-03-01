"""
Dataset v4 — Block Periodization (Accumulation → Transmutation → Realization).
Advanced dataset for structured block training.
"""

DATASET_VERSION = "v4"
DATASET_NAME = "Block Periodization Advanced"
DATASET_DESCRIPTION = (
    "Advanced dataset: 3-phase block periodization model. "
    "Accumulation builds volume, Transmutation converts to strength, "
    "Realization peaks for competition or testing."
)

INTENSITY_TABLE = {
    1:  {"pct_1rm": 100, "rpe": 10.0, "prilepin_zone": "max"},
    2:  {"pct_1rm": 97,  "rpe": 9.5,  "prilepin_zone": "near_max"},
    3:  {"pct_1rm": 94,  "rpe": 9.0,  "prilepin_zone": "near_max"},
    4:  {"pct_1rm": 90,  "rpe": 8.5,  "prilepin_zone": "heavy"},
    5:  {"pct_1rm": 87,  "rpe": 8.0,  "prilepin_zone": "heavy"},
    6:  {"pct_1rm": 83,  "rpe": 7.5,  "prilepin_zone": "heavy"},
    7:  {"pct_1rm": 80,  "rpe": 7.0,  "prilepin_zone": "medium"},
    8:  {"pct_1rm": 77,  "rpe": 6.5,  "prilepin_zone": "medium"},
    9:  {"pct_1rm": 74,  "rpe": 6.0,  "prilepin_zone": "medium"},
    10: {"pct_1rm": 71,  "rpe": 5.5,  "prilepin_zone": "light"},
    12: {"pct_1rm": 67,  "rpe": 5.0,  "prilepin_zone": "light"},
    15: {"pct_1rm": 62,  "rpe": 4.5,  "prilepin_zone": "light"},
    20: {"pct_1rm": 57,  "rpe": 4.0,  "prilepin_zone": "light"},
}

PRILEPIN_TABLE = {
    "55-65":  {"optimal_reps": 24, "range": (18, 30), "intensity_pct": (55, 65)},
    "70-75":  {"optimal_reps": 18, "range": (12, 24), "intensity_pct": (70, 75)},
    "80-85":  {"optimal_reps": 15, "range": (10, 20), "intensity_pct": (80, 85)},
    "90+":    {"optimal_reps": 4,  "range": (1, 10),  "intensity_pct": (90, 100)},
}

BLOCKS = {
    "accumulation": {
        "duration_weeks": 4,
        "primary_quality": "volume",
        "intensity_pct": (65, 80),
        "reps_per_set": (8, 12),
        "sets_per_exercise": (4, 6),
    },
    "transmutation": {
        "duration_weeks": 3,
        "primary_quality": "strength-endurance",
        "intensity_pct": (80, 90),
        "reps_per_set": (4, 6),
        "sets_per_exercise": (4, 5),
    },
    "realization": {
        "duration_weeks": 2,
        "primary_quality": "max_strength",
        "intensity_pct": (90, 100),
        "reps_per_set": (1, 3),
        "sets_per_exercise": (3, 5),
    },
}

EXERCISE_DEFAULTS = {
    "squat": {
        "accumulation": {"sets": 5, "reps": 10, "pct_1rm": 70, "frequency": 3},
        "transmutation": {"sets": 5, "reps": 5, "pct_1rm": 83, "frequency": 3},
        "realization": {"sets": 4, "reps": 2, "pct_1rm": 93, "frequency": 2},
    },
    "deadlift": {
        "accumulation": {"sets": 4, "reps": 8, "pct_1rm": 70, "frequency": 2},
        "transmutation": {"sets": 4, "reps": 4, "pct_1rm": 85, "frequency": 2},
        "realization": {"sets": 3, "reps": 2, "pct_1rm": 93, "frequency": 1},
    },
    "bench_press": {
        "accumulation": {"sets": 5, "reps": 10, "pct_1rm": 67, "frequency": 3},
        "transmutation": {"sets": 5, "reps": 5, "pct_1rm": 80, "frequency": 3},
        "realization": {"sets": 4, "reps": 2, "pct_1rm": 91, "frequency": 2},
    },
    "overhead_press": {
        "accumulation": {"sets": 4, "reps": 10, "pct_1rm": 65, "frequency": 2},
        "transmutation": {"sets": 4, "reps": 5, "pct_1rm": 78, "frequency": 2},
        "realization": {"sets": 3, "reps": 2, "pct_1rm": 90, "frequency": 2},
    },
    "row": {
        "accumulation": {"sets": 5, "reps": 10, "pct_1rm": 65, "frequency": 3},
        "transmutation": {"sets": 4, "reps": 6, "pct_1rm": 78, "frequency": 3},
        "realization": {"sets": 3, "reps": 3, "pct_1rm": 88, "frequency": 2},
    },
}

def get_matrix(exercise: str = None):
    if exercise:
        ex = exercise.lower().replace(" ", "_")
        return {
            "version": DATASET_VERSION,
            "exercise": ex,
            "intensity_table": INTENSITY_TABLE,
            "prilepin_table": PRILEPIN_TABLE,
            "blocks": BLOCKS,
            "exercise_defaults": EXERCISE_DEFAULTS.get(ex),
        }
    return {
        "version": DATASET_VERSION,
        "name": DATASET_NAME,
        "description": DATASET_DESCRIPTION,
        "intensity_table": INTENSITY_TABLE,
        "prilepin_table": PRILEPIN_TABLE,
        "blocks": BLOCKS,
        "exercise_defaults": EXERCISE_DEFAULTS,
    }
