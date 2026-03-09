"""
Biomechanics v2 Contract — Frozen Enums, Validation, and Documentation

This module defines the authoritative contract for exercise biomechanics data.
All future exercise batches MUST pass validate_exercise_batch() before seeding.
"""

CATALOG_REVISION = "2026-03-09T22:40:00Z"

IMPLEMENT_TYPES = frozenset({
    "barbell", "dumbbell", "bodyweight", "cable", "machine",
    "kettlebell", "band", "sled", "sandbag", "tire", "yoke",
})

BODY_POSITIONS = frozenset({
    "standing", "seated", "supine", "prone", "incline", "decline",
    "hanging", "inverted", "kneeling", "side_lying",
})

LATERALITIES = frozenset({"bilateral", "unilateral", "alternating"})

RESISTANCE_ORIGINS = frozenset({
    "gravity", "floor", "low", "mid", "high", "overhead", "elastic",
})

RESISTANCE_DIRECTIONS = frozenset({
    "vertical", "horizontal", "diagonal_low_high",
    "diagonal_high_low", "rotational",
})

GRIP_STYLES = frozenset({
    "overhand", "underhand", "neutral", "mixed", "false",
    "rope", "handle",
})

HUMERAL_PLANES = frozenset({"sagittal", "frontal", "scapular", "transverse"})

ELBOW_PATHS = frozenset({"fixed", "free", "tracking"})

MOVEMENT_FAMILIES = frozenset({
    "press", "row", "fly", "curl", "extension", "raise",
    "squat", "hinge", "lunge", "thrust", "carry", "pull",
    "dip", "olympic", "complex", "push",
})

PATTERN_CLASSES = frozenset({
    "compound", "isolation", "carry", "ballistic", "olympic",
})

METADATA_TIERS = frozenset({"core", "extended", "full"})

EXERCISE_SLOTS = frozenset({"hinge", "squat", "push", "pull", "carry", "oly"})

CANONICAL_MUSCLES = [
    "Forearms", "Biceps", "Triceps", "Deltoids", "Front/Anterior Delt",
    "Rear/Posterior Delt", "Side/Lateral Delt", "Neck", "Traps",
    "Upper Traps", "Mid Traps", "Lower Traps", "Upper Back",
    "Middle Back", "Lower Back", "Lats", "Pectorals", "Obliques",
    "Abs", "Glutes", "Adductors", "Abductors", "Quads",
    "Hamstrings", "Shins", "Calves", "Hands/Grip",
]

TIER_REQUIREMENTS = {
    "core": {
        "required": ["implement_type", "body_position", "laterality",
                     "resistance_origin", "resistance_direction",
                     "stability_demand", "movement_family", "pattern_class"],
    },
    "extended": {
        "required": ["implement_type", "body_position", "laterality",
                     "resistance_origin", "resistance_direction",
                     "stability_demand", "movement_family", "pattern_class"],
    },
    "full": {
        "required": ["implement_type", "body_position", "laterality",
                     "resistance_origin", "resistance_direction",
                     "stability_demand", "movement_family", "pattern_class"],
    },
}

FIELD_CLASSIFICATION = {
    "structural": [
        "implement_type", "body_position", "laterality",
        "resistance_origin", "resistance_direction",
        "grip_style", "bench_angle",
    ],
    "categorical": ["movement_family", "pattern_class"],
    "interpretive": [
        "stability_demand", "stretch_bias", "shortened_bias",
        "convergence_arc", "humeral_plane", "elbow_path",
    ],
}

METADATA_TIER_DEFINITIONS = {
    "core": "Structural fields + stability_demand + movement_family + pattern_class only. Interpretive fields may be null.",
    "extended": "Core fields plus applicable interpretive fields authored with reasonable confidence. Some interpretive nulls are honest (field not applicable).",
    "full": "All applicable fields authored with high confidence. Nulls only where field is genuinely not applicable to the movement.",
}

MANUAL_ENTRY_LINKAGE_RULES = {
    "intel_backed_selection": "User selects an exact Intel exercise from catalog -> store intel_exercise_id on the lift_set. Full matrix scoring applies.",
    "local_custom_movement": "User enters a free-text movement name not in Intel catalog -> intel_exercise_id = null. No matrix scoring. Bridge-dose fallback only.",
    "no_inferred_variants": "Do NOT infer overly specific variants (e.g., do not map 'bench press' to 'Close-Grip Bench Press'). Only exact catalog matches get intel_exercise_id.",
}


def validate_biomechanics(name, bio):
    errors = []

    def _check_enum(field, value, allowed):
        if value is not None and value not in allowed:
            errors.append(f"{name}: {field}='{value}' not in {sorted(allowed)}")

    _check_enum("implement_type", bio.get("implement_type"), IMPLEMENT_TYPES)
    _check_enum("body_position", bio.get("body_position"), BODY_POSITIONS)
    _check_enum("laterality", bio.get("laterality"), LATERALITIES)
    _check_enum("resistance_origin", bio.get("resistance_origin"), RESISTANCE_ORIGINS)
    _check_enum("resistance_direction", bio.get("resistance_direction"), RESISTANCE_DIRECTIONS)
    _check_enum("grip_style", bio.get("grip_style"), GRIP_STYLES)
    _check_enum("humeral_plane", bio.get("humeral_plane"), HUMERAL_PLANES)
    _check_enum("elbow_path", bio.get("elbow_path"), ELBOW_PATHS)
    _check_enum("movement_family", bio.get("movement_family"), MOVEMENT_FAMILIES)
    _check_enum("pattern_class", bio.get("pattern_class"), PATTERN_CLASSES)
    _check_enum("metadata_tier", bio.get("metadata_tier"), METADATA_TIERS)

    for field in ["implement_type", "body_position", "laterality"]:
        if not bio.get(field):
            errors.append(f"{name}: required field '{field}' is missing")

    for field in ["movement_family", "pattern_class"]:
        if not bio.get(field):
            errors.append(f"{name}: categorical field '{field}' is missing")

    sd = bio.get("stability_demand")
    if sd is not None and not (0.0 <= sd <= 1.0):
        errors.append(f"{name}: stability_demand={sd} out of range [0,1]")

    for field in ["stretch_bias", "shortened_bias"]:
        val = bio.get(field)
        if val is not None and not (0.0 <= val <= 1.0):
            errors.append(f"{name}: {field}={val} out of range [0,1]")

    ca = bio.get("convergence_arc")
    if ca is not None and ca not in (0, 1, True, False):
        errors.append(f"{name}: convergence_arc={ca} must be 0 or 1")

    tier = bio.get("metadata_tier", "core")
    tier_req = TIER_REQUIREMENTS.get(tier, {})
    for field in tier_req.get("required", []):
        if bio.get(field) is None:
            errors.append(f"{name}: tier='{tier}' requires '{field}' but it is null")

    return errors


def validate_exercise_batch(batch_data):
    all_errors = []
    muscle_set = set(CANONICAL_MUSCLES)

    for name, data in batch_data.items():
        bio = data.get("biomechanics", {})
        all_errors.extend(validate_biomechanics(name, bio))

        for matrix_name in ["activation", "role_weighted", "bottleneck", "stabilization"]:
            matrix = data.get(matrix_name)
            if matrix is None:
                all_errors.append(f"{name}: missing '{matrix_name}' matrix")
                continue
            missing = muscle_set - set(matrix.keys())
            if missing:
                all_errors.append(f"{name}: {matrix_name} missing muscles: {sorted(missing)}")
            extra = set(matrix.keys()) - muscle_set
            if extra:
                all_errors.append(f"{name}: {matrix_name} has unknown muscles: {sorted(extra)}")

        act = data.get("activation", {})
        for m, v in act.items():
            if not isinstance(v, int) or not (0 <= v <= 5):
                all_errors.append(f"{name}: activation['{m}']={v} must be int 0-5")

        for matrix_name in ["role_weighted", "bottleneck", "stabilization"]:
            matrix = data.get(matrix_name, {})
            for m, v in matrix.items():
                if not (0.0 <= float(v) <= 1.0):
                    all_errors.append(f"{name}: {matrix_name}['{m}']={v} must be float 0-1")

        tags = data.get("tags", [])
        for tag in tags:
            if tag not in EXERCISE_SLOTS:
                all_errors.append(f"{name}: tag '{tag}' not in {sorted(EXERCISE_SLOTS)}")

        if not bio.get("metadata_tier"):
            all_errors.append(f"{name}: metadata_tier is required")

    return all_errors


def get_contract_documentation():
    return {
        "contract_version": "2.0",
        "catalog_revision": CATALOG_REVISION,
        "biomechanics_object_shape": {
            "implement_type": {"type": "string", "required": True, "enum": sorted(IMPLEMENT_TYPES), "classification": "structural"},
            "body_position": {"type": "string", "required": True, "enum": sorted(BODY_POSITIONS), "classification": "structural"},
            "laterality": {"type": "string", "required": True, "enum": sorted(LATERALITIES), "classification": "structural"},
            "resistance_origin": {"type": "string", "required": True, "enum": sorted(RESISTANCE_ORIGINS), "classification": "structural"},
            "resistance_direction": {"type": "string", "required": True, "enum": sorted(RESISTANCE_DIRECTIONS), "classification": "structural"},
            "grip_style": {"type": "string|null", "required": False, "enum": sorted(GRIP_STYLES), "classification": "structural",
                          "nullability": "Null when grip is not a defining characteristic of the exercise"},
            "bench_angle": {"type": "float|null", "required": False, "classification": "structural",
                           "nullability": "Null when no bench is used. Values: 0=flat, 30/45=incline, -15/-30=decline, 90=seated OHP"},
            "stability_demand": {"type": "float", "required": True, "range": [0.0, 1.0], "classification": "interpretive"},
            "stretch_bias": {"type": "float|null", "required": False, "range": [0.0, 1.0], "classification": "interpretive",
                            "nullability": "Null unless resistance profile meaningfully peaks at stretched position"},
            "shortened_bias": {"type": "float|null", "required": False, "range": [0.0, 1.0], "classification": "interpretive",
                              "nullability": "Null unless resistance profile meaningfully peaks at contraction"},
            "convergence_arc": {"type": "boolean|null", "required": False, "classification": "interpretive",
                               "nullability": "Null for barbell/machine/lower body. True only for real inward converging arm path (flies, DB presses)"},
            "humeral_plane": {"type": "string|null", "required": False, "enum": sorted(HUMERAL_PLANES), "classification": "interpretive",
                             "nullability": "Null for lower body, carries, olympic lifts. Only for upper-body shoulder-driven patterns"},
            "elbow_path": {"type": "string|null", "required": False, "enum": sorted(ELBOW_PATHS), "classification": "interpretive",
                          "nullability": "Null for lower body, carries, whole-body movements. Only where elbow tracking materially defines the exercise"},
            "movement_family": {"type": "string", "required": True, "enum": sorted(MOVEMENT_FAMILIES), "classification": "categorical"},
            "pattern_class": {"type": "string", "required": True, "enum": sorted(PATTERN_CLASSES), "classification": "categorical"},
            "biomechanics_version": {"type": "integer", "required": True, "current": 2},
            "metadata_tier": {"type": "string", "required": True, "enum": sorted(METADATA_TIERS), "definitions": METADATA_TIER_DEFINITIONS},
            "updated_at": {"type": "string|null", "required": False, "format": "ISO 8601 timestamp of last authoring update"},
            "field_classification": {
                "type": "object",
                "description": "Included in every response. Tells Expo which fields are safe for hard filtering vs advisory display.",
                "shape": FIELD_CLASSIFICATION,
            },
        },
        "manual_entry_linkage_rules": MANUAL_ENTRY_LINKAGE_RULES,
        "future_considerations": {
            "variant_group": "Not yet implemented. Future field (parent_exercise_id or variant_group) for UI grouping only. Example: 'Incline Dumbbell Curl' groups under 'Dumbbell Curl' family. Not for scoring — purely display.",
        },
    }
