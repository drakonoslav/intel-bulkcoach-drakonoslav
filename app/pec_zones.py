import re
from app.pec_zone_profiles import EXERCISE_PROFILES, ARCHETYPE_DEFAULTS, NEUTRAL_DEFAULT


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _renormalize(shares):
    total = shares["upper"] + shares["mid"] + shares["lower"]
    if total <= 0:
        return {"upper": 0.33, "mid": 0.34, "lower": 0.33}
    return {k: v / total for k, v in shares.items()}


def _apply_floor_and_normalize(shares, floor=0.10):
    shares = {k: max(floor, v) for k, v in shares.items()}
    return _renormalize(shares)


def _infer_archetype(exercise_name):
    name = exercise_name.lower()

    if "dip" in name:
        return "dip"

    is_press = "bench" in name or "press" in name
    is_pushup = "push-up" in name or "pushup" in name or "push up" in name

    if is_pushup:
        if "decline" in name:
            return "pushup_decline"
        if "incline" in name:
            return "pushup_incline"
        return "pushup_flat"

    if "fly" in name or "flye" in name:
        if "low to high" in name or "low-to-high" in name:
            return "fly_low_to_high"
        if "high to low" in name or "high-to-low" in name:
            return "fly_high_to_low"
        return "fly_midline"

    if is_press:
        if "incline" in name:
            return "incline_press"
        if "decline" in name:
            return "decline_press"
        return "flat_press"

    return None


def get_base_pec_zone_shares(exercise_name):
    profile = EXERCISE_PROFILES.get(exercise_name)
    if profile:
        return {
            "upper": profile["upper"],
            "mid": profile["mid"],
            "lower": profile["lower"],
        }, "exercise_exact_match"

    archetype = _infer_archetype(exercise_name)
    if archetype and archetype in ARCHETYPE_DEFAULTS:
        return dict(ARCHETYPE_DEFAULTS[archetype]), f"archetype_inferred:{archetype}"

    return dict(NEUTRAL_DEFAULT), "neutral_default"


def adjust_pec_zone_shares(base, front_delt_signal, triceps_signal):
    proxy_total = front_delt_signal + triceps_signal
    if proxy_total <= 0:
        return _apply_floor_and_normalize(base), False

    fd_ratio = front_delt_signal / proxy_total
    tri_ratio = triceps_signal / proxy_total
    raw_shift = fd_ratio - tri_ratio

    upper_delta = _clamp(raw_shift * 0.10, -0.08, 0.08)
    lower_delta = _clamp((-raw_shift) * 0.10, -0.08, 0.08)
    mid_delta = -0.5 * (upper_delta + lower_delta)

    adjusted = {
        "upper": base["upper"] + upper_delta,
        "mid": base["mid"] + mid_delta,
        "lower": base["lower"] + lower_delta,
    }
    proxy_applied = abs(raw_shift) > 1e-9
    return _apply_floor_and_normalize(adjusted), proxy_applied


def allocate_pec_zones_for_signal(
    exercise_name,
    pectorals_total_dose,
    pectorals_direct_dose,
    front_delt_signal,
    triceps_signal,
):
    base, source = get_base_pec_zone_shares(exercise_name)
    shares, proxy_applied = adjust_pec_zone_shares(
        base,
        front_delt_signal=front_delt_signal,
        triceps_signal=triceps_signal,
    )

    total_dose = {
        "upper": pectorals_total_dose * shares["upper"],
        "mid": pectorals_total_dose * shares["mid"],
        "lower": pectorals_total_dose * shares["lower"],
    }
    direct_dose = {
        "upper": pectorals_direct_dose * shares["upper"],
        "mid": pectorals_direct_dose * shares["mid"],
        "lower": pectorals_direct_dose * shares["lower"],
    }

    return {
        "shares": shares,
        "total_dose": total_dose,
        "direct_dose": direct_dose,
        "meta": {
            "base_profile_source": source,
            "proxy_adjustment_applied": proxy_applied,
            "front_delt_signal": round(front_delt_signal, 4),
            "triceps_signal": round(triceps_signal, 4),
        },
    }


def aggregate_pec_zones(records):
    agg_total = {"upper": 0.0, "mid": 0.0, "lower": 0.0}
    agg_direct = {"upper": 0.0, "mid": 0.0, "lower": 0.0}

    for rec in records:
        for zone in ("upper", "mid", "lower"):
            agg_total[zone] += rec["total_dose"][zone]
            agg_direct[zone] += rec["direct_dose"][zone]

    total_sum = agg_total["upper"] + agg_total["mid"] + agg_total["lower"]
    shares = {}
    if total_sum > 0:
        shares = {z: agg_total[z] / total_sum for z in ("upper", "mid", "lower")}
    else:
        shares = {"upper": 0.33, "mid": 0.34, "lower": 0.33}

    return {
        "total_dose": agg_total,
        "direct_dose": agg_direct,
        "shares": shares,
    }
