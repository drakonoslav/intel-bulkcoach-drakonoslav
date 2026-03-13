"""
Persist every daily log to data/daily_log.csv.
Upserts by (expo_user_id, date) — re-submitting a date replaces that row.
File survives restarts, crashes, redeployments.
"""
import csv
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
    # circumference measurements (inches, decimal)
    "neck_in",
    "chest_in",
    "hip_in",
    "bicep_l_in",
    "bicep_r_in",
    "forearm_l_in",
    "forearm_r_in",
    "thigh_l_in",
    "thigh_r_in",
    "calf_l_in",
    "calf_r_in",
    "ankle_l_in",
    "ankle_r_in",
    "wrist_l_in",
    "wrist_r_in",
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
    "step_count",
    "active_energy_kcal",
    "exercise_min",
    "cardio_duration_min",
    "cardio_avg_hr_bpm",
    # nutrition (actual — whole-day totals)
    "kcal_actual",
    "protein_g_actual",
    "carbs_g_actual",
    "fat_g_actual",
    # nutrition (targets)
    "kcal_target",
    "protein_g_target",
    "carbs_g_target",
    "fat_g_target",
    # per-window actuals vs planned (logged separately after eating)
    "meal_actuals_logged_at",
    "day_kcal_planned",
    "day_kcal_actual_windows",
    "day_kcal_delta",
    "day_p_planned",
    "day_p_actual",
    "day_p_delta",
    "day_c_planned",
    "day_c_actual",
    "day_c_delta",
    "day_f_planned",
    "day_f_actual",
    "day_f_delta",
]


def _read_all() -> list[dict]:
    if not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0:
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_all(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_log(row: dict) -> None:
    """Upsert a log row by (expo_user_id, date). Replaces existing row for that date."""
    row = dict(row)
    row["logged_at"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Normalise date to string
    row["date"] = str(row.get("date", ""))

    existing = _read_all()
    uid = row.get("expo_user_id", "")
    dt  = row.get("date", "")

    replaced = False
    updated = []
    for r in existing:
        if r.get("expo_user_id") == uid and r.get("date") == dt:
            updated.append(row)   # replace with new data
            replaced = True
        else:
            updated.append(r)

    if not replaced:
        updated.append(row)

    _write_all(updated)
