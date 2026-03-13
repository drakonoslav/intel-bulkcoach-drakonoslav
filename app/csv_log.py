"""
Append every daily log submission to data/daily_log.csv.
File persists across restarts — never lost.
"""
import csv
import os
import datetime
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "daily_log.csv"

COLUMNS = [
    "logged_at",
    "expo_user_id",
    "date",
    # sleep
    "sleep_onset_hhmm",
    "sleep_wake_hhmm",
    "sleep_duration_min",
    "sleep_rem_min",
    "sleep_core_min",
    "sleep_deep_min",
    "sleep_awake_min",
    "sleep_efficiency_pct",
    # biometrics
    "hrv_ms",
    "resting_hr_bpm",
    "morning_temp_f",
    "morning_temp_c",
    # weight / body comp
    "body_weight_lb",
    "body_fat_pct",
    "skeletal_muscle_pct",
    "fat_mass_lb",
    "fat_free_mass_lb",
    "skeletal_muscle_lb",
    "waist_at_navel_in",
    # subjective
    "libido_score",
    "morning_erection_score",
    "mood_stability_score",
    "mental_drive_score",
    "soreness_score",
    "joint_friction_score",
    "stress_load_score",
    "motivation_score",
    # activity
    "resting_hr_bpm",
    "step_count",
    "active_energy_kcal",
    "exercise_min",
    "cardio_duration_min",
    "cardio_avg_hr_bpm",
    # nutrition (actual)
    "kcal_actual",
    "protein_g_actual",
    "carbs_g_actual",
    "fat_g_actual",
    # nutrition (targets)
    "kcal_target",
    "protein_g_target",
    "carbs_g_target",
    "fat_g_target",
]

# dedupe (resting_hr_bpm appears twice in list above by mistake)
COLUMNS = list(dict.fromkeys(COLUMNS))


def append_log(row: dict) -> None:
    """Append a single log row to the CSV.  Creates the file + header if needed."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_file = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0

    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        row["logged_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        writer.writerow(row)
