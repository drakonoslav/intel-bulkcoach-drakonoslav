GEOMETRY_INCLINE_PRESS = "incline_press"
GEOMETRY_FLAT_PRESS = "flat_press"
GEOMETRY_DECLINE_PRESS = "decline_press"
GEOMETRY_DIP = "dip"
GEOMETRY_HORIZONTAL_ADDUCTION = "horizontal_adduction"
GEOMETRY_VERTICAL_ADDUCTION = "vertical_adduction"
GEOMETRY_DOWNWARD_ADDUCTION = "downward_adduction"
GEOMETRY_PUSHUP = "pushup"
GEOMETRY_NEUTRAL_PRESS = "neutral_press"

GEOMETRY_BASE_SHARES = {
    GEOMETRY_INCLINE_PRESS:        {"upper": 0.60, "mid": 0.25, "lower": 0.15},
    GEOMETRY_FLAT_PRESS:           {"upper": 0.25, "mid": 0.50, "lower": 0.25},
    GEOMETRY_DECLINE_PRESS:        {"upper": 0.15, "mid": 0.30, "lower": 0.55},
    GEOMETRY_DIP:                  {"upper": 0.10, "mid": 0.25, "lower": 0.65},
    GEOMETRY_HORIZONTAL_ADDUCTION: {"upper": 0.30, "mid": 0.45, "lower": 0.25},
    GEOMETRY_VERTICAL_ADDUCTION:   {"upper": 0.55, "mid": 0.30, "lower": 0.15},
    GEOMETRY_DOWNWARD_ADDUCTION:   {"upper": 0.15, "mid": 0.25, "lower": 0.60},
    GEOMETRY_PUSHUP:               {"upper": 0.25, "mid": 0.50, "lower": 0.25},
    GEOMETRY_NEUTRAL_PRESS:        {"upper": 0.33, "mid": 0.34, "lower": 0.33},
}

GRIP_ADJUSTMENTS = {
    "wide":       {"upper": 0.00, "mid": 0.06, "lower": -0.06},
    "close_grip": {"upper": 0.04, "mid": -0.04, "lower": 0.00},
    "dip":        {"upper": -0.04, "mid": -0.04, "lower": 0.08},
}


def classify_geometry(exercise_name):
    name = exercise_name.lower()

    if "dip" in name:
        return GEOMETRY_DIP

    is_pushup = "push-up" in name or "pushup" in name or "push up" in name
    if is_pushup:
        if "decline" in name:
            return GEOMETRY_DECLINE_PRESS
        if "incline" in name:
            return GEOMETRY_INCLINE_PRESS
        return GEOMETRY_PUSHUP

    if "fly" in name or "flye" in name:
        if "low to high" in name or "low-to-high" in name:
            return GEOMETRY_VERTICAL_ADDUCTION
        if "high to low" in name or "high-to-low" in name:
            return GEOMETRY_DOWNWARD_ADDUCTION
        return GEOMETRY_HORIZONTAL_ADDUCTION

    is_press = "bench" in name or "press" in name
    if is_press:
        if "incline" in name:
            return GEOMETRY_INCLINE_PRESS
        if "decline" in name:
            return GEOMETRY_DECLINE_PRESS
        return GEOMETRY_FLAT_PRESS

    return GEOMETRY_NEUTRAL_PRESS


def infer_grip_class(exercise_name):
    name = exercise_name.lower()
    if "close-grip" in name or "close grip" in name:
        return "close_grip"
    if "wide" in name:
        return "wide"
    if "dip" in name:
        return "dip"
    return None
