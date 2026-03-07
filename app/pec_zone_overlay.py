"""
Pec Zone Micro-Matrix Overlay — per-exercise biomechanical feature table.

This is a sidecar-only data layer for the pec-zone analytics system.
It does NOT modify the canonical 27-region muscle schema, seed CSVs,
balance/recovery/optimizer logic, or any frontend-facing response shapes.

Architecture:
    The overlay stores per-exercise biomechanical coefficients (0.0–1.0)
    that describe movement characteristics relevant to pectoral-zone
    partitioning.  A formula converts these features into normalized
    upper/mid/lower pec shares at runtime.  The canonical Pectorals dose
    is the source of truth — the overlay only redistributes it.

Data provenance note:
    With current exercise data, the canonical activation matrices give
    uniform front-delt and triceps signals across all pec exercises, and
    V3 phase data is near-uniform (5/5/4).  The overlay coefficients are
    authored biomechanics priors informed by EMG literature and movement
    analysis, not newly measured differentiation from the canonical
    matrices.  This is primarily a structural and explainability upgrade
    that encodes *why* an exercise biases toward a pec zone, enabling
    future refinement and personalization.
"""

FORMULA_WEIGHTS = {
    "fd_to_upper": 0.08,
    "stretch_to_upper": 0.05,
    "decline_neg_upper": 0.05,
    "adduction_to_mid": 0.08,
    "convergence_to_mid": 0.05,
    "decline_to_lower": 0.08,
    "triceps_to_lower": 0.05,
    "fd_neg_lower": 0.05,
}

EXERCISE_OVERLAY = {
    "Incline Barbell Bench Press": {
        "upper_bias": 0.55, "mid_bias": 0.30, "lower_bias": 0.15,
        "stretch_bias": 0.50, "front_delt_coupling": 0.65,
        "triceps_coupling": 0.40, "adduction_bias": 0.10,
        "decline_vector_bias": 0.00, "convergence_bias": 0.10,
        "confidence": 0.90, "archetype": "incline_press",
    },
    "Incline Dumbbell Bench Press": {
        "upper_bias": 0.58, "mid_bias": 0.27, "lower_bias": 0.15,
        "stretch_bias": 0.65, "front_delt_coupling": 0.65,
        "triceps_coupling": 0.35, "adduction_bias": 0.20,
        "decline_vector_bias": 0.00, "convergence_bias": 0.25,
        "confidence": 0.90, "archetype": "incline_press",
    },
    "Flat Barbell Bench Press": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.50, "front_delt_coupling": 0.40,
        "triceps_coupling": 0.55, "adduction_bias": 0.30,
        "decline_vector_bias": 0.10, "convergence_bias": 0.15,
        "confidence": 0.92, "archetype": "flat_press",
    },
    "Flat Dumbbell Bench Press": {
        "upper_bias": 0.27, "mid_bias": 0.48, "lower_bias": 0.25,
        "stretch_bias": 0.65, "front_delt_coupling": 0.38,
        "triceps_coupling": 0.50, "adduction_bias": 0.35,
        "decline_vector_bias": 0.10, "convergence_bias": 0.30,
        "confidence": 0.90, "archetype": "flat_press",
    },
    "Machine Chest Press": {
        "upper_bias": 0.28, "mid_bias": 0.50, "lower_bias": 0.22,
        "stretch_bias": 0.30, "front_delt_coupling": 0.35,
        "triceps_coupling": 0.50, "adduction_bias": 0.25,
        "decline_vector_bias": 0.10, "convergence_bias": 0.40,
        "confidence": 0.75, "archetype": "flat_press",
    },
    "Decline Bench Press": {
        "upper_bias": 0.12, "mid_bias": 0.30, "lower_bias": 0.58,
        "stretch_bias": 0.50, "front_delt_coupling": 0.25,
        "triceps_coupling": 0.60, "adduction_bias": 0.20,
        "decline_vector_bias": 0.85, "convergence_bias": 0.15,
        "confidence": 0.88, "archetype": "decline_press",
    },
    "Decline Barbell Bench Press": {
        "upper_bias": 0.12, "mid_bias": 0.30, "lower_bias": 0.58,
        "stretch_bias": 0.50, "front_delt_coupling": 0.25,
        "triceps_coupling": 0.60, "adduction_bias": 0.20,
        "decline_vector_bias": 0.85, "convergence_bias": 0.15,
        "confidence": 0.88, "archetype": "decline_press",
    },
    "Decline Dumbbell Bench Press": {
        "upper_bias": 0.12, "mid_bias": 0.28, "lower_bias": 0.60,
        "stretch_bias": 0.65, "front_delt_coupling": 0.22,
        "triceps_coupling": 0.55, "adduction_bias": 0.25,
        "decline_vector_bias": 0.85, "convergence_bias": 0.25,
        "confidence": 0.88, "archetype": "decline_press",
    },
    "Weighted Dips": {
        "upper_bias": 0.10, "mid_bias": 0.25, "lower_bias": 0.65,
        "stretch_bias": 0.60, "front_delt_coupling": 0.20,
        "triceps_coupling": 0.70, "adduction_bias": 0.15,
        "decline_vector_bias": 0.90, "convergence_bias": 0.05,
        "confidence": 0.82, "archetype": "dip",
    },
    "Parallel Bar Dips (chest-focused)": {
        "upper_bias": 0.10, "mid_bias": 0.25, "lower_bias": 0.65,
        "stretch_bias": 0.65, "front_delt_coupling": 0.22,
        "triceps_coupling": 0.65, "adduction_bias": 0.15,
        "decline_vector_bias": 0.90, "convergence_bias": 0.05,
        "confidence": 0.85, "archetype": "dip",
    },
    "Parallel Bar Dips (tricep-focused)": {
        "upper_bias": 0.12, "mid_bias": 0.28, "lower_bias": 0.60,
        "stretch_bias": 0.40, "front_delt_coupling": 0.18,
        "triceps_coupling": 0.80, "adduction_bias": 0.10,
        "decline_vector_bias": 0.80, "convergence_bias": 0.05,
        "confidence": 0.80, "archetype": "dip",
    },
    "Ring Dips": {
        "upper_bias": 0.10, "mid_bias": 0.28, "lower_bias": 0.62,
        "stretch_bias": 0.70, "front_delt_coupling": 0.22,
        "triceps_coupling": 0.60, "adduction_bias": 0.20,
        "decline_vector_bias": 0.85, "convergence_bias": 0.10,
        "confidence": 0.78, "archetype": "dip",
    },
    "Chest Fly": {
        "upper_bias": 0.30, "mid_bias": 0.45, "lower_bias": 0.25,
        "stretch_bias": 0.70, "front_delt_coupling": 0.30,
        "triceps_coupling": 0.15, "adduction_bias": 0.80,
        "decline_vector_bias": 0.05, "convergence_bias": 0.50,
        "confidence": 0.85, "archetype": "fly_midline",
    },
    "Cable Fly High-to-Low": {
        "upper_bias": 0.15, "mid_bias": 0.25, "lower_bias": 0.60,
        "stretch_bias": 0.55, "front_delt_coupling": 0.15,
        "triceps_coupling": 0.20, "adduction_bias": 0.75,
        "decline_vector_bias": 0.70, "convergence_bias": 0.35,
        "confidence": 0.85, "archetype": "fly_high_to_low",
    },
    "Cable Fly Midline": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.65, "front_delt_coupling": 0.30,
        "triceps_coupling": 0.15, "adduction_bias": 0.85,
        "decline_vector_bias": 0.05, "convergence_bias": 0.55,
        "confidence": 0.85, "archetype": "fly_midline",
    },
    "Cable Fly Low-to-High": {
        "upper_bias": 0.60, "mid_bias": 0.25, "lower_bias": 0.15,
        "stretch_bias": 0.55, "front_delt_coupling": 0.55,
        "triceps_coupling": 0.10, "adduction_bias": 0.75,
        "decline_vector_bias": 0.00, "convergence_bias": 0.40,
        "confidence": 0.85, "archetype": "fly_low_to_high",
    },
    "Push-Up": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.45, "front_delt_coupling": 0.35,
        "triceps_coupling": 0.45, "adduction_bias": 0.25,
        "decline_vector_bias": 0.10, "convergence_bias": 0.10,
        "confidence": 0.80, "archetype": "pushup_flat",
    },
    "Weighted Push-Up": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.50, "front_delt_coupling": 0.35,
        "triceps_coupling": 0.45, "adduction_bias": 0.25,
        "decline_vector_bias": 0.10, "convergence_bias": 0.10,
        "confidence": 0.82, "archetype": "pushup_flat",
    },
    "Decline Push-Up": {
        "upper_bias": 0.15, "mid_bias": 0.30, "lower_bias": 0.55,
        "stretch_bias": 0.45, "front_delt_coupling": 0.22,
        "triceps_coupling": 0.50, "adduction_bias": 0.20,
        "decline_vector_bias": 0.70, "convergence_bias": 0.10,
        "confidence": 0.78, "archetype": "pushup_decline",
    },
    "Incline Push-Up": {
        "upper_bias": 0.45, "mid_bias": 0.35, "lower_bias": 0.20,
        "stretch_bias": 0.40, "front_delt_coupling": 0.50,
        "triceps_coupling": 0.40, "adduction_bias": 0.20,
        "decline_vector_bias": 0.00, "convergence_bias": 0.10,
        "confidence": 0.78, "archetype": "pushup_incline",
    },
    "Close-Grip Bench Press": {
        "upper_bias": 0.20, "mid_bias": 0.45, "lower_bias": 0.35,
        "stretch_bias": 0.40, "front_delt_coupling": 0.30,
        "triceps_coupling": 0.75, "adduction_bias": 0.20,
        "decline_vector_bias": 0.15, "convergence_bias": 0.10,
        "confidence": 0.85, "archetype": "flat_press",
    },
    "Floor Press": {
        "upper_bias": 0.22, "mid_bias": 0.50, "lower_bias": 0.28,
        "stretch_bias": 0.20, "front_delt_coupling": 0.38,
        "triceps_coupling": 0.55, "adduction_bias": 0.15,
        "decline_vector_bias": 0.10, "convergence_bias": 0.10,
        "confidence": 0.80, "archetype": "flat_press",
    },
    "Board Press / Pin Press": {
        "upper_bias": 0.22, "mid_bias": 0.50, "lower_bias": 0.28,
        "stretch_bias": 0.15, "front_delt_coupling": 0.38,
        "triceps_coupling": 0.60, "adduction_bias": 0.15,
        "decline_vector_bias": 0.10, "convergence_bias": 0.10,
        "confidence": 0.75, "archetype": "flat_press",
    },
    "Spoto Press": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.55, "front_delt_coupling": 0.40,
        "triceps_coupling": 0.50, "adduction_bias": 0.20,
        "decline_vector_bias": 0.10, "convergence_bias": 0.15,
        "confidence": 0.80, "archetype": "flat_press",
    },
}

ARCHETYPE_OVERLAY = {
    "incline_press": {
        "upper_bias": 0.55, "mid_bias": 0.30, "lower_bias": 0.15,
        "stretch_bias": 0.50, "front_delt_coupling": 0.60,
        "triceps_coupling": 0.40, "adduction_bias": 0.10,
        "decline_vector_bias": 0.00, "convergence_bias": 0.10,
        "confidence": 0.65,
    },
    "flat_press": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.45, "front_delt_coupling": 0.38,
        "triceps_coupling": 0.52, "adduction_bias": 0.25,
        "decline_vector_bias": 0.10, "convergence_bias": 0.15,
        "confidence": 0.60,
    },
    "decline_press": {
        "upper_bias": 0.12, "mid_bias": 0.30, "lower_bias": 0.58,
        "stretch_bias": 0.50, "front_delt_coupling": 0.25,
        "triceps_coupling": 0.58, "adduction_bias": 0.20,
        "decline_vector_bias": 0.82, "convergence_bias": 0.15,
        "confidence": 0.60,
    },
    "dip": {
        "upper_bias": 0.10, "mid_bias": 0.25, "lower_bias": 0.65,
        "stretch_bias": 0.55, "front_delt_coupling": 0.20,
        "triceps_coupling": 0.68, "adduction_bias": 0.12,
        "decline_vector_bias": 0.88, "convergence_bias": 0.05,
        "confidence": 0.55,
    },
    "fly_low_to_high": {
        "upper_bias": 0.60, "mid_bias": 0.25, "lower_bias": 0.15,
        "stretch_bias": 0.55, "front_delt_coupling": 0.50,
        "triceps_coupling": 0.10, "adduction_bias": 0.72,
        "decline_vector_bias": 0.00, "convergence_bias": 0.38,
        "confidence": 0.58,
    },
    "fly_midline": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.65, "front_delt_coupling": 0.28,
        "triceps_coupling": 0.15, "adduction_bias": 0.80,
        "decline_vector_bias": 0.05, "convergence_bias": 0.50,
        "confidence": 0.58,
    },
    "fly_high_to_low": {
        "upper_bias": 0.15, "mid_bias": 0.25, "lower_bias": 0.60,
        "stretch_bias": 0.52, "front_delt_coupling": 0.15,
        "triceps_coupling": 0.18, "adduction_bias": 0.72,
        "decline_vector_bias": 0.68, "convergence_bias": 0.32,
        "confidence": 0.58,
    },
    "pushup_flat": {
        "upper_bias": 0.25, "mid_bias": 0.50, "lower_bias": 0.25,
        "stretch_bias": 0.42, "front_delt_coupling": 0.35,
        "triceps_coupling": 0.45, "adduction_bias": 0.22,
        "decline_vector_bias": 0.10, "convergence_bias": 0.10,
        "confidence": 0.55,
    },
    "pushup_decline": {
        "upper_bias": 0.15, "mid_bias": 0.30, "lower_bias": 0.55,
        "stretch_bias": 0.42, "front_delt_coupling": 0.22,
        "triceps_coupling": 0.48, "adduction_bias": 0.18,
        "decline_vector_bias": 0.65, "convergence_bias": 0.08,
        "confidence": 0.52,
    },
    "pushup_incline": {
        "upper_bias": 0.45, "mid_bias": 0.35, "lower_bias": 0.20,
        "stretch_bias": 0.38, "front_delt_coupling": 0.48,
        "triceps_coupling": 0.38, "adduction_bias": 0.18,
        "decline_vector_bias": 0.00, "convergence_bias": 0.08,
        "confidence": 0.52,
    },
    "neutral_press": {
        "upper_bias": 0.33, "mid_bias": 0.34, "lower_bias": 0.33,
        "stretch_bias": 0.35, "front_delt_coupling": 0.35,
        "triceps_coupling": 0.45, "adduction_bias": 0.20,
        "decline_vector_bias": 0.10, "convergence_bias": 0.10,
        "confidence": 0.30,
    },
}

_FEATURE_KEYS = [
    "upper_bias", "mid_bias", "lower_bias",
    "stretch_bias", "front_delt_coupling", "triceps_coupling",
    "adduction_bias", "decline_vector_bias", "convergence_bias",
]


def compute_shares_from_features(features):
    w = FORMULA_WEIGHTS
    upper = (features["upper_bias"]
             + w["fd_to_upper"] * features["front_delt_coupling"]
             + w["stretch_to_upper"] * features["stretch_bias"]
             - w["decline_neg_upper"] * features["decline_vector_bias"])
    mid = (features["mid_bias"]
           + w["adduction_to_mid"] * features["adduction_bias"]
           + w["convergence_to_mid"] * features["convergence_bias"])
    lower = (features["lower_bias"]
             + w["decline_to_lower"] * features["decline_vector_bias"]
             + w["triceps_to_lower"] * features["triceps_coupling"]
             - w["fd_neg_lower"] * features["front_delt_coupling"])

    upper = max(upper, 0.0)
    mid = max(mid, 0.0)
    lower = max(lower, 0.0)
    total = upper + mid + lower
    if total <= 0:
        return {"upper": 0.33, "mid": 0.34, "lower": 0.33}
    return {"upper": upper / total, "mid": mid / total, "lower": lower / total}


def _identify_primary_driver(features):
    zones = {"upper": features["upper_bias"], "mid": features["mid_bias"], "lower": features["lower_bias"]}
    dominant_zone = max(zones, key=zones.get)
    modifiers = {
        "front_delt_coupling": features["front_delt_coupling"],
        "stretch_bias": features["stretch_bias"],
        "triceps_coupling": features["triceps_coupling"],
        "adduction_bias": features["adduction_bias"],
        "decline_vector_bias": features["decline_vector_bias"],
        "convergence_bias": features["convergence_bias"],
    }
    top_modifier = max(modifiers, key=modifiers.get)
    return dominant_zone, top_modifier


def get_overlay_result(exercise_name, archetype_hint=None):
    entry = EXERCISE_OVERLAY.get(exercise_name)
    if entry:
        features = {k: entry[k] for k in _FEATURE_KEYS}
        shares = compute_shares_from_features(features)
        confidence = entry["confidence"]
        dominant_zone, top_modifier = _identify_primary_driver(features)
        return shares, "overlay_exact", features, confidence, {
            "dominant_zone": dominant_zone,
            "top_modifier": top_modifier,
            "archetype": entry.get("archetype"),
        }

    arch = archetype_hint
    if arch and arch in ARCHETYPE_OVERLAY:
        entry = ARCHETYPE_OVERLAY[arch]
        features = {k: entry[k] for k in _FEATURE_KEYS}
        shares = compute_shares_from_features(features)
        confidence = entry["confidence"]
        dominant_zone, top_modifier = _identify_primary_driver(features)
        return shares, f"overlay_archetype:{arch}", features, confidence, {
            "dominant_zone": dominant_zone,
            "top_modifier": top_modifier,
            "archetype": arch,
        }

    entry = ARCHETYPE_OVERLAY["neutral_press"]
    features = {k: entry[k] for k in _FEATURE_KEYS}
    shares = compute_shares_from_features(features)
    confidence = entry["confidence"]
    return shares, "overlay_neutral_fallback", features, confidence, {
        "dominant_zone": "mid",
        "top_modifier": "triceps_coupling",
        "archetype": None,
    }
