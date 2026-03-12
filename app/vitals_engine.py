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


def _decide_cardio(
    composite: float, flags: dict,
    zone3_count_7d: int, zone2_count_7d: int,
    hrv_ms=None, hrv_7d_avg=None,
    resting_hr_bpm=None, rhr_7d_avg=None,
    previous_two_zone3: bool = False,
) -> str:
    # Hard override — HRV suppression or RHR elevation → floor at zone_2
    if hrv_ms is not None and hrv_7d_avg is not None:
        if float(hrv_ms) < 0.90 * float(hrv_7d_avg):
            return "zone_2"
    if resting_hr_bpm is not None and rhr_7d_avg is not None:
        if float(resting_hr_bpm) > float(rhr_7d_avg) + 4:
            return "zone_2"

    # Sequential cap — two consecutive zone3 sessions → force zone_2
    if previous_two_zone3:
        return "zone_2"

    if flags["hardStopFatigue"]:
        return "recovery_walk" if composite < 40 else "zone_2"

    if flags["monthlyResensitizeOverride"] and zone3_count_7d >= 1:
        return "zone_2"

    # Rolling cap — 3+ zone3 sessions in 7 days
    if zone3_count_7d >= 3:
        return "zone_2"

    # Resensitize week — limit zone3 to at most 1 per week
    if flags["monthlyResensitizeOverride"] and zone3_count_7d >= 1:
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


# Ingredient priority order: least → most disruptive to routine.
# kcalPerPrimaryUnit: Intel canonical calorie density — Expo must use these values
# to stay in sync with Intel's macro target math (4 kcal/g carb, 9 kcal/g fat, 4 kcal/g protein).
# protectedMealWindows: meal windows that must not be reduced (anabolic timing).
# preferredReductionWindow: which named meal to draw from first when reducing.
_INGREDIENT_PRIORITY = [
    {
        "ingredient": "MCT Powder",  "unit": "g",   "primaryMacro": "fat",
        "secondaryMacro": None,
        "kcalPerPrimaryUnit": 9.0,
        "perIngredientCapG": 25,
    },
    {
        "ingredient": "Dextrin",     "unit": "g",   "primaryMacro": "carbs",
        "secondaryMacro": None,
        "kcalPerPrimaryUnit": 4.0,
        "perIngredientCapG": 50,
        "protectedMealWindows": ["post_lift"],
        "preferredReductionWindow": "pre_lift",
        "distributionNote": "Reduce pre-lift pool first. Post-lift Dextrin is anabolically timed — protect it.",
    },
    {
        "ingredient": "Oats",        "unit": "g",   "primaryMacro": "carbs",
        "secondaryMacro": "fat",
        "kcalPerPrimaryUnit": 4.0,
        "carbsPerG": 0.67, "fatPerG": 0.06, "proteinPerG": 0.17,
        "perIngredientCapG": 80,
    },
    {
        "ingredient": "Bananas",     "unit": "each","primaryMacro": "carbs",
        "secondaryMacro": None,
        "kcalPerPrimaryUnit": 4.0,
        "carbsPerUnit": 27, "proteinPerUnit": 1, "fatPerUnit": 0,
        "perIngredientCapUnits": 2,
    },
    {
        "ingredient": "Eggs",        "unit": "each","primaryMacro": "protein",
        "secondaryMacro": "fat",
        "kcalPerPrimaryUnit": 4.0,
        "proteinPerUnit": 6, "fatPerUnit": 5, "carbsPerUnit": 0,
        "perIngredientCapUnits": 3,
    },
    {
        "ingredient": "Flaxseed",    "unit": "g",   "primaryMacro": "fat",
        "secondaryMacro": "carbs",
        "kcalPerPrimaryUnit": 9.0,
        "fatPerG": 0.40, "carbsPerG": 0.27, "proteinPerG": 0.20,
        "perIngredientCapG": 30,
    },
    {
        "ingredient": "Whey",        "unit": "g",   "primaryMacro": "protein",
        "secondaryMacro": None,
        "kcalPerPrimaryUnit": 4.0,
        "proteinPerG": 0.80, "carbsPerG": 0.08, "fatPerG": 0.05,
        "perIngredientCapG": 40,
    },
    {
        "ingredient": "Greek Yogurt","unit": "cup", "primaryMacro": "protein",
        "secondaryMacro": None,
        "kcalPerPrimaryUnit": 4.0,
        "perIngredientCapUnits": 1,
    },
]

# Maximum per-macro adjustment distributed across all windows combined.
_WINDOW_CAPS = {"fat": 35, "carbs": 80, "protein": 20}


def _compute_ingredient_adjustments(macro_day: str, macro_delta: dict) -> list:
    """
    Distribute macro delta across ingredients using ranked candidates.
    Each ingredient absorbs min(ingredient_cap, remaining_delta).
    No single ingredient absorbs the full delta.
    Post-lift windows are protected.
    """
    if not macro_delta:
        return []

    remaining = {
        "fat":     min(abs(float(macro_delta.get("fatDeltaG", 0) or 0)),
                       _WINDOW_CAPS["fat"]) * (1 if (macro_delta.get("fatDeltaG") or 0) >= 0 else -1),
        "carbs":   min(abs(float(macro_delta.get("carbsDeltaG", 0) or 0)),
                       _WINDOW_CAPS["carbs"]) * (1 if (macro_delta.get("carbsDeltaG") or 0) >= 0 else -1),
        "protein": min(abs(float(macro_delta.get("proteinDeltaG", 0) or 0)),
                       _WINDOW_CAPS["protein"]) * (1 if (macro_delta.get("proteinDeltaG") or 0) >= 0 else -1),
    }

    adjustments = []
    for item in _INGREDIENT_PRIORITY:
        primary = item["primaryMacro"]
        delta = remaining.get(primary, 0)
        if abs(delta) < 0.5:
            continue

        unit = item["unit"]

        if unit == "g":
            per_g = item.get(f"{primary}PerG", 1.0)
            cap_g = item.get("perIngredientCapG")
            max_delta = (cap_g * per_g) if cap_g else abs(delta)
            allocated_g = min(abs(delta / per_g) if per_g else abs(delta), cap_g or abs(delta))
            if abs(allocated_g) < 1:
                continue
            allocated_g = int(round(allocated_g)) * (1 if delta > 0 else -1)
            allocated_macro = round(allocated_g * per_g, 1)
            display = f"{abs(allocated_g)}g"
            qty = allocated_g
        elif unit == "each":
            per_unit = item.get(f"{primary}PerUnit", 1)
            cap_units = item.get("perIngredientCapUnits")
            units_raw = (delta / per_unit) if per_unit else 1
            units_qty = int(round(units_raw))
            if cap_units:
                units_qty = max(-cap_units, min(cap_units, units_qty))
            if abs(units_qty) < 1:
                continue
            allocated_macro = round(units_qty * per_unit, 1)
            display = f"{abs(units_qty)} unit(s)"
            qty = units_qty
        else:
            allocated_macro = delta
            display = f"1 {unit}"
            qty = 1

        action = "increase" if qty > 0 else "decrease"
        kcal_per_unit = item.get("kcalPerPrimaryUnit", 4.0)
        kcal_delta = round(allocated_macro * kcal_per_unit, 1)

        entry = {
            "priority":           len(adjustments) + 1,
            "ingredient":         item["ingredient"],
            "unit":               unit,
            "action":             action,
            "primaryMacro":       primary,
            "deltaG":             allocated_macro,
            "qty":                abs(qty),
            "kcalPerPrimaryUnit": kcal_per_unit,
            "kcalDelta":          kcal_delta,
            "display":            f"{action} {display}",
        }
        if item.get("protectedMealWindows"):
            entry["protectedMealWindows"]    = item["protectedMealWindows"]
        if item.get("preferredReductionWindow"):
            entry["preferredReductionWindow"] = item["preferredReductionWindow"]
        if item.get("distributionNote"):
            entry["distributionNote"]        = item["distributionNote"]

        adjustments.append(entry)
        remaining[primary] = remaining[primary] - allocated_macro

        if all(abs(v) < 0.5 for v in remaining.values()):
            break

    return adjustments


def _macro_intent(macro_day: str, macro_delta: dict) -> dict:
    """
    Clarifies what the macro day type means for the day's calorie and macro strategy.
    Prevents Expo from conflating a macro-split rebalance with an actual calorie cut/surplus.
    kcalChange: 'stable' | 'reduction' | 'surplus'
    splitChange: describes the directional macro split shift
    applyFrom: 'baseline' — Expo must apply ingredient deltas from the LOCKED BASELINE,
               NOT from the previous day's actual submission.
    """
    kcal_delta = float(macro_delta.get("kcalDelta", 0) or 0) if macro_delta else 0
    carbs_delta = float(macro_delta.get("carbsDeltaG", 0) or 0) if macro_delta else 0
    fat_delta   = float(macro_delta.get("fatDeltaG", 0) or 0) if macro_delta else 0

    if abs(kcal_delta) < 20:
        kcal_change = "stable"
    elif kcal_delta < 0:
        kcal_change = "reduction"
    else:
        kcal_change = "surplus"

    if abs(carbs_delta) >= 10 and abs(fat_delta) >= 5:
        split_change = (
            f"carbs {'down' if carbs_delta < 0 else 'up'} {abs(round(carbs_delta))}g, "
            f"fat {'up' if fat_delta > 0 else 'down'} {abs(round(fat_delta))}g — "
            f"{'iso-caloric rebalance' if kcal_change == 'stable' else 'net calorie shift'}"
        )
    elif abs(carbs_delta) >= 10:
        split_change = f"carbs {'down' if carbs_delta < 0 else 'up'} {abs(round(carbs_delta))}g, fat stable"
    else:
        split_change = "macro split unchanged"

    descriptions = {
        "surge":        "High-output day. Carb surplus loaded front and back. Fat held flat.",
        "build":        "Training day. Moderate carb increase. Fat slightly elevated.",
        "reset":        "Recovery day. Carb reduction, fat increase. Total kcal stable.",
        "resensitize":  "Deload day. Significant carb reduction. Fat increase. Slight kcal decrease.",
    }

    return {
        "kcalChange":    kcal_change,
        "splitChange":   split_change,
        "description":   descriptions.get(macro_day, "Standard macro day."),
        "applyFrom":     "baseline",
        "applyFromNote": (
            "Apply ingredient deltas from the LOCKED BASELINE values, not from "
            "the previous day's actuals. Baseline: 330.9g C / 54.4g F / 173.9g P."
        ),
    }


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
                "macroDay":    macro_day,
                "macroIntent": _macro_intent(macro_day, macro_delta),
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


def _build_raw_inputs(log_row: VitalsDailyLog, refs: dict, baselines: dict,
                      yesterday_lift_strain, yesterday_cardio) -> dict:
    def _f(v):
        return float(v) if v is not None else None

    hrv = _f(log_row.hrv_ms)
    hrv7 = refs.get("hrv7dAvg")
    hrv_ratio = round(hrv / hrv7, 2) if (hrv and hrv7) else None
    hrv_delta = round(hrv - hrv7, 1) if (hrv and hrv7) else None

    rhr = _f(log_row.resting_hr_bpm)
    rhr7 = refs.get("rhr7dAvg")
    rhr_delta = round(rhr - rhr7, 1) if (rhr and rhr7) else None

    sleep_min = _f(log_row.sleep_duration_min)
    midpoint = _f(log_row.sleep_midpoint_min)
    midpoint7 = refs.get("sleepMidpoint7dAvg")
    midpoint_shift = round(abs(midpoint - midpoint7), 1) if (midpoint and midpoint7) else None

    bw = _f(log_row.body_weight_lb)
    bw7 = refs.get("bodyWeight7dAvg")
    bw_delta_pct = round((bw - bw7) / bw7 * 100, 2) if (bw and bw7) else None

    libido = _f(log_row.libido_score)
    erection = _f(log_row.morning_erection_score)
    motivation = _f(log_row.motivation_score)
    mental_drive = _f(log_row.mental_drive_score)
    soreness = _f(log_row.soreness_score)
    joint_friction = _f(log_row.joint_friction_score)

    def _drive_composite():
        vals = []
        if libido is not None:       vals.append((libido - 1) / 4 * 10)
        if erection is not None:     vals.append((erection / 3) * 10)       # 0–3 scale
        if motivation is not None:   vals.append((motivation - 1) / 4 * 10)
        if mental_drive is not None: vals.append((mental_drive - 1) / 4 * 10)
        return round(sum(vals) / len(vals), 1) if vals else None

    def _recovery_comfort():
        vals = []
        if soreness is not None:      vals.append((5 - soreness) / 4 * 10)
        if joint_friction is not None: vals.append((5 - joint_friction) / 4 * 10)
        return round(sum(vals) / len(vals), 1) if vals else None

    kcal_actual = _f(log_row.kcal_actual)
    kcal7 = refs.get("kcal7dAvg")
    kcal_target = _f(log_row.kcal_target) if log_row.kcal_target else _f(baselines.get("default_kcal"))
    kcal7_ratio = round(kcal7 / kcal_target, 2) if (kcal7 and kcal_target) else None

    protein_actual = _f(log_row.protein_g_actual)
    protein7 = refs.get("protein7dAvg")
    fat_actual = _f(log_row.fat_g_actual)
    fat7 = refs.get("fat7dAvg")
    carbs_actual = _f(log_row.carbs_g_actual)
    carbs7 = refs.get("carbs7dAvg")
    carbs_target = _f(log_row.carbs_g_target)
    carbs_ratio = round(carbs7 / carbs_target, 2) if (carbs7 and carbs_target and carbs_target > 0) else None

    waist = _f(log_row.waist_at_navel_in)
    waist_per_lb = round(waist / bw, 3) if (waist and bw) else None

    def _r(v, digits=2):
        return round(v, digits) if v is not None else None

    return {
        "acute": {
            "hrv_ms":                  hrv,
            "hrv_7d_avg":              _r(hrv7, 1),
            "hrv_year_avg":            _f(baselines.get("hrv_year_avg")),
            "hrv_ratio":               hrv_ratio,
            "hrv_delta_ms":            hrv_delta,
            "rhr_bpm":                 rhr,
            "rhr_7d_avg":              _r(rhr7, 1),
            "rhr_year_avg":            _f(baselines.get("rhr_year_avg")),
            "rhr_delta_bpm":           rhr_delta,
            "sleep_duration_min":      sleep_min,
            "sleep_midpoint_min":      midpoint,
            "sleep_midpoint_7d_avg":   _r(midpoint7, 1),
            "sleep_midpoint_shift_min": midpoint_shift,
            "body_weight_lb":          bw,
            "weight_7d_avg_lb":        _r(bw7, 2),
            "weight_delta_pct":        bw_delta_pct,
            "libido_score":            libido,
            "morning_erection_score":  erection,
            "motivation_score":        motivation,
            "mental_drive_score":      mental_drive,
            "drive_composite_0_10":    _drive_composite(),
            "soreness_score":          soreness,
            "joint_friction_score":    joint_friction,
            "recovery_comfort_0_10":   _recovery_comfort(),
            "lift_strain_yesterday":   yesterday_lift_strain,
            "cardio_mode_yesterday":   yesterday_cardio,
        },
        "resource": {
            "kcal_actual_today":           kcal_actual,
            "kcal_7d_avg":                 _r(kcal7, 1),
            "kcal_target":                 kcal_target,
            "kcal_7d_ratio":               kcal7_ratio,
            "protein_g_actual_today":      protein_actual,
            "protein_7d_avg_g":            _r(protein7, 1),
            "fat_g_actual_today":          fat_actual,
            "fat_7d_avg_g":                _r(fat7, 1),
            "carbs_g_actual_today":        carbs_actual,
            "carbs_7d_avg_g":              _r(carbs7, 1),
            "carbs_g_target_today":        carbs_target,
            "carb_adherence_ratio":        carbs_ratio,
            "weight_trend_14d_lb_per_week": _r(refs.get("weightTrend14dLbPerWeek"), 3),
            "waist_change_14d_in":          _r(refs.get("waistChange14dIn"), 3),
            "ffm_trend_14d_lb_per_week":    _r(refs.get("ffmTrend14dLbPerWeek"), 3),
            "strength_trend_14d_pct":       refs.get("strengthTrend14dPct"),
            "zone2_7d":                     refs.get("cardioZone2Count7d"),
            "zone3_7d":                     refs.get("cardioZone3Count7d"),
            "recovery_7d":                  refs.get("cardioRecoveryCount7d"),
        },
        "seasonal": {
            "hrv_28d_avg":                    _r(refs.get("hrv28dAvg"), 1),
            "hrv_prev_28d_avg":               _r(refs.get("hrvPrev28dAvg"), 1),
            "rhr_28d_avg":                    _r(refs.get("rhr28dAvg"), 1),
            "rhr_prev_28d_avg":               _r(refs.get("rhrPrev28dAvg"), 1),
            "sleep_regularity_28d_score":     _r(refs.get("sleepRegularity28dScore"), 1),
            "sleep_regularity_prev_28d_score": _r(refs.get("sleepRegularityPrev28dScore"), 1),
            "waist_per_lb_ratio":             waist_per_lb,
            "ffm_28d_avg":                    _r(refs.get("ffm28dAvg"), 1),
            "ffm_prev_28d_avg":               _r(refs.get("ffmPrev28dAvg"), 1),
            "training_monotony_index_28d":    _r(refs.get("trainingMonotonyIndex28d"), 1),
            "cardio_monotony_28d":            _r(refs.get("cardioMonotony28d"), 1),
            "lift_monotony_28d":              _r(refs.get("liftMonotony28d"), 1),
            "macro_monotony_28d":             _r(refs.get("macroMonotony28d"), 1),
            "virility_trend_28d":             _r(refs.get("virilityTrend28d"), 1),
            "virility_trend_prev_28d":        _r(refs.get("virilityTrendPrev28d"), 1),
            "deload_score_28d":               refs.get("deloadScore28d"),
            "deload_compliance_28d":          refs.get("deloadCompliance28d"),
            "light_exposure_consistency_28d": refs.get("lightExposureConsistency28d"),
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
        fat_high_days_7d=refs["fatHighDays7d"],
        fat_low_days_7d=refs["fatLowDays7d"],
        carb_day_type_adherence_7d=refs["carbDayTypeAdherence7d"],
        carbs_7d_avg=refs["carbs7dAvg"],
        carbs_g_target=float(log_row.carbs_g_target) if log_row.carbs_g_target else None,
        weight_trend_14d_lb_per_week=refs["weightTrend14dLbPerWeek"],
        waist_change_14d_in=refs["waistChange14dIn"],
        ffm_trend_14d_lb_per_week=refs["ffmTrend14dLbPerWeek"],
        strength_trend_14d_pct=refs["strengthTrend14dPct"],
        zone2_count_7d=refs["cardioZone2Count7d"],
        zone3_count_7d=refs["cardioZone3Count7d"],
        recovery_count_7d=refs["cardioRecoveryCount7d"],
        ffm_trend_confidence=refs.get("ffmTrend14dConfidence"),
        waist_trend_confidence=refs.get("waistTrendConfidence"),
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
        deload_score_28d=refs["deloadScore28d"],
        deload_compliance_28d=refs["deloadCompliance28d"],
        training_monotony_index_28d=refs["trainingMonotonyIndex28d"],
        light_exposure_consistency_28d=refs["lightExposureConsistency28d"],
        virility_trend_28d=refs["virilityTrend28d"],
        cardio_monotony_28d=refs.get("cardioMonotony28d"),
        lift_monotony_28d=refs.get("liftMonotony28d"),
        macro_monotony_28d=refs.get("macroMonotony28d"),
        virility_trend_prev_28d=refs.get("virilityTrendPrev28d"),
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

    # Sequential zone3 cap — check previous two days
    two_days_ago = target_date - timedelta(days=2)
    two_days_ago_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == two_days_ago,
    ).first()
    yesterday_was_z3 = yesterday_row and yesterday_row.actual_cardio_mode == "zone_3"
    two_days_ago_was_z3 = two_days_ago_row and two_days_ago_row.actual_cardio_mode == "zone_3"
    previous_two_zone3 = bool(yesterday_was_z3 and two_days_ago_was_z3)

    cardio_mode = _decide_cardio(
        composite["compositeScore"], flags,
        refs["cardioZone3Count7d"], refs["cardioZone2Count7d"],
        hrv_ms=log_row.hrv_ms, hrv_7d_avg=refs.get("hrv7dAvg"),
        resting_hr_bpm=log_row.resting_hr_bpm, rhr_7d_avg=refs.get("rhr7dAvg"),
        previous_two_zone3=previous_two_zone3,
    )
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

    raw_inputs = _build_raw_inputs(log_row, refs, baselines, yesterday_lift_strain, yesterday_cardio)

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
        "rawInputs": raw_inputs,
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
    existing.rolling_reset_day_count_28d = sum(
        1 for dt in refs.get("recentMacroDayTypes7d", [])
        if dt in ("reset", "resensitize")
    )
    existing.fatigue_flag = result["flags"]["hardStopFatigue"]
    existing.monotony_flag = result["flags"]["cardioMonotony"]
    existing.deload_compliance_flag = refs["deloadCompliance28d"]
    existing.acute_breakdown = result["acuteResult"]["breakdown"]
    existing.resource_breakdown = result["resourceResult"]["breakdown"]
    existing.seasonal_breakdown = result["seasonalResult"]["breakdown"]
    db.commit()
