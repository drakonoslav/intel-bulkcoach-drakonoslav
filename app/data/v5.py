"""
Dataset v5 — Conjugate / Concurrent Method.
Max effort + dynamic effort days; bands/chains optional.
"""

DATASET_VERSION = "v5"
DATASET_NAME = "Conjugate / Concurrent Method"
DATASET_DESCRIPTION = (
    "Elite dataset: Conjugate method with Max Effort and Dynamic Effort days. "
    "Concurrent development of multiple strength qualities. "
    "Includes accommodating resistance recommendations."
)

INTENSITY_TABLE = {
    1:  {"pct_1rm": 100, "rpe": 10.0, "effort_type": "ME"},
    2:  {"pct_1rm": 97,  "rpe": 9.5,  "effort_type": "ME"},
    3:  {"pct_1rm": 94,  "rpe": 9.0,  "effort_type": "ME"},
    4:  {"pct_1rm": 91,  "rpe": 8.5,  "effort_type": "ME"},
    5:  {"pct_1rm": 87,  "rpe": 8.0,  "effort_type": "ME"},
    6:  {"pct_1rm": 83,  "rpe": 7.5,  "effort_type": "ME/DE"},
    7:  {"pct_1rm": 80,  "rpe": 7.0,  "effort_type": "ME/DE"},
    8:  {"pct_1rm": 76,  "rpe": 6.5,  "effort_type": "DE"},
    9:  {"pct_1rm": 72,  "rpe": 6.0,  "effort_type": "DE"},
    10: {"pct_1rm": 68,  "rpe": 5.5,  "effort_type": "DE"},
    12: {"pct_1rm": 63,  "rpe": 5.0,  "effort_type": "DE/Hyp"},
    15: {"pct_1rm": 58,  "rpe": 4.5,  "effort_type": "Hyp"},
    20: {"pct_1rm": 53,  "rpe": 4.0,  "effort_type": "Hyp"},
}

DE_PROTOCOL = {
    "squat":        {"sets": 10, "reps": 2, "pct_1rm": 55, "bar_weight_pct": 55, "band_tension_pct": 25},
    "deadlift":     {"sets": 10, "reps": 1, "pct_1rm": 60, "bar_weight_pct": 60, "band_tension_pct": 20},
    "bench_press":  {"sets": 9,  "reps": 3, "pct_1rm": 50, "bar_weight_pct": 50, "band_tension_pct": 25},
}

ME_VARIATIONS = {
    "squat": ["box squat", "safety bar squat", "front squat", "pause squat", "belt squat"],
    "deadlift": ["sumo deadlift", "trap bar deadlift", "deficit deadlift", "rack pull", "Romanian deadlift"],
    "bench_press": ["floor press", "board press", "close grip bench", "incline press", "reverse band bench"],
}

EXERCISE_DEFAULTS = {
    "squat": {
        "strength": {"me_sets": 1, "me_reps": 1, "me_pct": 100, "de_sets": 10, "de_reps": 2, "de_pct": 55},
        "hypertrophy": {"sets": 5, "reps": 8, "pct_1rm": 73, "frequency": 2},
        "injury": {"sets": 3, "reps": 10, "pct_1rm": 60, "frequency": 2},
    },
    "deadlift": {
        "strength": {"me_sets": 1, "me_reps": 1, "me_pct": 100, "de_sets": 10, "de_reps": 1, "de_pct": 60},
        "hypertrophy": {"sets": 4, "reps": 8, "pct_1rm": 70, "frequency": 2},
        "injury": {"sets": 3, "reps": 8, "pct_1rm": 58, "frequency": 1},
    },
    "bench_press": {
        "strength": {"me_sets": 1, "me_reps": 1, "me_pct": 100, "de_sets": 9, "de_reps": 3, "de_pct": 50},
        "hypertrophy": {"sets": 5, "reps": 10, "pct_1rm": 67, "frequency": 3},
        "injury": {"sets": 3, "reps": 12, "pct_1rm": 55, "frequency": 2},
    },
    "overhead_press": {
        "strength": {"sets": 5, "reps": 3, "pct_1rm": 85, "frequency": 2},
        "hypertrophy": {"sets": 4, "reps": 10, "pct_1rm": 65, "frequency": 2},
        "injury": {"sets": 3, "reps": 12, "pct_1rm": 53, "frequency": 2},
    },
    "row": {
        "strength": {"sets": 4, "reps": 6, "pct_1rm": 78, "frequency": 3},
        "hypertrophy": {"sets": 5, "reps": 10, "pct_1rm": 65, "frequency": 3},
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
            "de_protocol": DE_PROTOCOL.get(ex),
            "me_variations": ME_VARIATIONS.get(ex),
            "exercise_defaults": EXERCISE_DEFAULTS.get(ex),
        }
    return {
        "version": DATASET_VERSION,
        "name": DATASET_NAME,
        "description": DATASET_DESCRIPTION,
        "intensity_table": INTENSITY_TABLE,
        "de_protocol": DE_PROTOCOL,
        "me_variations": ME_VARIATIONS,
        "exercise_defaults": EXERCISE_DEFAULTS,
    }
