from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.vitals_scoring import (
    calculate_acute_score, calculate_resource_score, calculate_seasonal_score,
    calculate_composite, classify_oscillator,
    MACRO_TEMPLATES, MEAL_TIMING_TEMPLATES,
)
from app.vitals_rolling import compute_rolling_references
from app.vitals_models import VitalsDailyLog, VitalsOscillatorState, VitalsUserBaselines


DEFAULT_BASELINES = {
    "hrv_year_avg": 36.0,
    "rhr_year_avg": 60.0,
    "body_weight_setpoint_lb": 156.0,
    "waist_setpoint_in": 31.5,
    "protein_floor_g": 170.0,
    "fat_floor_avg_g": 55.0,
    "default_kcal": 2695.0,
}


def _get_cycle_day_28(start_date: date, current_date: date) -> int:
    diff = (current_date - start_date).days
    return (diff % 28) + 1


def _get_cycle_week_type(cycle_day_28: int) -> str:
    if 1 <= cycle_day_28 <= 7:
        return "prime"
    if 8 <= cycle_day_28 <= 14:
        return "overload"
    if 15 <= cycle_day_28 <= 21:
        return "peak"
    return "resensitize"


def _get_baselines(db: Session, expo_user_id: str) -> dict:
    row = db.query(VitalsUserBaselines).filter(
        VitalsUserBaselines.expo_user_id == expo_user_id
    ).first()
    if not row:
        return DEFAULT_BASELINES.copy()
    return {
        "hrv_year_avg": float(row.hrv_year_avg) if row.hrv_year_avg else DEFAULT_BASELINES["hrv_year_avg"],
        "rhr_year_avg": float(row.rhr_year_avg) if row.rhr_year_avg else DEFAULT_BASELINES["rhr_year_avg"],
        "body_weight_setpoint_lb": float(row.body_weight_setpoint_lb) if row.body_weight_setpoint_lb else DEFAULT_BASELINES["body_weight_setpoint_lb"],
        "waist_setpoint_in": float(row.waist_setpoint_in) if row.waist_setpoint_in else DEFAULT_BASELINES["waist_setpoint_in"],
        "protein_floor_g": float(row.protein_floor_g) if row.protein_floor_g else DEFAULT_BASELINES["protein_floor_g"],
        "fat_floor_avg_g": float(row.fat_floor_avg_g) if row.fat_floor_avg_g else DEFAULT_BASELINES["fat_floor_avg_g"],
        "default_kcal": float(row.default_kcal) if row.default_kcal else DEFAULT_BASELINES["default_kcal"],
        "base_protein_g": float(row.base_protein_g) if row.base_protein_g else None,
        "base_carbs_g": float(row.base_carbs_g) if row.base_carbs_g else None,
        "base_fat_g": float(row.base_fat_g) if row.base_fat_g else None,
        "cycle_start_date": row.cycle_start_date,
    }


def _derive_flags(
    composite_score: float,
    hrv_ms, hrv_7d_avg,
    resting_hr_bpm, rhr_7d_avg,
    sleep_duration_min,
    zone2_count_7d: int,
    zone3_count_7d: int,
    recovery_count_7d: int,
    cycle_day_28: int
) -> dict:
    suppressed_hrv = (
        hrv_ms is not None and hrv_7d_avg is not None and
        float(hrv_ms) < float(hrv_7d_avg) * 0.90
    )
    elevated_rhr = (
        resting_hr_bpm is not None and rhr_7d_avg is not None and
        float(resting_hr_bpm) > float(rhr_7d_avg) + 4
    )
    low_sleep = sleep_duration_min is not None and float(sleep_duration_min) < 360
    hard_stop = suppressed_hrv or elevated_rhr or low_sleep or composite_score < 55
    cardio_monotony = max(zone2_count_7d, zone3_count_7d, recovery_count_7d) >= 5
    monthly_resensitize = cycle_day_28 >= 22

    return {
        "hardStopFatigue": hard_stop,
        "lowSleep": low_sleep,
        "elevatedRhr": elevated_rhr,
        "suppressedHrv": suppressed_hrv,
        "cardioMonotony": cardio_monotony,
        "monthlyResensitizeOverride": monthly_resensitize,
    }


def _decide_cardio(composite: float, flags: dict, zone3_count_7d: int, zone2_count_7d: int) -> str:
    if flags["hardStopFatigue"]:
        return "recovery_walk" if composite < 40 else "zone_2"

    if flags["monthlyResensitizeOverride"] and zone3_count_7d >= 1:
        return "zone_2"

    if zone3_count_7d >= 3:
        return "zone_2"

    if composite >= 70:
        return "zone_3"
    elif composite >= 40:
        return "zone_2"
    else:
        return "recovery_walk"


def _decide_lift(composite: float, flags: dict) -> str:
    if flags["hardStopFatigue"]:
        return "off" if composite < 40 else "recovery_patterning"
    if composite >= 85:
        return "neural_tension"
    elif composite >= 70:
        return "hypertrophy_build"
    elif composite >= 55:
        return "pump"
    elif composite >= 40:
        return "recovery_patterning"
    else:
        return "mobility"


def _decide_macro_day(composite: float, flags: dict, rhr_elevated: bool, soreness_high: bool) -> str:
    if flags["hardStopFatigue"]:
        return "resensitize" if composite < 40 else "reset"

    if flags["monthlyResensitizeOverride"]:
        if composite >= 85 and not flags["suppressedHrv"] and not flags["elevatedRhr"]:
            return "build"
        return "reset"

    if composite >= 85:
        return "surge"
    elif composite >= 70:
        return "build"
    elif composite >= 55:
        return "reset" if (rhr_elevated or soreness_high) else "build"
    elif composite >= 40:
        return "reset"
    else:
        return "resensitize"


def _build_reasoning(composite, oscillator_class, acute, resource, seasonal, cardio, lift, macro, flags) -> list:
    lines = [
        f"Composite score {composite} ({oscillator_class}).",
        f"Acute {acute}, Resource {resource}, Seasonal {seasonal}.",
    ]
    if flags["suppressedHrv"]:
        lines.append("HRV is suppressed versus 7-day baseline.")
    if flags["elevatedRhr"]:
        lines.append("RHR is elevated versus 7-day baseline.")
    if flags["lowSleep"]:
        lines.append("Sleep was below 6 hours.")
    if flags["monthlyResensitizeOverride"]:
        lines.append("Monthly cycle is in resensitize week (days 22-28).")
    if flags["cardioMonotony"]:
        lines.append("Recent cardio distribution is too repetitive.")
    lines.append(f"Assigned cardio mode: {cardio}.")
    lines.append(f"Assigned lift mode: {lift}.")
    lines.append(f"Assigned macro day: {macro}.")
    return lines


# Ingredient priority order: least → most disruptive to routine
# Each entry maps its primary macro and a secondary macro it also moves
_INGREDIENT_PRIORITY = [
    {"ingredient": "MCT Powder",  "unit": "g",   "primaryMacro": "fat",     "secondaryMacro": None},
    {"ingredient": "Dextrin",     "unit": "g",   "primaryMacro": "carbs",   "secondaryMacro": None},
    {"ingredient": "Oats",        "unit": "g",   "primaryMacro": "carbs",   "secondaryMacro": "fat",
     "carbsPerG": 0.67, "fatPerG": 0.06, "proteinPerG": 0.17},
    {"ingredient": "Bananas",     "unit": "each","primaryMacro": "carbs",   "secondaryMacro": None,
     "carbsPerUnit": 27, "proteinPerUnit": 1, "fatPerUnit": 0},
    {"ingredient": "Eggs",        "unit": "each","primaryMacro": "protein", "secondaryMacro": "fat",
     "proteinPerUnit": 6, "fatPerUnit": 5, "carbsPerUnit": 0},
    {"ingredient": "Flaxseed",    "unit": "g",   "primaryMacro": "fat",     "secondaryMacro": "carbs",
     "fatPerG": 0.40, "carbsPerG": 0.27, "proteinPerG": 0.20},
    {"ingredient": "Whey",        "unit": "g",   "primaryMacro": "protein", "secondaryMacro": None,
     "proteinPerG": 0.80, "carbsPerG": 0.08, "fatPerG": 0.05},
    {"ingredient": "Greek Yogurt","unit": "cup", "primaryMacro": "protein", "secondaryMacro": None},
]


def _compute_ingredient_adjustments(macro_day: str, macro_delta: dict) -> list:
    """Walk through ingredient priority order and assign macro delta to ingredients."""
    if not macro_delta:
        return []

    remaining = {
        "fat":     float(macro_delta.get("fatDeltaG", 0) or 0),
        "carbs":   float(macro_delta.get("carbsDeltaG", 0) or 0),
        "protein": float(macro_delta.get("proteinDeltaG", 0) or 0),
    }

    adjustments = []
    for item in _INGREDIENT_PRIORITY:
        primary = item["primaryMacro"]
        delta = remaining.get(primary, 0)
        if abs(delta) < 0.5:
            continue

        action = "increase" if delta > 0 else "decrease"
        unit = item["unit"]

        if unit == "g":
            per_g = item.get(f"{primary}PerG", 1.0)
            grams = round(delta / per_g, 0) if per_g else delta
            if abs(grams) < 1:
                continue
            display = f"{abs(int(grams))}g"
            qty = int(grams)
        elif unit == "each":
            per_unit = item.get(f"{primary}PerUnit", 1)
            units_qty = round(delta / per_unit) if per_unit else 1
            if abs(units_qty) < 1:
                continue
            display = f"{abs(int(units_qty))} unit(s)"
            qty = int(units_qty)
        else:
            display = f"1 {unit}"
            qty = 1

        adjustments.append({
            "priority":      len(adjustments) + 1,
            "ingredient":    item["ingredient"],
            "unit":          unit,
            "action":        action,
            "primaryMacro":  primary,
            "deltaG":        round(delta, 1),
            "qty":           abs(qty),
            "display":       f"{action} {display}",
        })

        remaining[primary] = 0

        if all(abs(v) < 0.5 for v in remaining.values()):
            break

    return adjustments


def _build_cycles_block(
    acute, resource, seasonal, composite, cycle_day_28,
    cycle_week_type, flags, cardio_mode, lift_mode,
    macro_day, macro_targets, macro_delta, meal_timing,
) -> dict:
    """Build per-cycle independent output channels for Expo to route to each screen."""

    acute_score = acute["score"]
    resource_score = resource["score"]
    seasonal_score = seasonal["score"]
    active_flags = [k for k, v in flags.items() if v]

    # Acute state label
    if acute_score >= 71:
        acute_state = "peaking"
    elif acute_score >= 51:
        acute_state = "stable"
    elif acute_score >= 31:
        acute_state = "recovering"
    else:
        acute_state = "suppressed"

    # Resource state label
    if resource_score >= 76:
        resource_state = "peak"
    elif resource_score >= 56:
        resource_state = "strong"
    elif resource_score >= 31:
        resource_state = "building"
    else:
        resource_state = "depleted"

    # Seasonal phase
    if cycle_day_28 <= 7:
        seasonal_phase = "prime"
    elif cycle_day_28 <= 14:
        seasonal_phase = "build"
    elif cycle_day_28 <= 21:
        seasonal_phase = "sustain"
    else:
        seasonal_phase = "deload"

    # Virility trend value from seasonal breakdown
    virility_trend = None
    import re
    for b in seasonal.get("breakdown", []):
        if b.get("key") == "virility_trend":
            m = re.search(r"([\d.]+)/100", b.get("note", ""))
            if m:
                virility_trend = float(m.group(1))

    ingredient_adjustments = _compute_ingredient_adjustments(macro_day, macro_delta)

    # Key drivers for acute — top 3 breakdown items by abs(score)
    acute_breakdown = sorted(
        acute.get("breakdown", []),
        key=lambda b: abs(b.get("score", 0)),
        reverse=True,
    )[:3]

    return {
        "acute_7d": {
            "score":       acute_score,
            "maxScore":    100,
            "state":       acute_state,
            "governor":    "vitals_tab",
            "activeFlags": active_flags,
            "keyDrivers":  [{"key": b["key"], "score": b["score"], "note": b.get("note", "")} for b in acute_breakdown],
            "output": {
                "cardioMode": cardio_mode,
                "liftMode":   lift_mode,
            },
        },
        "resource_14d": {
            "score":     resource_score,
            "maxScore":  100,
            "state":     resource_state,
            "governor":  "nutrition_targets",
            "output": {
                "macroDay":              macro_day,
                "macroTargets":          macro_targets,
                "macroDelta":            macro_delta,
                "ingredientAdjustments": ingredient_adjustments,
            },
        },
        "seasonal_28d": {
            "score":      seasonal_score,
            "maxScore":   100,
            "cycleDay":   cycle_day_28,
            "weekType":   cycle_week_type,
            "phase":      seasonal_phase,
            "governor":   "report_monthly",
            "output": {
                "deloadActive":   flags.get("monthlyResensitizeOverride", False),
                "virilityTrend":  virility_trend,
                "narrative":      (
                    f"Day {cycle_day_28} of 28 — {seasonal_phase} window. "
                    f"{cycle_week_type.replace('_', ' ').title()} prescription active."
                ),
            },
        },
        "circadian_24h": {
            "governor": "plan_tab",
            "output": {
                "cardioWindow": {"mode": cardio_mode, "anchor": "06:00"},
                "liftWindow":   {"mode": lift_mode,   "anchor": "17:00"},
                "mealTiming":   meal_timing,
            },
        },
        "ultradian_90min": {
            "governor": "game_timing",
            "status":   "not_yet_implemented",
            "note":     "Grip/CNS check-in layer pending. Will govern within-day nudges and game timing.",
        },
        "macro_block_90d": {
            "governor": "report_longrange",
            "status":   "not_yet_implemented",
            "note":     "Strength arc / recomp phase tracking pending. Will govern Report screen long-range view.",
        },
    }


def compute_daily_recommendation(db: Session, expo_user_id: str, log_row: VitalsDailyLog) -> dict:
    target_date = log_row.date
    baselines = _get_baselines(db, expo_user_id)
    refs = compute_rolling_references(db, expo_user_id, target_date)

    yesterday = target_date - timedelta(days=1)
    yesterday_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == yesterday
    ).first()
    yesterday_lift_strain = float(yesterday_row.lift_strain_score) if yesterday_row and yesterday_row.lift_strain_score else None
    yesterday_cardio = yesterday_row.actual_cardio_mode if yesterday_row else None

    acute = calculate_acute_score(
        hrv_ms=log_row.hrv_ms,
        hrv_7d_avg=refs["hrv7dAvg"],
        hrv_year_avg=baselines["hrv_year_avg"],
        resting_hr_bpm=log_row.resting_hr_bpm,
        rhr_7d_avg=refs["rhr7dAvg"],
        rhr_year_avg=baselines["rhr_year_avg"],
        sleep_duration_min=log_row.sleep_duration_min,
        sleep_efficiency_pct=log_row.sleep_efficiency_pct,
        sleep_midpoint_min=log_row.sleep_midpoint_min,
        sleep_midpoint_7d_avg=refs["sleepMidpoint7dAvg"],
        body_weight_lb=log_row.body_weight_lb,
        weight_7d_avg=refs["bodyWeight7dAvg"],
        libido_score=log_row.libido_score,
        morning_erection_score=log_row.morning_erection_score,
        motivation_score=log_row.motivation_score,
        mental_drive_score=log_row.mental_drive_score,
        soreness_score=log_row.soreness_score,
        joint_friction_score=log_row.joint_friction_score,
        yesterday_lift_strain_score=yesterday_lift_strain,
        yesterday_cardio_mode=yesterday_cardio,
    )

    resource = calculate_resource_score(
        kcal_7d_avg=refs["kcal7dAvg"],
        kcal_target=float(log_row.kcal_target) if log_row.kcal_target else baselines["default_kcal"],
        protein_7d_avg=refs["protein7dAvg"],
        fat_7d_avg=refs["fat7dAvg"],
        recent_macro_day_types_7d=refs["recentMacroDayTypes7d"],
        carbs_7d_avg=refs["carbs7dAvg"],
        carbs_g_target=float(log_row.carbs_g_target) if log_row.carbs_g_target else None,
        weight_trend_14d_lb_per_week=refs["weightTrend14dLbPerWeek"],
        waist_change_14d_in=refs["waistChange14dIn"],
        ffm_trend_14d_lb_per_week=refs["ffmTrend14dLbPerWeek"],
        strength_trend_14d_pct=refs["strengthTrend14dPct"],
        zone2_count_7d=refs["cardioZone2Count7d"],
        zone3_count_7d=refs["cardioZone3Count7d"],
        recovery_count_7d=refs["cardioRecoveryCount7d"],
    )

    seasonal = calculate_seasonal_score(
        hrv_28d_avg=refs["hrv28dAvg"],
        hrv_prev_28d_avg=refs["hrvPrev28dAvg"],
        rhr_28d_avg=refs["rhr28dAvg"],
        rhr_prev_28d_avg=refs["rhrPrev28dAvg"],
        sleep_regularity_28d_score=refs["sleepRegularity28dScore"],
        sleep_regularity_prev_28d_score=refs["sleepRegularityPrev28dScore"],
        waist_28d_change_in=refs["waist28dChangeIn"],
        weight_28d_change_lb=refs["weight28dChangeLb"],
        ffm_28d_avg=refs["ffm28dAvg"],
        ffm_prev_28d_avg=refs["ffmPrev28dAvg"],
        deload_compliance_28d=refs["deloadCompliance28d"],
        training_monotony_index_28d=refs["trainingMonotonyIndex28d"],
        light_exposure_consistency_28d=refs["lightExposureConsistency28d"],
        virility_trend_28d=refs["virilityTrend28d"],
    )

    composite = calculate_composite(acute["score"], resource["score"], seasonal["score"])

    cycle_start = baselines.get("cycle_start_date") or target_date
    cycle_day_28 = _get_cycle_day_28(cycle_start, target_date)
    cycle_week_type = _get_cycle_week_type(cycle_day_28)

    soreness_high = log_row.soreness_score is not None and int(log_row.soreness_score) >= 4
    flags = _derive_flags(
        composite["compositeScore"],
        log_row.hrv_ms, refs["hrv7dAvg"],
        log_row.resting_hr_bpm, refs["rhr7dAvg"],
        log_row.sleep_duration_min,
        refs["cardioZone2Count7d"],
        refs["cardioZone3Count7d"],
        refs["cardioRecoveryCount7d"],
        cycle_day_28,
    )

    cardio_mode = _decide_cardio(composite["compositeScore"], flags, refs["cardioZone3Count7d"], refs["cardioZone2Count7d"])
    lift_mode = _decide_lift(composite["compositeScore"], flags)
    macro_day = _decide_macro_day(composite["compositeScore"], flags, flags["elevatedRhr"], soreness_high)

    macro_targets = MACRO_TEMPLATES[macro_day]
    meal_timing = MEAL_TIMING_TEMPLATES[macro_day]
    reasoning = _build_reasoning(
        composite["compositeScore"], composite["oscillatorClass"],
        acute["score"], resource["score"], seasonal["score"],
        cardio_mode, lift_mode, macro_day, flags,
    )

    base_p = baselines.get("base_protein_g")
    base_c = baselines.get("base_carbs_g")
    base_f = baselines.get("base_fat_g")
    if base_p is not None and base_c is not None and base_f is not None:
        macro_delta = {
            "proteinDeltaG": round(macro_targets["proteinG"] - base_p, 1),
            "carbsDeltaG": round(macro_targets["carbsG"] - base_c, 1),
            "fatDeltaG": round(macro_targets["fatG"] - base_f, 1),
            "kcalDelta": round(macro_targets["kcal"] - float(baselines["default_kcal"]), 0),
        }
    else:
        macro_delta = None

    cycles = _build_cycles_block(
        acute=acute, resource=resource, seasonal=seasonal,
        composite=composite, cycle_day_28=cycle_day_28,
        cycle_week_type=cycle_week_type, flags=flags,
        cardio_mode=cardio_mode, lift_mode=lift_mode,
        macro_day=macro_day, macro_targets=macro_targets,
        macro_delta=macro_delta, meal_timing=meal_timing,
    )

    return {
        "acuteResult": acute,
        "resourceResult": resource,
        "seasonalResult": seasonal,
        "composite": composite,
        "cycleDay28": cycle_day_28,
        "cycleWeekType": cycle_week_type,
        "flags": flags,
        "recommendedCardioMode": cardio_mode,
        "recommendedLiftMode": lift_mode,
        "recommendedMacroDayType": macro_day,
        "macroTargets": macro_targets,
        "macroDelta": macro_delta,
        "mealTimingTargets": meal_timing,
        "reasoning": reasoning,
        "cycles": cycles,
        "refs": refs,
    }


def persist_oscillator_state(db: Session, expo_user_id: str, log_row: VitalsDailyLog, result: dict):
    refs = result["refs"]
    composite = result["composite"]

    existing = db.query(VitalsOscillatorState).filter(
        VitalsOscillatorState.expo_user_id == expo_user_id,
        VitalsOscillatorState.date == log_row.date,
    ).first()

    if not existing:
        existing = VitalsOscillatorState(expo_user_id=expo_user_id, date=log_row.date)
        db.add(existing)

    existing.cycle_day_28 = result["cycleDay28"]
    existing.cycle_week_type = result["cycleWeekType"]
    existing.acute_score = result["acuteResult"]["score"]
    existing.resource_score = result["resourceResult"]["score"]
    existing.seasonal_score = result["seasonalResult"]["score"]
    existing.oscillator_composite_score = composite["compositeScore"]
    existing.oscillator_class = composite["oscillatorClass"]
    existing.rolling_zone2_count_7d = refs["cardioZone2Count7d"]
    existing.rolling_zone3_count_7d = refs["cardioZone3Count7d"]
    existing.rolling_recovery_count_7d = refs["cardioRecoveryCount7d"]
    existing.rolling_neural_lift_count_7d = refs["neuralLiftCount7d"]
    existing.rolling_reset_day_count_28d = refs["resetOrResensitizeDayCount28d"]
    existing.fatigue_flag = result["flags"]["hardStopFatigue"]
    existing.monotony_flag = result["flags"]["cardioMonotony"]
    existing.deload_compliance_flag = refs["deloadCompliance28d"]
    existing.acute_breakdown = result["acuteResult"]["breakdown"]
    existing.resource_breakdown = result["resourceResult"]["breakdown"]
    existing.seasonal_breakdown = result["seasonalResult"]["breakdown"]
    db.commit()
