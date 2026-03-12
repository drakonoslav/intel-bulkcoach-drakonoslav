from datetime import date, timedelta
from collections import Counter
from sqlalchemy.orm import Session
from app.vitals_models import VitalsDailyLog


DAY_TYPE_CARB_TARGETS = {
    "surge": 390,
    "build": 350,
    "reset": 290,
    "resensitize": 250,
}


def _rows_for_range(db: Session, expo_user_id: str, start: date, end: date):
    rows = (
        db.query(VitalsDailyLog)
        .filter(
            VitalsDailyLog.expo_user_id == expo_user_id,
            VitalsDailyLog.date >= start,
            VitalsDailyLog.date <= end,
        )
        .order_by(VitalsDailyLog.date.asc())
        .all()
    )
    return [
        {c.name: getattr(r, c.name) for c in VitalsDailyLog.__table__.columns}
        for r in rows
    ]


def _linear_slope(pairs):
    if len(pairs) < 2:
        return None
    n = len(pairs)
    sx = sum(p[0] for p in pairs)
    sy = sum(p[1] for p in pairs)
    sxy = sum(p[0] * p[1] for p in pairs)
    sxx = sum(p[0] ** 2 for p in pairs)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    return (n * sxy - sx * sy) / denom


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
        pairs = [(i, float(r[field])) for i, r in enumerate(rows) if r[field] is not None]
        slope = _linear_slope(pairs)
        return slope * 7 if slope is not None else None

    def trend_pct_change(rows, field):
        pairs = [(i, float(r[field])) for i, r in enumerate(rows) if r[field] is not None]
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

    # ── FAT OSCILLATION: actual intake distribution ────────────────────────────
    fat_high_days_7d = sum(1 for r in rows_7d if r["fat_g_actual"] is not None and float(r["fat_g_actual"]) >= 75)
    fat_low_days_7d = sum(1 for r in rows_7d if r["fat_g_actual"] is not None and float(r["fat_g_actual"]) <= 50)
    fat_daily_values_7d = [float(r["fat_g_actual"]) for r in rows_7d if r["fat_g_actual"] is not None]

    # ── CARB DAY-TYPE ADHERENCE: per-day actual vs day-type specific target ────
    carb_day_adherences = []
    for r in rows_7d:
        if r["carbs_g_actual"] is not None and r["recommended_macro_day"] in DAY_TYPE_CARB_TARGETS:
            dt_target = DAY_TYPE_CARB_TARGETS[r["recommended_macro_day"]]
            carb_day_adherences.append(float(r["carbs_g_actual"]) / dt_target)
    carb_day_type_adherence_7d = sum(carb_day_adherences) / len(carb_day_adherences) if carb_day_adherences else None

    # ── 3-CHANNEL MONOTONY (cardio / lift / macro) ─────────────────────────────
    def _dominance_pct(items):
        if not items:
            return None
        counts = Counter(items)
        return counts.most_common(1)[0][1] / len(items) * 100

    cardio_modes_28d = [r["actual_cardio_mode"] for r in rows_28d if r["actual_cardio_mode"]]
    lift_modes_28d = [r["completed_lift_mode"] for r in rows_28d if r["completed_lift_mode"]]
    macro_days_28d = [r["recommended_macro_day"] for r in rows_28d if r["recommended_macro_day"]]

    cardio_monotony = _dominance_pct(cardio_modes_28d)
    lift_monotony = _dominance_pct(lift_modes_28d)
    macro_monotony = _dominance_pct(macro_days_28d)

    if any(v is not None for v in [cardio_monotony, lift_monotony, macro_monotony]):
        cm = cardio_monotony or 50.0
        lm = lift_monotony or 50.0
        mm = macro_monotony or 50.0
        monotony_index = 0.35 * cm + 0.40 * lm + 0.25 * mm
    else:
        monotony_index = None

    # ── VIRILITY TREND: corrected formula ─────────────────────────────────────
    # VirilityDaily = 0.40*LibidoNorm + 0.35*ErectionNorm + 0.15*MentalDriveNorm + 0.10*MoodNorm
    def _norm_1_5(v):
        return (float(v) - 1) / 4 if v is not None else None

    def _norm_0_3(v):
        return float(v) / 3 if v is not None else None

    virility_daily_28d = []
    for r in rows_28d:
        lib = _norm_1_5(r["libido_score"])
        ere = _norm_0_3(r["morning_erection_score"])
        mnd = _norm_1_5(r["mental_drive_score"])
        moo = _norm_1_5(r["mood_stability_score"])
        parts = [(lib, 0.40), (ere, 0.35), (mnd, 0.15), (moo, 0.10)]
        available = [(val, w) for val, w in parts if val is not None]
        if available:
            total_w = sum(w for _, w in available)
            score = sum(val * w for val, w in available) / total_w
            virility_daily_28d.append(score)

    virility_trend_28d = (sum(virility_daily_28d) / len(virility_daily_28d) * 100) if virility_daily_28d else None

    virility_prev_28d = []
    for r in rows_prev28d:
        lib = _norm_1_5(r["libido_score"])
        ere = _norm_0_3(r["morning_erection_score"])
        mnd = _norm_1_5(r["mental_drive_score"])
        moo = _norm_1_5(r["mood_stability_score"])
        parts = [(lib, 0.40), (ere, 0.35), (mnd, 0.15), (moo, 0.10)]
        available = [(val, w) for val, w in parts if val is not None]
        if available:
            total_w = sum(w for _, w in available)
            virility_prev_28d.append(sum(val * w for val, w in available) / total_w)

    virility_trend_prev_28d = (sum(virility_prev_28d) / len(virility_prev_28d) * 100) if virility_prev_28d else None

    # ── BEHAVIORAL DELOAD COMPLIANCE ────────────────────────────────────────────
    def _compute_deload_score():
        if len(rows_28d) < 7:
            return None, False

        recent = rows_28d[-7:]
        prior = rows_28d[:-7]

        if not prior:
            return None, False

        def _avg_nonzero(rows, field):
            vals = [float(r[field]) for r in rows if r[field] is not None]
            return sum(vals) / len(vals) if vals else None

        def _score_ratio(recent_val, prior_val, lower_is_better=True):
            if recent_val is None or prior_val is None or prior_val == 0:
                return 50.0
            ratio = recent_val / prior_val
            if lower_is_better:
                if ratio <= 0.65:   return 100.0
                elif ratio <= 0.80: return 75.0
                elif ratio <= 0.95: return 40.0
                else:               return 10.0
            else:
                if ratio >= 1.30:   return 100.0
                elif ratio >= 1.10: return 75.0
                elif ratio >= 0.90: return 40.0
                else:               return 10.0

        lift_strain_recent = _avg_nonzero(recent, "lift_strain_score")
        lift_strain_prior = _avg_nonzero(prior, "lift_strain_score")

        lift_count_recent = sum(1 for r in recent if r["completed_lift_mode"] and r["completed_lift_mode"] != "off")
        lift_count_prior_norm = sum(1 for r in prior if r["completed_lift_mode"] and r["completed_lift_mode"] != "off")
        lift_count_prior_weekly = lift_count_prior_norm / (len(prior) / 7) if len(prior) >= 7 else lift_count_prior_norm

        neural_recent = sum(1 for r in recent if r["completed_lift_mode"] == "neural_tension")
        neural_prior = sum(1 for r in prior if r["completed_lift_mode"] == "neural_tension") / (len(prior) / 7)

        zone2_recent = sum(1 for r in recent if r["actual_cardio_mode"] == "zone_2")
        zone2_prior = sum(1 for r in prior if r["actual_cardio_mode"] == "zone_2") / (len(prior) / 7)

        surge_recent = sum(1 for r in recent if r["recommended_macro_day"] == "surge")
        surge_prior = sum(1 for r in prior if r["recommended_macro_day"] == "surge") / (len(prior) / 7)

        volume_score = _score_ratio(lift_count_recent, lift_count_prior_weekly, lower_is_better=True)
        neural_score = _score_ratio(neural_recent, neural_prior, lower_is_better=True)
        zone2_score = _score_ratio(zone2_recent, zone2_prior, lower_is_better=False)
        surge_score = _score_ratio(surge_recent, surge_prior, lower_is_better=True)
        strain_score = _score_ratio(lift_strain_recent, lift_strain_prior, lower_is_better=True)

        deload_score = (
            0.30 * volume_score
            + 0.20 * neural_score
            + 0.20 * zone2_score
            + 0.15 * surge_score
            + 0.15 * strain_score
        )
        return round(deload_score, 1), deload_score >= 70

    deload_score_28d, deload_compliance_28d = _compute_deload_score()

    # ── LIGHT EXPOSURE ─────────────────────────────────────────────────────────
    # Uses sunlight_min if available; default None until field is tracked
    light_exposure_consistency_28d = None

    # ── FFM TREND CONFIDENCE ───────────────────────────────────────────────────
    ffm_14d_vals = [r["fat_free_mass_lb"] for r in rows_14d if r["fat_free_mass_lb"] is not None]
    ffm_trend_14d_confidence = min(1.0, len(ffm_14d_vals) / 10) if ffm_14d_vals else 0.0

    waist_14d_vals = [r["waist_at_navel_in"] for r in rows_14d if r["waist_at_navel_in"] is not None]
    waist_trend_confidence = min(1.0, len(waist_14d_vals) / 6) if waist_14d_vals else 0.0

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
        "ffmTrend14dConfidence": ffm_trend_14d_confidence,
        "waistChange14dIn": waist_change_14d,
        "waistTrendConfidence": waist_trend_confidence,
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
        "deloadScore28d": deload_score_28d,
        "deloadCompliance28d": deload_compliance_28d,
        "trainingMonotonyIndex28d": monotony_index,
        "cardioMonotony28d": cardio_monotony,
        "liftMonotony28d": lift_monotony,
        "macroMonotony28d": macro_monotony,
        "lightExposureConsistency28d": light_exposure_consistency_28d,
        "virilityTrend28d": virility_trend_28d,
        "virilityTrendPrev28d": virility_trend_prev_28d,
        "fatHighDays7d": fat_high_days_7d,
        "fatLowDays7d": fat_low_days_7d,
        "fatDailyValues7d": fat_daily_values_7d,
        "carbDayTypeAdherence7d": carb_day_type_adherence_7d,
        "recentMacroDayTypes7d": recent_macro_types_7d,
    }
