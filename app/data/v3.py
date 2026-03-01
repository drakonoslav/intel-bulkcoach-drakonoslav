"""
Dataset v3 — Wave Loading / Undulating Intensity.
Adds week-by-week wave patterns on top of v2 base.
"""

DATASET_VERSION = "v3"
DATASET_NAME = "Wave Loading Intermediate"
DATASET_DESCRIPTION = (
    "Intermediate dataset: 3-week intensity waves with volume accumulation "
    "and planned deload. Suited for lifters past linear plateau."
)

INTENSITY_TABLE = {
    1:  {"pct_1rm": 100, "rpe": 10.0},
    2:  {"pct_1rm": 97,  "rpe": 9.5},
    3:  {"pct_1rm": 94,  "rpe": 9.0},
    4:  {"pct_1rm": 91,  "rpe": 8.5},
    5:  {"pct_1rm": 88,  "rpe": 8.0},
    6:  {"pct_1rm": 85,  "rpe": 7.5},
    7:  {"pct_1rm": 82,  "rpe": 7.0},
    8:  {"pct_1rm": 79,  "rpe": 6.5},
    9:  {"pct_1rm": 76,  "rpe": 6.0},
    10: {"pct_1rm": 73,  "rpe": 5.5},
    12: {"pct_1rm": 68,  "rpe": 5.0},
    15: {"pct_1rm": 63,  "rpe": 4.5},
    20: {"pct_1rm": 58,  "rpe": 4.0},
}

WAVE_PATTERN = {
    "week_1": {"label": "Accumulation", "volume_multiplier": 1.0, "intensity_offset": 0},
    "week_2": {"label": "Intensification", "volume_multiplier": 0.9, "intensity_offset": 3},
    "week_3": {"label": "Peak", "volume_multiplier": 0.8, "intensity_offset": 5},
    "week_4": {"label": "Deload", "volume_multiplier": 0.6, "intensity_offset": -5},
}

EXERCISE_DEFAULTS = {
    "squat": {
        "strength": {"sets": 5, "reps": [5, 4, 3], "pct_1rm": [80, 83, 87], "frequency": 3},
        "hypertrophy": {"sets": 4, "reps": [10, 8, 6], "pct_1rm": [68, 73, 78], "frequency": 2},
        "injury": {"sets": 3, "reps": [12, 10, 8], "pct_1rm": [58, 63, 68], "frequency": 2},
    },
    "deadlift": {
        "strength": {"sets": 4, "reps": [4, 3, 2], "pct_1rm": [83, 88, 93], "frequency": 2},
        "hypertrophy": {"sets": 3, "reps": [8, 6, 4], "pct_1rm": [70, 76, 82], "frequency": 2},
        "injury": {"sets": 3, "reps": [10, 8, 6], "pct_1rm": [58, 63, 68], "frequency": 1},
    },
    "bench_press": {
        "strength": {"sets": 5, "reps": [5, 4, 3], "pct_1rm": [80, 83, 87], "frequency": 3},
        "hypertrophy": {"sets": 4, "reps": [12, 10, 8], "pct_1rm": [63, 68, 73], "frequency": 3},
        "injury": {"sets": 3, "reps": [15, 12, 10], "pct_1rm": [53, 58, 63], "frequency": 2},
    },
    "overhead_press": {
        "strength": {"sets": 5, "reps": [5, 4, 3], "pct_1rm": [80, 83, 87], "frequency": 2},
        "hypertrophy": {"sets": 4, "reps": [10, 8, 6], "pct_1rm": [65, 70, 76], "frequency": 2},
        "injury": {"sets": 3, "reps": [12, 10, 8], "pct_1rm": [53, 58, 63], "frequency": 2},
    },
    "row": {
        "strength": {"sets": 4, "reps": [6, 5, 4], "pct_1rm": [76, 80, 84], "frequency": 3},
        "hypertrophy": {"sets": 4, "reps": [12, 10, 8], "pct_1rm": [63, 68, 73], "frequency": 3},
        "injury": {"sets": 3, "reps": [15, 12, 10], "pct_1rm": [53, 58, 63], "frequency": 2},
    },
}

def get_matrix(exercise: str = None):
    if exercise:
        ex = exercise.lower().replace(" ", "_")
        return {
            "version": DATASET_VERSION,
            "exercise": ex,
            "intensity_table": INTENSITY_TABLE,
            "wave_pattern": WAVE_PATTERN,
            "exercise_defaults": EXERCISE_DEFAULTS.get(ex),
        }
    return {
        "version": DATASET_VERSION,
        "name": DATASET_NAME,
        "description": DATASET_DESCRIPTION,
        "intensity_table": INTENSITY_TABLE,
        "wave_pattern": WAVE_PATTERN,
        "exercise_defaults": EXERCISE_DEFAULTS,
    }
