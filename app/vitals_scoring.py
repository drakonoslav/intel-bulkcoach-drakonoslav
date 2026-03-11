from typing import Optional


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return float(a) / float(b)


def _avg(values):
    valid = [float(v) for v in values if v is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _normalize_five_point(v):
    if v is None:
        return None
    return _clamp(((float(v) - 1) / 4) * 10, 0, 10)


def _normalize_three_zero(v):
    if v is None:
        return None
    return _clamp((float(v) / 3) * 10, 0, 10)


def _reverse_five_point(v):
    if v is None:
        return None
    return _clamp(((5 - float(v)) / 4) * 10, 0, 10)


def _item(key, label, score, max_score, note=""):
    return {"key": key, "label": label, "score": score, "maxScore": max_score, "note": note}


def score_hrv_state(today_hrv, hrv_7d_avg, hrv_year_avg):
    ratio = _safe_ratio(today_hrv, hrv_7d_avg)
    year_ratio = _safe_ratio(today_hrv, hrv_year_avg)

    if ratio is None:
        score = 0
        note = "Missing HRV"
    elif ratio >= 1.10:
        score = 22
    elif ratio >= 1.03:
        score = 19
    elif ratio >= 0.97:
        score = 15
    elif ratio >= 0.90:
        score = 9
    else:
        score = 4

    if ratio is not None:
        note = f"HRV ratio vs 7d avg: {ratio:.2f}"

    if year_ratio is not None:
        if year_ratio > 1.15:
            score += 1
        if year_ratio < 0.85:
            score -= 1

    return _item("hrv_state", "HRV State", _clamp(score, 0, 22), 22, note if ratio is None else f"HRV ratio vs 7d avg: {ratio:.2f}")


def score_rhr_state(today_rhr, rhr_7d_avg, rhr_year_avg):
    if today_rhr is None or rhr_7d_avg is None:
        return _item("rhr_state", "RHR State", 0, 18, "Missing RHR")

    delta = float(today_rhr) - float(rhr_7d_avg)
    if delta <= -3:
        score = 18
    elif delta <= -1:
        score = 16
    elif delta <= 1:
        score = 13
    elif delta <= 3:
        score = 8
    elif delta <= 5:
        score = 4
    else:
        score = 1

    if rhr_year_avg is not None:
        if float(today_rhr) <= float(rhr_year_avg) - 3:
            score += 1
        if float(today_rhr) >= float(rhr_year_avg) + 5:
            score -= 1

    return _item("rhr_state", "RHR State", _clamp(score, 0, 18), 18, f"RHR delta vs 7d avg: {delta:.1f} bpm")


def score_sleep_quantity(sleep_duration_min, sleep_efficiency_pct):
    if sleep_duration_min is None:
        return _item("sleep_quantity", "Sleep Quantity", 0, 15, "Missing sleep duration")

    s = float(sleep_duration_min)
    if 450 <= s <= 510:
        score = 15
    elif (420 <= s <= 449) or (511 <= s <= 540):
        score = 12
    elif 390 <= s <= 419:
        score = 8
    elif 360 <= s <= 389:
        score = 4
    else:
        score = 1

    if sleep_efficiency_pct is not None and float(sleep_efficiency_pct) >= 90:
        score += 1

    return _item("sleep_quantity", "Sleep Quantity", _clamp(score, 0, 15), 15, f"{s:.0f} min sleep")


def score_sleep_regularity(sleep_midpoint_min, sleep_midpoint_7d_avg):
    if sleep_midpoint_min is None or sleep_midpoint_7d_avg is None:
        return _item("sleep_regularity", "Sleep Regularity", 0, 8, "Missing midpoint data")

    shift = abs(float(sleep_midpoint_min) - float(sleep_midpoint_7d_avg))
    if shift <= 20:
        score = 8
    elif shift <= 40:
        score = 6
    elif shift <= 60:
        score = 4
    elif shift <= 90:
        score = 2
    else:
        score = 0

    return _item("sleep_regularity", "Sleep Regularity", score, 8, f"Midpoint shift: {shift:.0f} min")


def score_bodyweight_stability(body_weight_lb, weight_7d_avg):
    if body_weight_lb is None or weight_7d_avg is None or float(weight_7d_avg) == 0:
        return _item("bodyweight_stability", "Bodyweight Stability", 0, 5, "Missing body weight")

    delta_pct = ((float(body_weight_lb) - float(weight_7d_avg)) / float(weight_7d_avg)) * 100
    abs_pct = abs(delta_pct)

    if abs_pct <= 0.4:
        score = 5
    elif abs_pct <= 0.8:
        score = 4
    elif abs_pct <= 1.2:
        score = 2
    else:
        score = 0

    return _item("bodyweight_stability", "Bodyweight Stability", score, 5, f"Weight delta vs 7d avg: {delta_pct:.2f}%")


def score_subjective_drive(libido_score, morning_erection_score, motivation_score, mental_drive_score):
    values = [
        _normalize_five_point(libido_score),
        _normalize_three_zero(morning_erection_score),
        _normalize_five_point(motivation_score),
        _normalize_five_point(mental_drive_score),
    ]
    value = _avg(values)
    if value is None:
        return _item("subjective_drive", "Subjective Drive", 0, 10, "Missing subjective entries")
    score = int(_clamp(round(value), 0, 10))
    return _item("subjective_drive", "Subjective Drive", score, 10, f"Average subjective drive {value:.1f}/10")


def score_joint_soreness(soreness_score, joint_friction_score):
    values = [
        _reverse_five_point(soreness_score),
        _reverse_five_point(joint_friction_score),
    ]
    value = _avg(values)
    if value is None:
        return _item("joint_soreness", "Joint / Soreness State", 0, 10, "Missing soreness/joint data")
    score = int(_clamp(round(value), 0, 10))
    return _item("joint_soreness", "Joint / Soreness State", score, 10, f"Recovery comfort {value:.1f}/10")


def score_yesterday_lift_strain(yesterday_lift_strain_score):
    if yesterday_lift_strain_score is None:
        return _item("yesterday_lift_strain", "Yesterday Lift Strain", 0, 7, "Missing yesterday lift strain")

    s = float(yesterday_lift_strain_score)
    if s <= 35:
        score = 7
    elif s <= 55:
        score = 5
    elif s <= 70:
        score = 3
    else:
        score = 1

    return _item("yesterday_lift_strain", "Yesterday Lift Strain", score, 7, f"Yesterday lift strain {s:.0f}")


def score_yesterday_cardio_strain(yesterday_cardio_mode):
    mode_scores = {
        "recovery_walk": 5,
        "zone_2": 4,
        "zone_3": 2,
    }
    score = mode_scores.get(yesterday_cardio_mode, 0)
    note = yesterday_cardio_mode or "Missing yesterday cardio mode"
    return _item("yesterday_cardio_strain", "Yesterday Cardio Strain", score, 5, note)


def calculate_acute_score(
    hrv_ms, hrv_7d_avg, hrv_year_avg,
    resting_hr_bpm, rhr_7d_avg, rhr_year_avg,
    sleep_duration_min, sleep_efficiency_pct,
    sleep_midpoint_min, sleep_midpoint_7d_avg,
    body_weight_lb, weight_7d_avg,
    libido_score, morning_erection_score, motivation_score, mental_drive_score,
    soreness_score, joint_friction_score,
    yesterday_lift_strain_score, yesterday_cardio_mode
):
    breakdown = [
        score_hrv_state(hrv_ms, hrv_7d_avg, hrv_year_avg),
        score_rhr_state(resting_hr_bpm, rhr_7d_avg, rhr_year_avg),
        score_sleep_quantity(sleep_duration_min, sleep_efficiency_pct),
        score_sleep_regularity(sleep_midpoint_min, sleep_midpoint_7d_avg),
        score_bodyweight_stability(body_weight_lb, weight_7d_avg),
        score_subjective_drive(libido_score, morning_erection_score, motivation_score, mental_drive_score),
        score_joint_soreness(soreness_score, joint_friction_score),
        score_yesterday_lift_strain(yesterday_lift_strain_score),
        score_yesterday_cardio_strain(yesterday_cardio_mode),
    ]
    total = _clamp(sum(item["score"] for item in breakdown), 0, 100)
    return {"score": total, "breakdown": breakdown}


def score_calorie_adherence_7d(kcal_7d_avg, kcal_target):
    ratio = _safe_ratio(kcal_7d_avg, kcal_target)
    if ratio is None:
        return _item("calorie_adherence_7d", "Calorie Adherence 7d", 0, 10, "Missing 7d kcal average")

    if 0.97 <= ratio <= 1.03:
        score = 10
    elif (0.94 <= ratio < 0.97) or (1.03 < ratio <= 1.06):
        score = 8
    elif (0.90 <= ratio < 0.94) or (1.06 < ratio <= 1.10):
        score = 5
    else:
        score = 2

    return _item("calorie_adherence_7d", "Calorie Adherence 7d", score, 10, f"7d kcal ratio {ratio:.2f}")


def score_protein_adequacy_7d(protein_7d_avg):
    if protein_7d_avg is None:
        return _item("protein_adequacy_7d", "Protein Adequacy 7d", 0, 12, "Missing 7d protein avg")

    p = float(protein_7d_avg)
    if 170 <= p <= 180:
        score = 12
    elif (160 <= p < 170) or (180 < p <= 190):
        score = 9
    elif 145 <= p < 160:
        score = 5
    else:
        score = 1

    return _item("protein_adequacy_7d", "Protein Adequacy 7d", score, 12, f"{p:.1f} g/day")


def score_fat_floor_7d(fat_7d_avg, recent_macro_day_types_7d):
    if fat_7d_avg is None:
        return _item("fat_floor_7d", "Fat Floor / Oscillation 7d", 0, 12, "Missing 7d fat avg")

    fat = float(fat_7d_avg)
    has_high_days = sum(1 for d in recent_macro_day_types_7d if d in ("reset", "resensitize")) >= 2
    has_low_days = sum(1 for d in recent_macro_day_types_7d if d == "surge") >= 2

    if fat >= 55 and has_high_days and has_low_days:
        score = 12
    elif fat >= 55:
        score = 9
    elif fat >= 50:
        score = 6
    else:
        score = 2

    return _item("fat_floor_7d", "Fat Floor / Oscillation 7d", score, 12, f"{fat:.1f} g/day")


def score_carb_adequacy_training(carbs_7d_avg, carbs_g_target):
    ratio = _safe_ratio(carbs_7d_avg, carbs_g_target or 330)
    if ratio is None:
        return _item("carb_adequacy_training", "Carb Adequacy Around Training", 0, 10, "Missing carb averages")

    if ratio >= 0.9:
        score = 10
    elif ratio >= 0.8:
        score = 8
    elif ratio >= 0.65:
        score = 5
    else:
        score = 2

    return _item("carb_adequacy_training", "Carb Adequacy Around Training", score, 10, f"Carb adherence ratio {ratio:.2f}")


def score_weight_trend(weight_trend_14d_lb_per_week):
    if weight_trend_14d_lb_per_week is None:
        return _item("weight_trend", "Weight Trend 14d", 0, 10, "Missing weight trend")

    t = float(weight_trend_14d_lb_per_week)
    if 0.10 <= t <= 0.50:
        score = 10
    elif 0.0 <= t < 0.10:
        score = 8
    elif 0.50 < t <= 0.80:
        score = 6
    elif t < -0.10:
        score = 4
    else:
        score = 3

    return _item("weight_trend", "Weight Trend 14d", score, 10, f"{t:.2f} lb/week")


def score_waist_trend(waist_change_14d_in):
    if waist_change_14d_in is None:
        return _item("waist_trend", "Waist Trend 14d", 0, 12, "Missing waist trend")

    c = float(waist_change_14d_in)
    if -0.25 <= c <= 0.10:
        score = 12
    elif 0.10 < c <= 0.25:
        score = 9
    elif 0.25 < c <= 0.40:
        score = 6
    else:
        score = 2

    return _item("waist_trend", "Waist Trend 14d", score, 12, f"{c:.2f} in")


def score_ffm_trend(ffm_trend_14d_lb_per_week):
    if ffm_trend_14d_lb_per_week is None:
        return _item("ffm_trend", "FFM Trend 14d", 0, 12, "Missing FFM trend")

    t = float(ffm_trend_14d_lb_per_week)
    if 0.20 <= t <= 0.60:
        score = 12
    elif 0.05 <= t < 0.20:
        score = 9
    elif -0.04 <= t < 0.05:
        score = 7
    else:
        score = 3

    return _item("ffm_trend", "FFM Trend 14d", score, 12, f"{t:.2f} lb/week")


def score_strength_trend(strength_trend_14d_pct):
    if strength_trend_14d_pct is None:
        return _item("strength_trend", "Strength Trend 14d", 0, 12, "Missing strength trend")

    t = float(strength_trend_14d_pct)
    if t > 2:
        score = 12
    elif t >= 0:
        score = 9
    elif t >= -2:
        score = 6
    else:
        score = 2

    return _item("strength_trend", "Strength Trend 14d", score, 12, f"{t:.2f}%")


def score_cardio_monotony(zone2_count_7d, zone3_count_7d, recovery_count_7d):
    z2 = int(zone2_count_7d or 0)
    z3 = int(zone3_count_7d or 0)
    easy = int(recovery_count_7d or 0)
    identical_max = max(z2, z3, easy)

    if (z2 == 3 and z3 == 3 and easy == 1) or identical_max <= 3:
        score = 10
    elif identical_max <= 4:
        score = 7
    elif identical_max <= 5:
        score = 4
    else:
        score = 1

    return _item("cardio_monotony", "Cardio Distribution 7d", score, 10, f"Z2:{z2} Z3:{z3} Easy:{easy}")


def calculate_resource_score(
    kcal_7d_avg, kcal_target,
    protein_7d_avg,
    fat_7d_avg, recent_macro_day_types_7d,
    carbs_7d_avg, carbs_g_target,
    weight_trend_14d_lb_per_week,
    waist_change_14d_in,
    ffm_trend_14d_lb_per_week,
    strength_trend_14d_pct,
    zone2_count_7d, zone3_count_7d, recovery_count_7d
):
    breakdown = [
        score_calorie_adherence_7d(kcal_7d_avg, kcal_target),
        score_protein_adequacy_7d(protein_7d_avg),
        score_fat_floor_7d(fat_7d_avg, recent_macro_day_types_7d),
        score_carb_adequacy_training(carbs_7d_avg, carbs_g_target),
        score_weight_trend(weight_trend_14d_lb_per_week),
        score_waist_trend(waist_change_14d_in),
        score_ffm_trend(ffm_trend_14d_lb_per_week),
        score_strength_trend(strength_trend_14d_pct),
        score_cardio_monotony(zone2_count_7d, zone3_count_7d, recovery_count_7d),
    ]
    total = _clamp(sum(item["score"] for item in breakdown), 0, 100)
    return {"score": total, "breakdown": breakdown}


def score_hrv_28d_trend(hrv_28d_avg, hrv_prev_28d_avg):
    if hrv_28d_avg is None or hrv_prev_28d_avg is None or float(hrv_prev_28d_avg) == 0:
        return _item("hrv_28d_trend", "HRV 28d Trend", 0, 18, "Missing HRV 28d trend")

    pct = ((float(hrv_28d_avg) - float(hrv_prev_28d_avg)) / float(hrv_prev_28d_avg)) * 100
    if pct > 8:
        score = 18
    elif pct >= 3:
        score = 15
    elif pct >= -2:
        score = 11
    elif pct >= -7:
        score = 6
    else:
        score = 2

    return _item("hrv_28d_trend", "HRV 28d Trend", score, 18, f"{pct:.2f}%")


def score_rhr_28d_trend(rhr_28d_avg, rhr_prev_28d_avg):
    if rhr_28d_avg is None or rhr_prev_28d_avg is None:
        return _item("rhr_28d_trend", "RHR 28d Trend", 0, 14, "Missing RHR 28d trend")

    delta = float(rhr_28d_avg) - float(rhr_prev_28d_avg)
    if delta <= -3:
        score = 14
    elif delta <= -1:
        score = 11
    elif delta <= 0.99:
        score = 8
    elif delta <= 2:
        score = 4
    else:
        score = 1

    return _item("rhr_28d_trend", "RHR 28d Trend", score, 14, f"{delta:.2f} bpm")


def score_sleep_regularity_28d(sleep_regularity_28d_score, sleep_regularity_prev_28d_score):
    if sleep_regularity_28d_score is None or sleep_regularity_prev_28d_score is None:
        return _item("sleep_regularity_28d", "Sleep Regularity 28d", 0, 10, "Missing sleep regularity trend")

    delta = float(sleep_regularity_28d_score) - float(sleep_regularity_prev_28d_score)
    if delta >= 8:
        score = 10
    elif delta >= 3:
        score = 8
    elif delta >= -2:
        score = 7
    elif delta >= -8:
        score = 3
    else:
        score = 1

    return _item("sleep_regularity_28d", "Sleep Regularity 28d", score, 10, f"{delta:.1f} pts")


def score_waist_weight_relationship(waist_28d_change_in, weight_28d_change_lb):
    if waist_28d_change_in is None or weight_28d_change_lb is None:
        return _item("waist_weight_relationship", "Waist:Weight Relationship", 0, 12, "Missing waist/weight relationship")

    waist = float(waist_28d_change_in)
    weight = float(weight_28d_change_lb)
    denom = max(abs(weight), 0.5)
    ratio = waist / denom

    if weight > 0 and waist <= 0:
        score = 12
    elif ratio <= 0.10:
        score = 9
    elif ratio <= 0.20:
        score = 5
    else:
        score = 2

    return _item("waist_weight_relationship", "Waist:Weight Relationship", score, 12, f"Waist per lb ratio {ratio:.3f}")


def score_ffm_28d_trend(ffm_28d_avg, ffm_prev_28d_avg):
    if ffm_28d_avg is None or ffm_prev_28d_avg is None:
        return _item("ffm_28d_trend", "FFM 28d Trend", 0, 14, "Missing FFM 28d trend")

    delta = float(ffm_28d_avg) - float(ffm_prev_28d_avg)
    if delta > 0.75:
        score = 14
    elif delta > 0.25:
        score = 11
    elif delta >= -0.1:
        score = 8
    else:
        score = 3

    return _item("ffm_28d_trend", "FFM 28d Trend", score, 14, f"{delta:.2f} lb")


def score_deload_compliance(deload_compliance_28d: bool):
    score = 10 if deload_compliance_28d else 1
    note = "Deload/resensitize block completed" if deload_compliance_28d else "No meaningful deload block found"
    return _item("deload_compliance", "Deload Compliance", score, 10, note)


def score_training_variation(training_monotony_index_28d):
    if training_monotony_index_28d is None:
        return _item("training_variation", "Training Variation", 0, 8, "Missing training monotony index")

    m = float(training_monotony_index_28d)
    if m <= 30:
        score = 8
    elif m <= 50:
        score = 5
    else:
        score = 1

    return _item("training_variation", "Training Variation", score, 8, f"Monotony {m:.1f}")


def score_light_consistency(light_exposure_consistency_28d):
    if light_exposure_consistency_28d is None:
        return _item("light_consistency", "Light / Outdoor Consistency", 0, 6, "Missing light exposure consistency")

    v = float(light_exposure_consistency_28d)
    if v >= 85:
        score = 6
    elif v >= 65:
        score = 4
    else:
        score = 2

    return _item("light_consistency", "Light / Outdoor Consistency", score, 6, f"{v:.1f}/100")


def score_virility_trend(virility_trend_28d):
    if virility_trend_28d is None:
        return _item("virility_trend", "Virility / Motivation Trend", 0, 8, "Missing virility trend")

    v = float(virility_trend_28d)
    if v >= 75:
        score = 8
    elif v >= 55:
        score = 6
    elif v >= 40:
        score = 4
    else:
        score = 1

    return _item("virility_trend", "Virility / Motivation Trend", score, 8, f"{v:.1f}/100")


def calculate_seasonal_score(
    hrv_28d_avg, hrv_prev_28d_avg,
    rhr_28d_avg, rhr_prev_28d_avg,
    sleep_regularity_28d_score, sleep_regularity_prev_28d_score,
    waist_28d_change_in, weight_28d_change_lb,
    ffm_28d_avg, ffm_prev_28d_avg,
    deload_compliance_28d,
    training_monotony_index_28d,
    light_exposure_consistency_28d,
    virility_trend_28d
):
    breakdown = [
        score_hrv_28d_trend(hrv_28d_avg, hrv_prev_28d_avg),
        score_rhr_28d_trend(rhr_28d_avg, rhr_prev_28d_avg),
        score_sleep_regularity_28d(sleep_regularity_28d_score, sleep_regularity_prev_28d_score),
        score_waist_weight_relationship(waist_28d_change_in, weight_28d_change_lb),
        score_ffm_28d_trend(ffm_28d_avg, ffm_prev_28d_avg),
        score_deload_compliance(bool(deload_compliance_28d)),
        score_training_variation(training_monotony_index_28d),
        score_light_consistency(light_exposure_consistency_28d),
        score_virility_trend(virility_trend_28d),
    ]
    total = _clamp(sum(item["score"] for item in breakdown), 0, 100)
    return {"score": total, "breakdown": breakdown}


def classify_oscillator(composite: float) -> str:
    if composite >= 85:
        return "peak"
    if composite >= 70:
        return "strong_build"
    if composite >= 55:
        return "controlled_build"
    if composite >= 40:
        return "reset"
    return "resensitize"


def calculate_composite(acute_score: float, resource_score: float, seasonal_score: float) -> dict:
    composite = round(acute_score * 0.5 + resource_score * 0.3 + seasonal_score * 0.2)
    composite = int(_clamp(composite, 0, 100))
    return {
        "acuteScore": acute_score,
        "resourceScore": resource_score,
        "seasonalScore": seasonal_score,
        "compositeScore": composite,
        "oscillatorClass": classify_oscillator(composite),
    }


MACRO_TEMPLATES = {
    "surge":        {"kcal": 2700, "proteinG": 175, "carbsG": 390, "fatG": 40},
    "build":        {"kcal": 2695, "proteinG": 175, "carbsG": 350, "fatG": 60},
    "reset":        {"kcal": 2695, "proteinG": 175, "carbsG": 290, "fatG": 80},
    "resensitize":  {"kcal": 2610, "proteinG": 175, "carbsG": 250, "fatG": 90},
}

MEAL_TIMING_TEMPLATES = {
    "surge": {
        "preCardioCarbsG": 30, "postCardioProteinG": 40, "postCardioCarbsG": 90, "postCardioFatG": 10,
        "meal2ProteinG": 30, "meal2CarbsG": 60, "meal2FatG": 10,
        "preLiftProteinG": 25, "preLiftCarbsG": 80, "preLiftFatG": 5,
        "postLiftProteinG": 45, "postLiftCarbsG": 110, "postLiftFatG": 5,
        "finalMealProteinG": 35, "finalMealCarbsG": 20, "finalMealFatG": 10,
    },
    "build": {
        "preCardioCarbsG": 30, "postCardioProteinG": 40, "postCardioCarbsG": 75, "postCardioFatG": 10,
        "meal2ProteinG": 30, "meal2CarbsG": 55, "meal2FatG": 10,
        "preLiftProteinG": 25, "preLiftCarbsG": 65, "preLiftFatG": 5,
        "postLiftProteinG": 45, "postLiftCarbsG": 85, "postLiftFatG": 5,
        "finalMealProteinG": 35, "finalMealCarbsG": 40, "finalMealFatG": 30,
    },
    "reset": {
        "preCardioCarbsG": 25, "postCardioProteinG": 40, "postCardioCarbsG": 60, "postCardioFatG": 15,
        "meal2ProteinG": 30, "meal2CarbsG": 45, "meal2FatG": 15,
        "preLiftProteinG": 25, "preLiftCarbsG": 45, "preLiftFatG": 10,
        "postLiftProteinG": 45, "postLiftCarbsG": 55, "postLiftFatG": 10,
        "finalMealProteinG": 35, "finalMealCarbsG": 35, "finalMealFatG": 30,
    },
    "resensitize": {
        "preCardioCarbsG": 20, "postCardioProteinG": 40, "postCardioCarbsG": 45, "postCardioFatG": 15,
        "meal2ProteinG": 30, "meal2CarbsG": 35, "meal2FatG": 20,
        "preLiftProteinG": 25, "preLiftCarbsG": 30, "preLiftFatG": 10,
        "postLiftProteinG": 40, "postLiftCarbsG": 40, "postLiftFatG": 10,
        "finalMealProteinG": 40, "finalMealCarbsG": 40, "finalMealFatG": 35,
    },
}
