"""
Dataset v2 — Linear Progression baseline.
Rep-max intensity table + exercise programming defaults.
"""

DATASET_VERSION = "v2"
DATASET_NAME = "Linear Progression Baseline"
DATASET_DESCRIPTION = (
    "Foundation dataset: standard percentage-of-1RM intensity table "
    "and default set/rep schemes for linear progression."
)

INTENSITY_TABLE = {
    1:  {"pct_1rm": 100, "rpe": 10.0},
    2:  {"pct_1rm": 95,  "rpe": 9.5},
    3:  {"pct_1rm": 93,  "rpe": 9.0},
    4:  {"pct_1rm": 90,  "rpe": 8.5},
    5:  {"pct_1rm": 87,  "rpe": 8.0},
    6:  {"pct_1rm": 85,  "rpe": 7.5},
    7:  {"pct_1rm": 83,  "rpe": 7.0},
    8:  {"pct_1rm": 80,  "rpe": 6.5},
    9:  {"pct_1rm": 77,  "rpe": 6.0},
    10: {"pct_1rm": 75,  "rpe": 5.5},
    12: {"pct_1rm": 70,  "rpe": 5.0},
    15: {"pct_1rm": 65,  "rpe": 4.5},
    20: {"pct_1rm": 60,  "rpe": 4.0},
}

EXERCISE_DEFAULTS = {
    "squat": {
        "strength": {"sets": 5, "reps": 5, "pct_1rm": 80, "frequency": 3},
        "hypertrophy": {"sets": 4, "reps": 8, "pct_1rm": 70, "frequency": 2},
        "injury": {"sets": 3, "reps": 10, "pct_1rm": 60, "frequency": 2},
    },
    "deadlift": {
        "strength": {"sets": 4, "reps": 4, "pct_1rm": 85, "frequency": 2},
        "hypertrophy": {"sets": 3, "reps": 8, "pct_1rm": 70, "frequency": 2},
        "injury": {"sets": 3, "reps": 8, "pct_1rm": 55, "frequency": 1},
    },
    "bench_press": {
        "strength": {"sets": 5, "reps": 5, "pct_1rm": 80, "frequency": 3},
        "hypertrophy": {"sets": 4, "reps": 10, "pct_1rm": 67, "frequency": 3},
        "injury": {"sets": 3, "reps": 12, "pct_1rm": 55, "frequency": 2},
    },
    "overhead_press": {
        "strength": {"sets": 5, "reps": 5, "pct_1rm": 80, "frequency": 2},
        "hypertrophy": {"sets": 4, "reps": 10, "pct_1rm": 65, "frequency": 2},
        "injury": {"sets": 3, "reps": 12, "pct_1rm": 50, "frequency": 2},
    },
    "row": {
        "strength": {"sets": 4, "reps": 6, "pct_1rm": 78, "frequency": 3},
        "hypertrophy": {"sets": 4, "reps": 10, "pct_1rm": 65, "frequency": 3},
        "injury": {"sets": 3, "reps": 12, "pct_1rm": 55, "frequency": 2},
    },
}

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
