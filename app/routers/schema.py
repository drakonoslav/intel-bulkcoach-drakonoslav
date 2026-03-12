from fastapi import APIRouter
from app.vitals_models import LIFT_MODES, CARDIO_MODES, MACRO_DAY_TYPES

router = APIRouter(prefix="/schema", tags=["schema"])

# ── Schema version ────────────────────────────────────────────────────────────
# Bump this any time a field is added, removed, or its metadata changes.
# ArcForge polls /schema/version on every launch. If version differs from what
# it has cached, it fetches the full /schema/ and re-renders all forms.
# The Expo app never needs to be rebuilt or resubmitted for field changes.
SCHEMA_VERSION = "1.3.0"

# ── Changelog ────────────────────────────────────────────────────────────────
# Human-readable record of what changed in each version.
# ArcForge can display this in a "What's new in your coach" notice.
SCHEMA_CHANGELOG = {
    "1.0.0": "Initial field set: morning biometrics, training, nutrition, body composition.",
    "1.1.0": "Added crossGearDiagnostics to response shape. Added sleep debt fields. FFM expansion threshold tightened to conf >= 0.50.",
    "1.2.0": "Added Apple Health native sleep inputs: stage breakdown (awake/REM/core/deep) and onset/wake HH:MM strings. Brain now derives duration, midpoint, efficiency, and time-in-bed automatically — no user math required.",
    "1.3.0": "Added morning_temp_f/morning_temp_c (brain converts between units). Added skeletal_muscle_pct — brain derives skeletal_muscle_lb automatically. Brain now auto-computes fat_mass_lb and fat_free_mass_lb from weight + body_fat_pct.",
}


def _field(
    key: str,
    type: str,
    label: str,
    *,
    unit: str = None,
    min=None,
    max=None,
    options: list = None,
    required: bool = False,
    source_hint: str = "manual",
    description: str = None,
    periodic: bool = False,
):
    f = {
        "key": key,
        "type": type,
        "label": label,
        "required": required,
        "source_hint": source_hint,
        "periodic": periodic,
    }
    if unit:        f["unit"] = unit
    if min is not None: f["min"] = min
    if max is not None: f["max"] = max
    if options:     f["options"] = options
    if description: f["description"] = description
    return f


@router.get("/version")
def get_schema_version():
    """
    Lightweight version check. ArcForge calls this on every app launch.
    Cost: one tiny JSON round-trip (~50 bytes).

    ArcForge logic:
      cached = SecureStore.get('schema_version')
      live   = GET /schema/version → version
      if live != cached:
          schema = GET /schema/
          SecureStore.set('schema', JSON.stringify(schema))
          SecureStore.set('schema_version', live)
          re-render all forms from new schema
    """
    return {
        "version":      SCHEMA_VERSION,
        "brain_url":    "https://arcforgecoach.net",
        "full_schema":  "/schema/",
        "changelog":    "/schema/changelog",
    }


@router.get("/changelog")
def get_schema_changelog():
    """
    Human-readable record of what changed in each schema version.
    ArcForge can surface this as a 'What's new in your coach' notice
    when the schema updates.
    """
    return {
        "current_version": SCHEMA_VERSION,
        "history": [
            {"version": v, "summary": s}
            for v, s in sorted(SCHEMA_CHANGELOG.items(), reverse=True)
        ],
    }


@router.get("/")
def get_schema():
    """
    Full schema definition. ArcForge only fetches this when /schema/version
    returns a version string different from what is cached in SecureStore.
    On a normal launch where nothing has changed, only /schema/version is called.

    ArcForge rendering contract:
    1. On app launch, call GET /schema/version (cheap)
    2. Compare returned version to SecureStore cached version
    3. If different: fetch GET /schema/, cache it, re-render all forms
    4. If same: use cached schema, skip full fetch
    5. Render each session's fields in the order returned
    6. Submit collected fields to POST /vitals/daily-log
    The Expo app never needs to be rebuilt or resubmitted when fields change here.
    """
    return {
        "version": SCHEMA_VERSION,
        "brain_url": "https://arcforgecoach.net",

        # ── ENUMERATIONS ──────────────────────────────────────────────────────
        # These are the only valid string values for mode fields.
        # Render these as pickers/segmented controls — never free text.
        "enumerations": {
            "lift_modes": list(LIFT_MODES),
            "cardio_modes": list(CARDIO_MODES),
            "macro_day_types": list(MACRO_DAY_TYPES),
            "age_modes": ["early_adult", "mature_adult", "preservation"],
            "body_comp_sources": {
                "dexa":    1.0,
                "inbody":  0.85,
                "calipers": 0.5,
                "visual":  0.3,
            },
        },

        # ── SESSIONS ──────────────────────────────────────────────────────────
        # Render sessions in order. Each session is a distinct UI step.
        # All fields are optional except those marked required: true.
        # The brain accepts partial logs — never block submission on missing fields.
        "sessions": [

            {
                "id": "morning",
                "label": "Morning Check-In",
                "timing": "on_wake",
                "description": "Before food, coffee, or training. Resting biometrics only.",
                "fields": [
                    _field("hrv_ms", "float", "HRV",
                           unit="ms", min=20, max=200,
                           source_hint="wearable_preferred",
                           description="Heart rate variability — pull from Apple Health / Garmin / Oura if available"),
                    _field("resting_hr_bpm", "float", "Resting Heart Rate",
                           unit="bpm", min=30, max=100,
                           source_hint="wearable_preferred"),
                    _field("sleep_duration_min", "float", "Sleep Duration",
                           unit="min", min=0, max=720,
                           source_hint="wearable_preferred",
                           description="Total time asleep — not time in bed"),
                    _field("sleep_midpoint_min", "float", "Sleep Midpoint",
                           unit="min_from_midnight", min=0, max=840,
                           source_hint="wearable_preferred",
                           description="Midpoint between sleep onset and wake. e.g. slept 11pm, woke 7am → midpoint 3am = 180"),
                    _field("sleep_efficiency_pct", "float", "Sleep Efficiency",
                           unit="%", min=0, max=100,
                           source_hint="brain_computed",
                           description="Auto-computed from stages if not provided. You do not need to enter this manually."),
                    # ── Sleep stage breakdown (manual entry) ──────────────────
                    # Type in the stage minutes exactly as shown by your sleep tracker.
                    # Brain auto-computes duration, efficiency, and time-in-bed from these.
                    _field("sleep_onset_hhmm", "string", "Sleep Onset Time",
                           source_hint="manual",
                           description="Time you fell asleep. Use 23:20, 23.20, or 2320 — all accepted. Brain computes midpoint automatically."),
                    _field("sleep_wake_hhmm", "string", "Wake Time",
                           source_hint="manual",
                           description="Time you woke up. Use 05:05, 05.05, or 0505 — all accepted. Brain computes midpoint automatically."),
                    _field("sleep_awake_min", "float", "Awake",
                           unit="min", min=0, max=120,
                           source_hint="manual",
                           description="Minutes awake. Type raw minutes (e.g. 2) or H.MM (e.g. 0.02 = 2 min)."),
                    _field("sleep_rem_min", "float", "REM Sleep",
                           unit="min", min=0, max=360,
                           source_hint="manual",
                           description="REM minutes. Type raw minutes (e.g. 85) or H.MM (e.g. 1.25 = 1h25m = 85 min)."),
                    _field("sleep_core_min", "float", "Core Sleep",
                           unit="min", min=0, max=480,
                           source_hint="manual",
                           description="Core sleep minutes. Type raw minutes or H.MM (e.g. 2.30 = 2h30m = 150 min)."),
                    _field("sleep_deep_min", "float", "Deep Sleep",
                           unit="min", min=0, max=300,
                           source_hint="manual",
                           description="Deep sleep minutes. Type raw minutes or H.MM (e.g. 1.05 = 1h05m = 65 min)."),
                    _field("body_weight_lb", "float", "Morning Weight",
                           unit="lb", min=80, max=400,
                           source_hint="scale",
                           description="Post-void, before food"),
                    _field("morning_temp_f", "float", "Morning Temperature (°F)",
                           unit="°F", min=95.0, max=104.0,
                           source_hint="manual",
                           description="Oral or wrist temp on waking, before getting up. Enter in °F. If you only have °C, use morning_temp_c instead — brain converts automatically."),
                    _field("morning_temp_c", "float", "Morning Temperature (°C)",
                           unit="°C", min=35.0, max=40.0,
                           source_hint="manual",
                           description="Enter in °C if that's what your thermometer shows. Brain stores both units automatically."),
                    _field("libido_score", "int", "Libido",
                           min=1, max=5,
                           description="1 = none / absent  →  5 = high / present"),
                    _field("morning_erection_score", "int", "Morning Erection",
                           min=0, max=3,
                           description="0 = none  1 = partial  2 = full  3 = spontaneous"),
                    _field("mood_stability_score", "int", "Mood Stability",
                           min=1, max=5,
                           description="1 = volatile / irritable  →  5 = calm / stable"),
                    _field("mental_drive_score", "int", "Mental Drive / Focus",
                           min=1, max=5,
                           description="1 = foggy / flat  →  5 = sharp / motivated"),
                    _field("soreness_score", "int", "Whole-Body Soreness",
                           min=1, max=5,
                           description="1 = none  →  5 = severe systemic soreness"),
                    _field("joint_friction_score", "int", "Joint Friction",
                           min=1, max=5,
                           description="1 = none  →  5 = grinding or pain"),
                ],
            },

            {
                "id": "training",
                "label": "Training Log",
                "timing": "post_workout",
                "description": "Log after training is complete for the day.",
                "fields": [
                    _field("planned_lift_mode", "enum", "Planned Training",
                           options=list(LIFT_MODES),
                           source_hint="prefilled_from_brain",
                           description="What the brain recommended this morning — pre-fill from recommendation response"),
                    _field("completed_lift_mode", "enum", "Training Actually Done",
                           options=list(LIFT_MODES),
                           description="What was actually performed — may differ from plan"),
                    _field("strength_output_index", "float", "Strength Output Score",
                           unit="index", min=0, max=100,
                           source_hint="brain_computed",
                           description="Returned by /vitals/lift-session after logging sets — echo it back here"),
                    _field("actual_cardio_mode", "enum", "Cardio Mode",
                           options=list(CARDIO_MODES)),
                    _field("cardio_duration_min", "float", "Cardio Duration",
                           unit="min", min=0, max=240),
                    _field("cardio_avg_hr_bpm", "float", "Average Cardio HR",
                           unit="bpm", min=80, max=200,
                           source_hint="wearable_preferred"),
                    _field("cardio_zone2_min", "float", "Zone 2 Time",
                           unit="min", min=0, max=240,
                           description="60–70% HRmax"),
                    _field("cardio_zone3_min", "float", "Zone 3 Time",
                           unit="min", min=0, max=240,
                           description="70–80% HRmax"),
                ],
            },

            {
                "id": "nutrition",
                "label": "Nutrition Close",
                "timing": "end_of_day",
                "description": "Log at end of day or before bed.",
                "fields": [
                    _field("kcal_actual", "float", "Total Calories",
                           unit="kcal", min=0, max=8000),
                    _field("protein_g_actual", "float", "Protein",
                           unit="g", min=0, max=500),
                    _field("carbs_g_actual", "float", "Carbs",
                           unit="g", min=0, max=1000),
                    _field("fat_g_actual", "float", "Fat",
                           unit="g", min=0, max=500),
                    _field("recommended_macro_day", "enum", "Macro Day Type Assigned",
                           options=list(MACRO_DAY_TYPES),
                           source_hint="prefilled_from_brain",
                           description="Echo back the macro day type the brain assigned this morning"),
                ],
            },

            {
                "id": "body_comp",
                "label": "Body Composition",
                "timing": "periodic",
                "description": "Log weekly or whenever measured. Never required daily.",
                "fields": [
                    _field("body_fat_pct", "float", "Body Fat %",
                           unit="%", min=3, max=60, periodic=True,
                           description="Enter the % your scale or app shows directly."),
                    _field("fat_free_mass_lb", "float", "Fat-Free Mass",
                           unit="lb", min=50, max=300, periodic=True,
                           source_hint="scale_or_dexa",
                           description="Enter directly if your scale shows it. Otherwise brain derives it from weight + body fat %."),
                    _field("fat_mass_lb", "float", "Fat Mass",
                           unit="lb", min=0, max=200, periodic=True,
                           source_hint="brain_computed",
                           description="Auto-computed from weight × body fat %. You do not need to enter this."),
                    _field("skeletal_muscle_pct", "float", "Skeletal Muscle %",
                           unit="%", min=20, max=60, periodic=True,
                           source_hint="scale",
                           description="Enter the % your scale shows. Brain converts to lbs automatically."),
                    _field("skeletal_muscle_lb", "float", "Skeletal Muscle (lbs)",
                           unit="lb", min=30, max=200, periodic=True,
                           source_hint="brain_computed",
                           description="Auto-computed from skeletal_muscle_pct × weight. Only enter directly if your scale gives lbs."),
                    _field("waist_at_navel_in", "float", "Waist at Navel",
                           unit="in", min=20, max=80, periodic=True,
                           description="Tape measure at navel, relaxed, morning"),
                    _field("body_comp_confidence", "float", "Measurement Source Confidence",
                           unit="0_to_1", min=0.0, max=1.0, periodic=True,
                           description="1.0=DEXA  0.85=InBody  0.5=calipers  0.3=visual estimate"),
                    _field("waist_measure_confidence", "float", "Waist Measurement Confidence",
                           unit="0_to_1", min=0.0, max=1.0, periodic=True,
                           description="1.0=tape measure  0.5=estimated"),
                ],
            },
        ],

        # ── REGISTRATION FIELDS ───────────────────────────────────────────────
        # Collected once at first launch only. Never re-collected.
        "registration": {
            "endpoint": "POST /users/register",
            "fields": [
                _field("expo_user_id", "string", "Device UUID",
                       required=True, source_hint="generated_on_device",
                       description="UUID-v4 generated client-side at first launch. Store in SecureStore. Never regenerate."),
                _field("username", "string", "Display Name",
                       required=True, min=1, max=40),
                _field("date_of_birth", "string", "Date of Birth",
                       required=True,
                       description="YYYY-MM-DD format. Used to derive age_mode (early_adult / mature_adult / preservation)."),
            ],
        },

        # ── BASELINES FIELDS ──────────────────────────────────────────────────
        # Collected at onboarding. Can be updated anytime from settings.
        "baselines": {
            "endpoint": "PUT /vitals/baselines/{expo_user_id}",
            "fields": [
                _field("hrv_year_avg", "float", "Typical HRV",
                       unit="ms", min=10, max=200,
                       description="User's normal resting HRV if known. Leave null if unknown."),
                _field("rhr_year_avg", "float", "Typical Resting HR",
                       unit="bpm", min=30, max=100),
                _field("body_weight_setpoint_lb", "float", "Target Body Weight",
                       unit="lb", min=80, max=400),
                _field("waist_setpoint_in", "float", "Target Waist",
                       unit="in", min=20, max=80),
                _field("protein_floor_g", "float", "Minimum Daily Protein",
                       unit="g", min=50, max=400,
                       description="Default 170g"),
                _field("fat_floor_avg_g", "float", "Minimum Daily Fat",
                       unit="g", min=20, max=200,
                       description="Default 55g"),
                _field("default_kcal", "float", "Baseline Daily Calories",
                       unit="kcal", min=1000, max=6000,
                       description="Default 2695"),
            ],
        },

        # ── RESPONSE SHAPE ────────────────────────────────────────────────────
        # What POST /vitals/daily-log returns. ArcForge renders these fields.
        # Never compute these client-side — always render what the brain returns.
        "response_shape": {
            "recommendation": {
                "arcPhase":               "string — accumulation | expansion | deload | resensitize",
                "arcDay":                 "int — day number within current arc phase",
                "arcTransitionReason":    "string | null — why the phase changed",
                "recommendedLiftMode":    "string — one of lift_modes enum",
                "recommendedCardioMode":  "string — one of cardio_modes enum",
                "recommendedMacroDayType":"string — one of macro_day_types enum",
                "macroTargets": {
                    "proteinG": "float",
                    "carbsG":   "float",
                    "fatG":     "float",
                    "kcal":     "float",
                },
                "flags": {
                    "hrvSuppressed":          "bool — HRV below threshold; reduce intensity",
                    "deloadPhaseActive":      "bool — arc is in deload; show deload banner",
                    "resensitizePhaseActive": "bool — arc is in resensitize; show reset banner",
                    "circadianAlignmentLow":  "bool — sleep timing drifting; flag recovery",
                },
                "adaptationConfidence":   "float 0–1 — below 0.30: show calibrating state",
                "acuteConfidence":        "float 0–1",
                "resourceConfidence":     "float 0–1",
                "reasoning":              "string — plain-language explanation of today's recommendation",
            },
            "crossGearDiagnostics": {
                "strengthWithoutFfm":       "bool — strength rising but lean mass not; neural gain only",
                "ffmFallingUnderLoad":      "bool — lean mass declining despite active training",
                "waistRisingFasterThanFfm": "bool — visceral drift; fat accumulating",
                "sleepDebtAccumulated":     "bool — 3+ nights below 7h in last 7 days",
                "sleepDebtNights7d":        "int — raw count of under-sleep nights",
            },
            "cycles": {
                "adaptation_arc": {
                    "arcPhase":     "string",
                    "arcDay":       "int",
                    "arcStartDate": "string YYYY-MM-DD",
                    "output": {
                        "deloadActive":      "bool",
                        "resensitizeActive": "bool",
                        "narrative":         "string — one-sentence arc status for display",
                    },
                },
            },
        },

        # ── UI RENDERING RULES ────────────────────────────────────────────────
        # ArcForge must follow these — they encode the brain's intent for display.
        "ui_rules": {
            "calibrating_threshold":  0.30,
            "calibrating_message":    "Still calibrating — keep logging daily for accurate guidance.",
            "deload_banner_message":  "Deload phase active. Pull back intensity — recovery is the work.",
            "resensitize_banner_message": "Resensitize phase. Rest, sleep, and eat. Next arc starts soon.",
            "hrv_suppressed_message": "HRV suppressed today. Reduce training intensity.",
            "cross_gear_messages": {
                "strengthWithoutFfm":       "Strength is rising without lean mass gain. Likely neural adaptation — not hypertrophic yet. Prioritize protein and sleep.",
                "ffmFallingUnderLoad":       "Lean mass is declining despite training. Check protein intake and sleep quality.",
                "waistRisingFasterThanFfm":  "Waist is growing faster than lean mass. Review carbohydrate timing and caloric surplus.",
                "sleepDebtAccumulated":      "Sleep debt building. 3+ nights below 7 hours this week. Prioritize sleep before training.",
            },
            "field_source_hints": {
                "wearable_preferred": "Offer manual entry as fallback if no wearable connected",
                "prefilled_from_brain": "Pre-fill from the recommendation returned this morning",
                "brain_computed": "Populated from a previous brain API call — do not ask user to enter manually",
                "generated_on_device": "Generated by the app — never shown to user",
                "scale": "Manual entry — user reads from scale",
            },
        },
    }
