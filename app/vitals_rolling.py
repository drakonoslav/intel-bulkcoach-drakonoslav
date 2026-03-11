from datetime import date, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text


def _linear_slope(pairs):
    n = len(pairs)
    if n < 2:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return None
    return num / den


def _rows_for_range(db: Session, expo_user_id: str, from_date: date, to_date: date):
    result = db.execute(text("""
        SELECT date, hrv_ms, resting_hr_bpm, sleep_duration_min, sleep_midpoint_min,
               body_weight_lb, fat_free_mass_lb, waist_at_navel_in,
               kcal_actual, protein_g_actual, carbs_g_actual, fat_g_actual,
               actual_cardio_mode, completed_lift_mode, recommended_macro_day,
               strength_output_index, libido_score, motivation_score, mood_stability_score,
               morning_erection_score
        FROM vitals_daily_log
        WHERE expo_user_id = :uid AND date >= :from_d AND date <= :to_d
        ORDER BY date ASC
    """), {"uid": expo_user_id, "from_d": from_date, "to_d": to_date})
    return result.mappings().all()


def compute_rolling_references(db: Session, expo_user_id: str, target_date: date) -> dict:
    today = target_date
    d7_start = today - timedelta(days=7)
    d14_start = today - timedelta(days=14)
    d28_start = today - timedelta(days=28)
    d56_start = today - timedelta(days=56)

    rows_7d = _rows_for_range(db, expo_user_id, d7_start, today - timedelta(days=1))
    rows_14d = _rows_for_range(db, expo_user_id, d14_start, today - timedelta(days=1))
    rows_28d = _rows_for_range(db, expo_user_id, d28_start, today - timedelta(days=1))
    rows_prev28d = _rows_for_range(db, expo_user_id, d56_start, d28_start - timedelta(days=1))

    def avg_field(rows, field):
        vals = [float(r[field]) for r in rows if r[field] is not None]
        return sum(vals) / len(vals) if vals else None

    def trend_lb_per_week(rows, field):
        pairs = []
        for i, r in enumerate(rows):
            if r[field] is not None:
                pairs.append((i, float(r[field])))
        slope = _linear_slope(pairs)
        return slope * 7 if slope is not None else None

    def trend_pct_change(rows, field):
        pairs = []
        for i, r in enumerate(rows):
            if r[field] is not None:
                pairs.append((i, float(r[field])))
        if len(pairs) < 2:
            return None
        half = len(pairs) // 2
        first_avg = sum(p[1] for p in pairs[:half]) / half if half else None
        second_avg = sum(p[1] for p in pairs[half:]) / (len(pairs) - half) if (len(pairs) - half) else None
        if first_avg and second_avg and first_avg != 0:
            return ((second_avg - first_avg) / first_avg) * 100
        return None

    hrv_7d = avg_field(rows_7d, "hrv_ms")
    rhr_7d = avg_field(rows_7d, "resting_hr_bpm")
    sleep_7d = avg_field(rows_7d, "sleep_duration_min")
    midpoint_7d = avg_field(rows_7d, "sleep_midpoint_min")
    weight_7d = avg_field(rows_7d, "body_weight_lb")
    kcal_7d = avg_field(rows_7d, "kcal_actual")
    protein_7d = avg_field(rows_7d, "protein_g_actual")
    carbs_7d = avg_field(rows_7d, "carbs_g_actual")
    fat_7d = avg_field(rows_7d, "fat_g_actual")

    weight_trend_14d = trend_lb_per_week(rows_14d, "body_weight_lb")
    ffm_trend_14d = trend_lb_per_week(rows_14d, "fat_free_mass_lb")
    strength_trend_14d = trend_pct_change(rows_14d, "strength_output_index")

    waist_14d_first = avg_field(rows_14d[:7], "waist_at_navel_in") if len(rows_14d) >= 7 else None
    waist_14d_last = avg_field(rows_14d[7:], "waist_at_navel_in") if len(rows_14d) >= 7 else None
    waist_change_14d = (float(waist_14d_last) - float(waist_14d_first)) if (waist_14d_first and waist_14d_last) else None

    hrv_28d = avg_field(rows_28d, "hrv_ms")
    rhr_28d = avg_field(rows_28d, "resting_hr_bpm")
    hrv_prev28d = avg_field(rows_prev28d, "hrv_ms")
    rhr_prev28d = avg_field(rows_prev28d, "resting_hr_bpm")

    ffm_28d = avg_field(rows_28d, "fat_free_mass_lb")
    ffm_prev28d = avg_field(rows_prev28d, "fat_free_mass_lb")

    weight_28d_first = avg_field(rows_28d[:14], "body_weight_lb")
    weight_28d_last = avg_field(rows_28d[14:], "body_weight_lb")
    weight_28d_change = (float(weight_28d_last) - float(weight_28d_first)) if (weight_28d_first and weight_28d_last) else None

    waist_28d_first = avg_field(rows_28d[:14], "waist_at_navel_in")
    waist_28d_last = avg_field(rows_28d[14:], "waist_at_navel_in")
    waist_28d_change = (float(waist_28d_last) - float(waist_28d_first)) if (waist_28d_first and waist_28d_last) else None

    def sleep_regularity_score(rows):
        midpoints = [float(r["sleep_midpoint_min"]) for r in rows if r["sleep_midpoint_min"] is not None]
        if len(midpoints) < 3:
            return None
        mean_mid = sum(midpoints) / len(midpoints)
        avg_dev = sum(abs(m - mean_mid) for m in midpoints) / len(midpoints)
        return max(0, 100 - (avg_dev / 90) * 100)

    sleep_reg_28d = sleep_regularity_score(rows_28d)
    sleep_reg_prev28d = sleep_regularity_score(rows_prev28d)

    zone2_7d = sum(1 for r in rows_7d if r["actual_cardio_mode"] == "zone_2")
    zone3_7d = sum(1 for r in rows_7d if r["actual_cardio_mode"] == "zone_3")
    recovery_7d = sum(1 for r in rows_7d if r["actual_cardio_mode"] == "recovery_walk")
    neural_7d = sum(1 for r in rows_7d if r["completed_lift_mode"] == "neural_tension")

    reset_count_28d = sum(1 for r in rows_28d if r["recommended_macro_day"] in ("reset", "resensitize"))
    deload_28d = reset_count_28d >= 4

    all_modes_28d = [r["actual_cardio_mode"] for r in rows_28d if r["actual_cardio_mode"]]
    all_lift_28d = [r["completed_lift_mode"] for r in rows_28d if r["completed_lift_mode"]]
    all_macro_28d = [r["recommended_macro_day"] for r in rows_28d if r["recommended_macro_day"]]
    all_types = all_modes_28d + all_lift_28d + all_macro_28d
    if all_types:
        from collections import Counter
        counts = Counter(all_types)
        most_common_pct = counts.most_common(1)[0][1] / len(all_types) * 100
        monotony_index = most_common_pct
    else:
        monotony_index = None

    virility_fields_28d = []
    for r in rows_28d:
        vals = [r["libido_score"], r["motivation_score"], r["mood_stability_score"]]
        valid = [float(v) for v in vals if v is not None]
        if valid:
            virility_fields_28d.append(sum(valid) / len(valid))
    virility_trend_28d = (sum(virility_fields_28d) / len(virility_fields_28d) / 5 * 100) if virility_fields_28d else None

    recent_macro_types_7d = [r["recommended_macro_day"] for r in rows_7d if r["recommended_macro_day"]]

    return {
        "hrv7dAvg": hrv_7d,
        "rhr7dAvg": rhr_7d,
        "sleepDuration7dAvg": sleep_7d,
        "sleepMidpoint7dAvg": midpoint_7d,
        "bodyWeight7dAvg": weight_7d,
        "kcal7dAvg": kcal_7d,
        "protein7dAvg": protein_7d,
        "carbs7dAvg": carbs_7d,
        "fat7dAvg": fat_7d,
        "weightTrend14dLbPerWeek": weight_trend_14d,
        "ffmTrend14dLbPerWeek": ffm_trend_14d,
        "waistChange14dIn": waist_change_14d,
        "strengthTrend14dPct": strength_trend_14d,
        "hrv28dAvg": hrv_28d,
        "hrvPrev28dAvg": hrv_prev28d,
        "rhr28dAvg": rhr_28d,
        "rhrPrev28dAvg": rhr_prev28d,
        "sleepRegularity28dScore": sleep_reg_28d,
        "sleepRegularityPrev28dScore": sleep_reg_prev28d,
        "ffm28dAvg": ffm_28d,
        "ffmPrev28dAvg": ffm_prev28d,
        "weight28dChangeLb": weight_28d_change,
        "waist28dChangeIn": waist_28d_change,
        "cardioZone2Count7d": zone2_7d,
        "cardioZone3Count7d": zone3_7d,
        "cardioRecoveryCount7d": recovery_7d,
        "neuralLiftCount7d": neural_7d,
        "resetOrResensitizeDayCount28d": reset_count_28d,
        "deloadCompliance28d": deload_28d,
        "trainingMonotonyIndex28d": monotony_index,
        "lightExposureConsistency28d": None,
        "virilityTrend28d": virility_trend_28d,
        "recentMacroDayTypes7d": recent_macro_types_7d,
    }
