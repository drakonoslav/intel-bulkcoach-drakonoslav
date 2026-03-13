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
# Source: user's food tracking app — large-batch measurements for maximum decimal precision.
#
# Banana (1 medium, 118g):        P=0.870g  C=25.120g  F=0.340g  | 103.8 kcal
#   Derived from: 10 medium (1180g) → P:8.7  C:251.2  F:3.4  kcal:1038
#
# Oats — Bob's Red Mill WG (per g): P=0.1330  C=0.6000  F=0.0500 | 4.0000 kcal
#   Derived from: 100g → P:13.3  C:60.0  F:5.0  kcal:400
#
# Whey — Transparent Labs Isolate (per g): P=0.8780  C=0.0310  F=0.0000 | 3.7600 kcal
#   Derived from: 100g → P:87.8  C:3.1  F:0.0  kcal:376
#
# MCT Powder — MCT Co. (per g): P=0.1000  C=0.0000  F=0.8000 | 7.0000 kcal
#   Derived from: 200g → P:20.0  C:0.0  F:160.0  kcal:1400
#
# Dextrin — Bulk Powders HBCD (per g): P=0.0000  C=0.9730  F=0.0000 | 3.8700 kcal
#   Derived from: 100g → P:0.0  C:97.3  F:0.0  kcal:387
#
# Greek Yogurt — Plain Nonfat (per cup, 245g): P=25.240  C=8.910  F=0.910 | 149.5 kcal
#   Derived from: 10 cups (2450g) → P:252.4  C:89.1  F:9.1  kcal:1495
#
# Flaxseed — Bio Planete Powder (per g): P=0.3300  C=0.0770  F=0.1000 | 3.2400 kcal
#   Derived from: 100g → P:33.0  C:7.7  F:10.0  kcal:324
#
# Eggs — Whole Hard-Boiled Large (per egg, 50g): P=6.290  C=0.560  F=5.300 | 77.5 kcal
#   Derived from: 10 large (500g) → P:62.9  C:5.6  F:53.0  kcal:775

INGREDIENT_MACROS = {
    "Banana":       {"unit": "whole", "p": 0.8700, "c": 25.1200, "f": 0.3400, "kcal": 103.8000},
    "Oats":         {"unit": "g",     "p": 0.1330, "c":  0.6000, "f": 0.0500, "kcal":   4.0000},
    "Whey":         {"unit": "g",     "p": 0.8780, "c":  0.0310, "f": 0.0000, "kcal":   3.7600},
    "MCT Powder":   {"unit": "g",     "p": 0.1000, "c":  0.0000, "f": 0.8000, "kcal":   7.0000},
    "Dextrin":      {"unit": "g",     "p": 0.0000, "c":  0.9730, "f": 0.0000, "kcal":   3.8700},
    "Greek Yogurt": {"unit": "cup",   "p": 25.2400,"c":  8.9100, "f": 0.9100, "kcal": 149.5000},
    "Flaxseed":     {"unit": "g",     "p": 0.3300, "c":  0.0770, "f": 0.1000, "kcal":   3.2400},
    "Eggs":         {"unit": "whole", "p": 6.2900, "c":  0.5600, "f": 5.3000, "kcal":  77.5000},
}

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
LOCKED_BASELINE_MACROS = {"p": 173.9, "c": 330.9, "f": 54.4}  # user's locked display values

# ─── BUILD DAY — DAILY INGREDIENT TOTALS (sacred, cross-verified) ────────────
# Sum of all windows. Whey excludes Intel 21:30 addition (baseline = 0g).
BUILD_DAILY_TOTALS = {
    "Oats":         {"amount": 244, "unit": "g",    "note": "Post-Cardio 120g + Evening Meal 124g"},
    "Dextrin":      {"amount": 120, "unit": "g",    "note": "Pre-Lift 80g + Post-Lift 40g"},
    "Whey":         {"amount": 90,  "unit": "g",    "note": "Post-Cardio 25g + Mid-Morning 15g + Pre-Lift 20g + Post-Lift 30g (+ Intel 21:30)"},
    "MCT Powder":   {"amount": 30,  "unit": "g",    "note": "Post-Cardio 10g + Evening Meal 20g"},
    "Flaxseed":     {"amount": 60,  "unit": "g",    "note": "Mid-Morning 30g + Evening Meal 30g"},
    "Greek Yogurt": {"amount": 1,   "unit": "cup",  "note": "Mid-Morning 1 cup"},
    "Eggs":         {"amount": 2,   "unit": "whole","note": "Evening Meal 2 eggs"},
    "Bananas":      {"amount": 2,   "unit": "whole","note": "Pre-Cardio 1 + Evening Meal 1"},
}

# ─── ADJUSTMENT PRIORITY — least disruptive first ────────────────────────────
ADJUSTMENT_PRIORITY = [
    {"rank": 1, "ingredient": "MCT Powder", "role": "fat-only"},
    {"rank": 2, "ingredient": "Dextrin",    "role": "fast carb"},
    {"rank": 3, "ingredient": "Oats",       "role": "slow carb"},
    {"rank": 4, "ingredient": "Bananas",    "role": "carbs + micros"},
    {"rank": 5, "ingredient": "Eggs",       "role": "protein + fat"},
    {"rank": 6, "ingredient": "Flaxseed",   "role": "fiber + fat"},
    {"rank": 7, "ingredient": "Whey",       "role": "protein anchor"},
    {"rank": 8, "ingredient": "Yogurt",     "role": "protein anchor"},
]

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
