"""
Drakonoslav base meal plan — food items per window per macro day type.
Baseline locked at: 330.9g C / 54.4g F / 173.9g P
Ingredients on hand: MCT Powder, Dextrin, Oats, Bananas, Eggs, Flaxseed, Whey, Greek Yogurt
"""

# Each entry: {name, amount, unit, notes (optional)}
# Amounts are calibrated to hit the MEAL_TIMING_TEMPLATES macro targets.

MEAL_PLAN = {
    # ─── SURGE (high output — carb surplus front and back) ──────────────────
    "surge": {
        "Pre-Cardio": [
            {"name": "Banana",   "amount": 1,   "unit": "whole", "macros": "~27g C"},
            {"name": "Dextrin",  "amount": 10,  "unit": "g",     "macros": "~10g C"},
        ],
        "Post-Cardio": [
            {"name": "Whey",         "amount": 50,  "unit": "g",     "macros": "~40g P"},
            {"name": "Dextrin",      "amount": 50,  "unit": "g",     "macros": "~50g C"},
            {"name": "Banana",       "amount": 1,   "unit": "whole", "macros": "~27g C"},
            {"name": "MCT Powder",   "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Meal 2": [
            {"name": "Greek Yogurt", "amount": 1,   "unit": "cup",   "macros": "~20g P, 9g C"},
            {"name": "Oats",         "amount": 60,  "unit": "g",     "macros": "~40g C, 10g P"},
            {"name": "Banana",       "amount": 0.5, "unit": "whole", "macros": "~14g C"},
            {"name": "MCT Powder",   "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Pre-Lift": [
            {"name": "Whey",       "amount": 30,  "unit": "g",     "macros": "~24g P"},
            {"name": "Oats",       "amount": 90,  "unit": "g",     "macros": "~60g C, 15g P"},
            {"name": "Flaxseed",   "amount": 10,  "unit": "g",     "macros": "~4g F"},
        ],
        "Post-Lift": [
            {"name": "Whey",       "amount": 55,  "unit": "g",     "macros": "~44g P"},
            {"name": "Dextrin",    "amount": 80,  "unit": "g",     "macros": "~80g C"},
            {"name": "Banana",     "amount": 1,   "unit": "whole", "macros": "~27g C"},
        ],
        "Final Meal": [
            {"name": "Eggs",         "amount": 3,   "unit": "whole", "macros": "~18g P, 15g F"},
            {"name": "Greek Yogurt", "amount": 0.5, "unit": "cup",   "macros": "~10g P, 4g C"},
            {"name": "Oats",         "amount": 25,  "unit": "g",     "macros": "~17g C"},
            {"name": "MCT Powder",   "amount": 5,   "unit": "g",     "macros": "~4g F"},
        ],
    },

    # ─── BUILD (training day — moderate carbs, fat slightly elevated) ───────
    "build": {
        "Pre-Cardio": [
            {"name": "Banana",   "amount": 1,   "unit": "whole", "macros": "~27g C"},
            {"name": "Dextrin",  "amount": 5,   "unit": "g",     "macros": "~5g C"},
        ],
        "Post-Cardio": [
            {"name": "Whey",         "amount": 50,  "unit": "g",     "macros": "~40g P"},
            {"name": "Dextrin",      "amount": 45,  "unit": "g",     "macros": "~45g C"},
            {"name": "Banana",       "amount": 1,   "unit": "whole", "macros": "~27g C"},
            {"name": "MCT Powder",   "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Meal 2": [
            {"name": "Greek Yogurt", "amount": 1,   "unit": "cup",   "macros": "~20g P, 9g C"},
            {"name": "Oats",         "amount": 55,  "unit": "g",     "macros": "~37g C, 9g P"},
            {"name": "Flaxseed",     "amount": 15,  "unit": "g",     "macros": "~6g F, 4g C"},
            {"name": "MCT Powder",   "amount": 5,   "unit": "g",     "macros": "~4g F"},
        ],
        "Pre-Lift": [
            {"name": "Whey",       "amount": 30,  "unit": "g",     "macros": "~24g P"},
            {"name": "Oats",       "amount": 80,  "unit": "g",     "macros": "~54g C, 14g P"},
            {"name": "Flaxseed",   "amount": 8,   "unit": "g",     "macros": "~3g F"},
        ],
        "Post-Lift": [
            {"name": "Whey",       "amount": 55,  "unit": "g",     "macros": "~44g P"},
            {"name": "Dextrin",    "amount": 60,  "unit": "g",     "macros": "~60g C"},
            {"name": "Banana",     "amount": 1,   "unit": "whole", "macros": "~27g C"},
        ],
        "Final Meal": [
            {"name": "Eggs",         "amount": 4,   "unit": "whole", "macros": "~24g P, 20g F"},
            {"name": "Greek Yogurt", "amount": 0.5, "unit": "cup",   "macros": "~10g P, 4g C"},
            {"name": "Oats",         "amount": 40,  "unit": "g",     "macros": "~27g C, 7g P"},
            {"name": "Flaxseed",     "amount": 12,  "unit": "g",     "macros": "~5g F"},
        ],
    },

    # ─── RESET (recovery — carbs down, fat up, total kcal stable) ───────────
    "reset": {
        "Pre-Cardio": [
            {"name": "Banana",   "amount": 0.75, "unit": "whole", "macros": "~20g C"},
            {"name": "Dextrin",  "amount": 5,    "unit": "g",     "macros": "~5g C"},
        ],
        "Post-Cardio": [
            {"name": "Whey",         "amount": 50,  "unit": "g",     "macros": "~40g P"},
            {"name": "Dextrin",      "amount": 35,  "unit": "g",     "macros": "~35g C"},
            {"name": "Banana",       "amount": 1,   "unit": "whole", "macros": "~27g C"},
            {"name": "MCT Powder",   "amount": 15,  "unit": "g",     "macros": "~13g F"},
        ],
        "Meal 2": [
            {"name": "Greek Yogurt", "amount": 1,   "unit": "cup",   "macros": "~20g P, 9g C"},
            {"name": "Oats",         "amount": 45,  "unit": "g",     "macros": "~30g C, 8g P"},
            {"name": "Flaxseed",     "amount": 18,  "unit": "g",     "macros": "~7g F"},
            {"name": "MCT Powder",   "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Pre-Lift": [
            {"name": "Whey",       "amount": 30,  "unit": "g",     "macros": "~24g P"},
            {"name": "Oats",       "amount": 55,  "unit": "g",     "macros": "~37g C, 9g P"},
            {"name": "MCT Powder", "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Post-Lift": [
            {"name": "Whey",       "amount": 55,  "unit": "g",     "macros": "~44g P"},
            {"name": "Dextrin",    "amount": 40,  "unit": "g",     "macros": "~40g C"},
            {"name": "Banana",     "amount": 0.5, "unit": "whole", "macros": "~14g C"},
            {"name": "MCT Powder", "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Final Meal": [
            {"name": "Eggs",         "amount": 4,   "unit": "whole", "macros": "~24g P, 20g F"},
            {"name": "Greek Yogurt", "amount": 0.5, "unit": "cup",   "macros": "~10g P, 4g C"},
            {"name": "Oats",         "amount": 40,  "unit": "g",     "macros": "~27g C, 7g P"},
            {"name": "Flaxseed",     "amount": 15,  "unit": "g",     "macros": "~6g F"},
            {"name": "MCT Powder",   "amount": 5,   "unit": "g",     "macros": "~4g F"},
        ],
    },

    # ─── RESENSITIZE (deload — carb reduction, fat up, kcal slightly down) ──
    "resensitize": {
        "Pre-Cardio": [
            {"name": "Banana",  "amount": 0.75, "unit": "whole", "macros": "~20g C"},
        ],
        "Post-Cardio": [
            {"name": "Whey",         "amount": 50,  "unit": "g",     "macros": "~40g P"},
            {"name": "Dextrin",      "amount": 20,  "unit": "g",     "macros": "~20g C"},
            {"name": "Banana",       "amount": 0.75,"unit": "whole", "macros": "~20g C"},
            {"name": "MCT Powder",   "amount": 15,  "unit": "g",     "macros": "~13g F"},
        ],
        "Meal 2": [
            {"name": "Greek Yogurt", "amount": 1,   "unit": "cup",   "macros": "~20g P, 9g C"},
            {"name": "Oats",         "amount": 35,  "unit": "g",     "macros": "~23g C, 6g P"},
            {"name": "Flaxseed",     "amount": 15,  "unit": "g",     "macros": "~6g F"},
            {"name": "MCT Powder",   "amount": 15,  "unit": "g",     "macros": "~13g F"},
        ],
        "Pre-Lift": [
            {"name": "Whey",       "amount": 30,  "unit": "g",     "macros": "~24g P"},
            {"name": "Oats",       "amount": 40,  "unit": "g",     "macros": "~27g C, 7g P"},
            {"name": "MCT Powder", "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Post-Lift": [
            {"name": "Whey",       "amount": 50,  "unit": "g",     "macros": "~40g P"},
            {"name": "Dextrin",    "amount": 30,  "unit": "g",     "macros": "~30g C"},
            {"name": "Banana",     "amount": 0.5, "unit": "whole", "macros": "~14g C"},
            {"name": "MCT Powder", "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
        "Final Meal": [
            {"name": "Eggs",         "amount": 4,   "unit": "whole", "macros": "~24g P, 20g F"},
            {"name": "Greek Yogurt", "amount": 1,   "unit": "cup",   "macros": "~20g P, 9g C"},
            {"name": "Oats",         "amount": 45,  "unit": "g",     "macros": "~30g C, 8g P"},
            {"name": "Flaxseed",     "amount": 20,  "unit": "g",     "macros": "~8g F"},
            {"name": "MCT Powder",   "amount": 10,  "unit": "g",     "macros": "~9g F"},
        ],
    },
}


def get_meal_plan(macro_day: str) -> dict:
    """Return the food plan for a given macro day type.
    Falls back to 'build' if day type not found."""
    return MEAL_PLAN.get(macro_day, MEAL_PLAN["build"])
