"""
Pec Zone Proxy Allocator — v2.5 (overlay)

Partitions canonical Pectorals dose into Upper/Mid/Lower Pec proxy zones.
This is a sidecar analytics layer; it does NOT alter the canonical 27-region
muscle schema, balance logic, recovery maps, or optimizer vectors.

v2.5 pipeline (applied in order):
    1. Overlay — per-exercise biomechanical feature coefficients converted to
       shares via weighted formula.  Replaces the hardcoded profile dict from v2.
    2. Geometry adjustment — movement geometry classification (small blend)
    3. Phase adjustment — V3 phase activation ratios (init/mid/lock)
    4. Proxy adjustment — front-delt vs triceps stabilizer ratio
    5. Grip adjustment — grip-width inference from exercise name
    6. Floor + renormalize — ensure minimum 0.10 per zone, sum to 1.0

Data provenance note:
    The overlay coefficients are authored biomechanics priors, not newly measured
    differentiation from the canonical matrices.  With current exercise data, the
    canonical activation matrices give uniform fd/tri signals and near-uniform
    phase data (5/5/4).  This is primarily a structural and explainability
    upgrade that encodes *why* an exercise biases toward a pec zone, enabling
    future refinement and personalization.

Conservation invariant (enforced at every level):
    upper_share + mid_share + lower_share = 1.0
    upper_dose + mid_dose + lower_dose = pectorals_dose
"""

from app.pec_zone_overlay import get_overlay_result
from app.exercise_geometry import (
    classify_geometry,
    infer_grip_class,
    GEOMETRY_BASE_SHARES,
    GRIP_ADJUSTMENTS,
    GEOMETRY_NEUTRAL_PRESS,
)


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
    archetype_hint = _infer_archetype(exercise_name)
    shares, source, features, confidence, drivers = get_overlay_result(
        exercise_name, archetype_hint=archetype_hint,
    )
    return shares, source, features, confidence, drivers


def apply_geometry_adjustment(shares, exercise_name):
    geometry = classify_geometry(exercise_name)
    geo_base = GEOMETRY_BASE_SHARES.get(geometry, GEOMETRY_BASE_SHARES[GEOMETRY_NEUTRAL_PRESS])

    blend_weight = 0.15

    adjusted = {
        z: shares[z] + blend_weight * (geo_base[z] - shares[z])
        for z in ("upper", "mid", "lower")
    }
    return _renormalize(adjusted), geometry


def apply_phase_adjustment(shares, pec_init, pec_mid, pec_lock):
    phase_total = pec_init + pec_mid + pec_lock
    if phase_total <= 0:
        return dict(shares), False

    init_ratio = pec_init / phase_total
    mid_ratio = pec_mid / phase_total
    lock_ratio = pec_lock / phase_total

    even = 1.0 / 3.0
    scale = 0.10

    upper_delta = _clamp((init_ratio - even) * scale, -0.06, 0.06)
    mid_delta = _clamp((mid_ratio - even) * scale, -0.06, 0.06)
    lower_delta = _clamp((lock_ratio - even) * scale, -0.06, 0.06)

    adjusted = {
        "upper": shares["upper"] + upper_delta,
        "mid": shares["mid"] + mid_delta,
        "lower": shares["lower"] + lower_delta,
    }
    applied = abs(upper_delta) > 1e-9 or abs(mid_delta) > 1e-9 or abs(lower_delta) > 1e-9
    return _renormalize(adjusted), applied


def apply_proxy_adjustment(shares, front_delt_signal, triceps_signal):
    proxy_total = front_delt_signal + triceps_signal
    if proxy_total <= 0:
        return dict(shares), False

    fd_ratio = front_delt_signal / proxy_total
    tri_ratio = triceps_signal / proxy_total
    raw_shift = fd_ratio - tri_ratio

    upper_delta = _clamp(raw_shift * 0.08, -0.08, 0.08)
    lower_delta = _clamp((-raw_shift) * 0.08, -0.08, 0.08)
    mid_delta = -(upper_delta + lower_delta) * 0.5

    adjusted = {
        "upper": shares["upper"] + upper_delta,
        "mid": shares["mid"] + mid_delta,
        "lower": shares["lower"] + lower_delta,
    }
    applied = abs(raw_shift) > 1e-9
    return _renormalize(adjusted), applied


def apply_grip_adjustment(shares, exercise_name):
    grip_class = infer_grip_class(exercise_name)
    if grip_class is None or grip_class not in GRIP_ADJUSTMENTS:
        return dict(shares), None

    adj = GRIP_ADJUSTMENTS[grip_class]
    adjusted = {
        "upper": shares["upper"] + adj["upper"],
        "mid": shares["mid"] + adj["mid"],
        "lower": shares["lower"] + adj["lower"],
    }
    return _renormalize(adjusted), grip_class


def compute_v2_shares(exercise_name, front_delt_signal, triceps_signal,
                      pec_init=0.0, pec_mid=0.0, pec_lock=0.0):
    base, source, overlay_features, overlay_confidence, overlay_drivers = \
        get_base_pec_zone_shares(exercise_name)

    geo_shares, geometry = apply_geometry_adjustment(dict(base), exercise_name)

    phase_shares, phase_applied = apply_phase_adjustment(
        dict(geo_shares), pec_init, pec_mid, pec_lock
    )

    proxy_shares, proxy_applied = apply_proxy_adjustment(
        dict(phase_shares), front_delt_signal, triceps_signal
    )

    grip_shares, grip_class = apply_grip_adjustment(dict(proxy_shares), exercise_name)

    final = _apply_floor_and_normalize(grip_shares)

    adjustments = {
        "overlay": {
            "source": source,
            "features": {k: round(v, 4) for k, v in overlay_features.items()},
            "computed_shares": {k: round(v, 6) for k, v in base.items()},
        },
        "geometry": {"geometry": geometry, "shares_after": {k: round(v, 6) for k, v in geo_shares.items()}},
        "phase": {"applied": phase_applied, "pec_init": pec_init, "pec_mid": pec_mid, "pec_lock": pec_lock,
                  "shares_after": {k: round(v, 6) for k, v in phase_shares.items()}},
        "proxy": {"applied": proxy_applied, "front_delt_signal": round(front_delt_signal, 4),
                  "triceps_signal": round(triceps_signal, 4),
                  "shares_after": {k: round(v, 6) for k, v in proxy_shares.items()}},
        "grip": {"grip_class": grip_class, "shares_after": {k: round(v, 6) for k, v in grip_shares.items()}},
    }

    return final, source, adjustments, overlay_confidence, overlay_drivers


def allocate_pec_zones_for_signal(
    exercise_name,
    pectorals_total_dose,
    pectorals_direct_dose,
    front_delt_signal,
    triceps_signal,
    pec_init=0.0,
    pec_mid=0.0,
    pec_lock=0.0,
):
    shares, source, adjustments, confidence, drivers = compute_v2_shares(
        exercise_name, front_delt_signal, triceps_signal,
        pec_init, pec_mid, pec_lock,
    )

    total_dose = {z: pectorals_total_dose * shares[z] for z in ("upper", "mid", "lower")}
    direct_dose = {z: pectorals_direct_dose * shares[z] for z in ("upper", "mid", "lower")}

    return {
        "shares": shares,
        "total_dose": total_dose,
        "direct_dose": direct_dose,
        "confidence": round(confidence, 4),
        "drivers": drivers,
        "meta": {
            "base_profile_source": source,
            "geometry": adjustments["geometry"]["geometry"],
            "phase_adjustment_applied": adjustments["phase"]["applied"],
            "proxy_adjustment_applied": adjustments["proxy"]["applied"],
            "grip_class": adjustments["grip"]["grip_class"],
            "front_delt_signal": adjustments["proxy"]["front_delt_signal"],
            "triceps_signal": adjustments["proxy"]["triceps_signal"],
        },
        "_adjustments": adjustments,
    }


def aggregate_pec_zones(records):
    agg_total = {"upper": 0.0, "mid": 0.0, "lower": 0.0}
    agg_direct = {"upper": 0.0, "mid": 0.0, "lower": 0.0}

    conf_weighted_sum = 0.0
    dose_weight_sum = 0.0

    for rec in records:
        rec_dose = sum(rec["total_dose"][z] for z in ("upper", "mid", "lower"))
        for zone in ("upper", "mid", "lower"):
            agg_total[zone] += rec["total_dose"][zone]
            agg_direct[zone] += rec["direct_dose"][zone]
        conf_weighted_sum += rec.get("confidence", 0.5) * rec_dose
        dose_weight_sum += rec_dose

    total_sum = agg_total["upper"] + agg_total["mid"] + agg_total["lower"]
    if total_sum > 0:
        shares = {z: agg_total[z] / total_sum for z in ("upper", "mid", "lower")}
    else:
        shares = {"upper": 0.33, "mid": 0.34, "lower": 0.33}

    avg_confidence = conf_weighted_sum / dose_weight_sum if dose_weight_sum > 0 else 0.30

    return {
        "total_dose": agg_total,
        "direct_dose": agg_direct,
        "shares": shares,
        "confidence": round(avg_confidence, 4),
    }
