"""
ARCFORGE MEAL PLAN — DRAKONOSLAV
=================================
BUILD Day is the immutable baseline. All other day types are derived from it
by applying ingredient-priority adjustments per the macro delta.

LOCKED_BASELINE_MACROS (when all 6 meals are checked, before 21:30 Intel add):
  p: 173.9g  |  c: 330.9g  |  f: 54.4g

BUILD total (including 21:30 baseline of 0g whey):
  175g P  |  346g C  |  60g F  |  2,696 kcal

Ingredient adjustment priority (least → most disruptive):
  MCT Powder → Dextrin → Oats → Bananas → Eggs → Flaxseed → Whey → Greek Yogurt

Window names (exact):
  Pre-Cardio   05:30
  Post-Cardio  06:45
  Mid-Morning  11:30
  Pre-Lift     15:45
  Post-Lift    18:20
  Evening Meal 20:00
  Evening Protein 21:30  ← Intel-managed; baseline = 0g Whey

This file is the source of truth. Do not modify without explicit user instruction.
"""

# ─── EXACT FOOD MACROS (per unit / per g) ────────────────────────────────────
# Banana (1 whole):   27g C | 1g P | 0g F | 104 kcal
# Oats (per g):       0.67g C | 0.17g P | 0.06g F
# Whey (per g):       0.08g C | 0.80g P | 0.05g F
# MCT Powder (per g): 0g C | 0g P | 0.90g F
# Dextrin (per g):    1.0g C | 0g P | 0g F
# Greek Yogurt (1c):  9g C | 20g P | 0g F
# Flaxseed (per g):   0.27g C | 0.20g P | 0.40g F
# Eggs (1 whole):     0g C | 6g P | 5g F | 70 kcal

MEAL_PLAN = {

    # ═══════════════════════════════════════════════════════════════════════════
    # BUILD — GROUND TRUTH. Exact foods and amounts. Do not estimate.
    # Total: 175g P | 346g C | 60g F | 2,696 kcal
    # ═══════════════════════════════════════════════════════════════════════════
    "build": {
        "Pre-Cardio": {
            "time": "05:30", "kcal": 104, "P": 0, "C": 26, "F": 0,
            "foods": [
                {"name": "Banana", "amount": 1, "unit": "whole"},
            ],
        },
        "Post-Cardio": {
            "time": "06:45", "kcal": 644, "P": 40, "C": 75, "F": 10,
            "foods": [
                {"name": "Oats",       "amount": 120, "unit": "g"},
                {"name": "Whey",       "amount": 25,  "unit": "g"},
                {"name": "MCT Powder", "amount": 10,  "unit": "g"},
            ],
        },
        "Mid-Morning": {
            "time": "11:30", "kcal": 303, "P": 30, "C": 55, "F": 10,
            "foods": [
                {"name": "Greek Yogurt", "amount": 1,  "unit": "cup"},
                {"name": "Flaxseed",     "amount": 30, "unit": "g"},
                {"name": "Whey",         "amount": 15, "unit": "g"},
            ],
        },
        "Pre-Lift": {
            "time": "15:45", "kcal": 385, "P": 25, "C": 65, "F": 5,
            "foods": [
                {"name": "Dextrin", "amount": 80, "unit": "g"},
                {"name": "Whey",    "amount": 20, "unit": "g"},
            ],
        },
        "Post-Lift": {
            "time": "18:20", "kcal": 268, "P": 45, "C": 85, "F": 5,
            "foods": [
                {"name": "Dextrin", "amount": 40, "unit": "g"},
                {"name": "Whey",    "amount": 30, "unit": "g"},
            ],
        },
        "Evening Meal": {
            "time": "20:00", "kcal": 992, "P": 35, "C": 40, "F": 30,
            "foods": [
                {"name": "Oats",       "amount": 124, "unit": "g"},
                {"name": "Flaxseed",   "amount": 30,  "unit": "g"},
                {"name": "MCT Powder", "amount": 20,  "unit": "g"},
                {"name": "Eggs",       "amount": 2,   "unit": "whole"},
                {"name": "Banana",     "amount": 1,   "unit": "whole"},
            ],
        },
        "Evening Protein": {
            "time": "21:30", "kcal": 0, "P": 0, "C": 0, "F": 0,
            "intel_managed": True,
            "note": "Intel resource cycle fills amount. Baseline = 0g Whey. Displayed as +Xg whey → +YP +Z kcal.",
            "foods": [
                {"name": "Whey", "amount": 0, "unit": "g", "intel_managed": True},
            ],
        },
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SURGE — High output. +44g C / -20g F vs build.
    # Carb increase: more Dextrin across Pre-Lift and Post-Lift.
    # Fat reduction: MCT removed from Evening Meal, reduced in Post-Cardio.
    # Total target: 175g P | 390g C | 40g F | ~2,700 kcal
    # ═══════════════════════════════════════════════════════════════════════════
    "surge": {
        "Pre-Cardio": {
            "time": "05:30", "kcal": 131, "P": 0, "C": 30, "F": 0,
            "foods": [
                {"name": "Banana",  "amount": 1,  "unit": "whole"},
                {"name": "Dextrin", "amount": 4,  "unit": "g"},
            ],
        },
        "Post-Cardio": {
            "time": "06:45", "kcal": 700, "P": 40, "C": 90, "F": 10,
            "foods": [
                {"name": "Oats",       "amount": 120, "unit": "g"},
                {"name": "Whey",       "amount": 25,  "unit": "g"},
                {"name": "MCT Powder", "amount": 10,  "unit": "g"},
                {"name": "Dextrin",    "amount": 15,  "unit": "g"},
            ],
        },
        "Mid-Morning": {
            "time": "11:30", "kcal": 323, "P": 30, "C": 60, "F": 10,
            "foods": [
                {"name": "Greek Yogurt", "amount": 1,  "unit": "cup"},
                {"name": "Flaxseed",     "amount": 30, "unit": "g"},
                {"name": "Whey",         "amount": 15, "unit": "g"},
                {"name": "Dextrin",      "amount": 5,  "unit": "g"},
            ],
        },
        "Pre-Lift": {
            "time": "15:45", "kcal": 445, "P": 25, "C": 80, "F": 5,
            "foods": [
                {"name": "Dextrin", "amount": 95, "unit": "g"},
                {"name": "Whey",    "amount": 20, "unit": "g"},
            ],
        },
        "Post-Lift": {
            "time": "18:20", "kcal": 368, "P": 45, "C": 110, "F": 5,
            "foods": [
                {"name": "Dextrin", "amount": 65, "unit": "g"},
                {"name": "Whey",    "amount": 30, "unit": "g"},
            ],
        },
        "Evening Meal": {
            "time": "20:00", "kcal": 630, "P": 35, "C": 20, "F": 10,
            "foods": [
                {"name": "Oats",     "amount": 30,  "unit": "g"},
                {"name": "Flaxseed", "amount": 5,   "unit": "g"},
                {"name": "Eggs",     "amount": 2,   "unit": "whole"},
                {"name": "Banana",   "amount": 1,   "unit": "whole"},
                {"name": "Whey",     "amount": 15,  "unit": "g"},
            ],
        },
        "Evening Protein": {
            "time": "21:30", "kcal": 0, "P": 0, "C": 0, "F": 0,
            "intel_managed": True,
            "note": "Intel resource cycle fills amount. Baseline = 0g Whey.",
            "foods": [
                {"name": "Whey", "amount": 0, "unit": "g", "intel_managed": True},
            ],
        },
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # RESET — Recovery. -56g C / +20g F vs build.
    # Carb reduction: Dextrin cut from Pre-Lift and Post-Lift, Oats reduced Evening.
    # Fat increase: MCT added to Mid-Morning, Flax held, MCT increase in Evening.
    # Total target: 175g P | 290g C | 80g F | ~2,695 kcal
    # ═══════════════════════════════════════════════════════════════════════════
    "reset": {
        "Pre-Cardio": {
            "time": "05:30", "kcal": 97, "P": 0, "C": 25, "F": 0,
            "foods": [
                {"name": "Banana", "amount": 0.75, "unit": "whole"},
            ],
        },
        "Post-Cardio": {
            "time": "06:45", "kcal": 650, "P": 40, "C": 60, "F": 15,
            "foods": [
                {"name": "Oats",       "amount": 90,  "unit": "g"},
                {"name": "Whey",       "amount": 25,  "unit": "g"},
                {"name": "MCT Powder", "amount": 15,  "unit": "g"},
            ],
        },
        "Mid-Morning": {
            "time": "11:30", "kcal": 323, "P": 30, "C": 45, "F": 15,
            "foods": [
                {"name": "Greek Yogurt", "amount": 1,  "unit": "cup"},
                {"name": "Flaxseed",     "amount": 30, "unit": "g"},
                {"name": "Whey",         "amount": 15, "unit": "g"},
                {"name": "MCT Powder",   "amount": 10, "unit": "g"},
            ],
        },
        "Pre-Lift": {
            "time": "15:45", "kcal": 310, "P": 25, "C": 45, "F": 10,
            "foods": [
                {"name": "Dextrin",    "amount": 45, "unit": "g"},
                {"name": "Whey",       "amount": 20, "unit": "g"},
                {"name": "MCT Powder", "amount": 10, "unit": "g"},
            ],
        },
        "Post-Lift": {
            "time": "18:20", "kcal": 280, "P": 45, "C": 55, "F": 10,
            "foods": [
                {"name": "Dextrin",    "amount": 20, "unit": "g"},
                {"name": "Whey",       "amount": 30, "unit": "g"},
                {"name": "MCT Powder", "amount": 10, "unit": "g"},
            ],
        },
        "Evening Meal": {
            "time": "20:00", "kcal": 1035, "P": 35, "C": 35, "F": 30,
            "foods": [
                {"name": "Oats",       "amount": 100, "unit": "g"},
                {"name": "Flaxseed",   "amount": 30,  "unit": "g"},
                {"name": "MCT Powder", "amount": 25,  "unit": "g"},
                {"name": "Eggs",       "amount": 2,   "unit": "whole"},
            ],
        },
        "Evening Protein": {
            "time": "21:30", "kcal": 0, "P": 0, "C": 0, "F": 0,
            "intel_managed": True,
            "note": "Intel resource cycle fills amount. Baseline = 0g Whey.",
            "foods": [
                {"name": "Whey", "amount": 0, "unit": "g", "intel_managed": True},
            ],
        },
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # RESENSITIZE — Deload. -96g C / +30g F / -85 kcal vs build.
    # Largest carb cut: Dextrin heavily reduced, Oats pulled back.
    # Fat increase: MCT increased across multiple windows, Flax held.
    # Total target: 175g P | 250g C | 90g F | ~2,610 kcal
    # ═══════════════════════════════════════════════════════════════════════════
    "resensitize": {
        "Pre-Cardio": {
            "time": "05:30", "kcal": 78, "P": 0, "C": 20, "F": 0,
            "foods": [
                {"name": "Banana", "amount": 0.75, "unit": "whole"},
            ],
        },
        "Post-Cardio": {
            "time": "06:45", "kcal": 600, "P": 40, "C": 45, "F": 15,
            "foods": [
                {"name": "Oats",       "amount": 65,  "unit": "g"},
                {"name": "Whey",       "amount": 25,  "unit": "g"},
                {"name": "MCT Powder", "amount": 15,  "unit": "g"},
            ],
        },
        "Mid-Morning": {
            "time": "11:30", "kcal": 360, "P": 30, "C": 35, "F": 20,
            "foods": [
                {"name": "Greek Yogurt", "amount": 1,  "unit": "cup"},
                {"name": "Flaxseed",     "amount": 30, "unit": "g"},
                {"name": "Whey",         "amount": 15, "unit": "g"},
                {"name": "MCT Powder",   "amount": 15, "unit": "g"},
            ],
        },
        "Pre-Lift": {
            "time": "15:45", "kcal": 270, "P": 25, "C": 30, "F": 10,
            "foods": [
                {"name": "Dextrin",    "amount": 30, "unit": "g"},
                {"name": "Whey",       "amount": 20, "unit": "g"},
                {"name": "MCT Powder", "amount": 10, "unit": "g"},
            ],
        },
        "Post-Lift": {
            "time": "18:20", "kcal": 280, "P": 40, "C": 40, "F": 10,
            "foods": [
                {"name": "Dextrin",    "amount": 15, "unit": "g"},
                {"name": "Whey",       "amount": 30, "unit": "g"},
                {"name": "MCT Powder", "amount": 10, "unit": "g"},
            ],
        },
        "Evening Meal": {
            "time": "20:00", "kcal": 1022, "P": 40, "C": 40, "F": 35,
            "foods": [
                {"name": "Oats",       "amount": 60,  "unit": "g"},
                {"name": "Flaxseed",   "amount": 30,  "unit": "g"},
                {"name": "MCT Powder", "amount": 25,  "unit": "g"},
                {"name": "Eggs",       "amount": 4,   "unit": "whole"},
                {"name": "Banana",     "amount": 1,   "unit": "whole"},
            ],
        },
        "Evening Protein": {
            "time": "21:30", "kcal": 0, "P": 0, "C": 0, "F": 0,
            "intel_managed": True,
            "note": "Intel resource cycle fills amount. Baseline = 0g Whey.",
            "foods": [
                {"name": "Whey", "amount": 0, "unit": "g", "intel_managed": True},
            ],
        },
    },
}

# Locked baseline — stored when all 6 meals are checked (before 21:30 Intel)
LOCKED_BASELINE_MACROS = {"p": 173.9, "c": 330.9, "f": 54.4}

# Window display order (always render in this sequence)
WINDOW_ORDER = [
    "Pre-Cardio",
    "Post-Cardio",
    "Mid-Morning",
    "Pre-Lift",
    "Post-Lift",
    "Evening Meal",
    "Evening Protein",
]


def get_meal_plan(macro_day: str) -> dict:
    """Return the ordered meal plan for a given macro day type."""
    plan = MEAL_PLAN.get(macro_day, MEAL_PLAN["build"])
    return {k: plan[k] for k in WINDOW_ORDER if k in plan}
