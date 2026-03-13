from datetime import date as DateType, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.vitals_models import (
    VitalsDailyLog, VitalsCardioSession, VitalsLiftSession,
    VitalsNutritionDayTarget, VitalsUserBaselines, ArcForgeUser,
    CARDIO_MODES, LIFT_MODES, MACRO_DAY_TYPES,
)
from app.vitals_engine import compute_daily_recommendation, persist_oscillator_state

_DEFAULT_DOB = DateType(1990, 1, 1)


def _auto_register_user(db, expo_user_id: str):
    """Silently create user + baselines if they don't exist. Called by daily-log so entries always save."""
    user = db.query(ArcForgeUser).filter(ArcForgeUser.expo_user_id == expo_user_id).first()
    if not user:
        today = DateType.today()
        age = today.year - _DEFAULT_DOB.year
        age_mode = "early_adult" if age < 35 else ("mature_adult" if age < 50 else "preservation")
        db.add(ArcForgeUser(
            expo_user_id  = expo_user_id,
            username      = "Athlete",
            date_of_birth = _DEFAULT_DOB,
            age_mode      = age_mode,
        ))
        baselines = db.query(VitalsUserBaselines).filter(
            VitalsUserBaselines.expo_user_id == expo_user_id
        ).first()
        if not baselines:
            db.add(VitalsUserBaselines(
                expo_user_id    = expo_user_id,
                age_mode        = age_mode,
                protein_floor_g = 170,
                fat_floor_avg_g = 55,
                default_kcal    = 2695,
            ))
        try:
            db.commit()
        except Exception:
            db.rollback()

router = APIRouter(prefix="/vitals", tags=["vitals"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_data_quality_warnings(result: dict) -> list:
    """Generate human-readable data quality warning strings for Expo to surface."""
    warnings = []
    low_conf = (
        result["acuteResult"].get("lowConfidenceKeys", []) +
        result["resourceResult"].get("lowConfidenceKeys", []) +
        result["adaptationResult"].get("lowConfidenceKeys", [])
    )
    raw = result.get("rawInputs", {})
    s_raw = raw.get("adaptation", {})

    if result["acuteResult"].get("overallConfidence", 1.0) < 0.5:
        warnings.append("bodyCompConfidenceLow")
    if "hrv_state" in low_conf or "hrv_28d_trend" in low_conf:
        warnings.append("hrvDataSparse")
    if "waist_trend" in low_conf or s_raw.get("waist_per_lb_ratio") is None:
        warnings.append("waistMeasurementStale")
    if "ffm_trend" in low_conf or "ffm_28d_trend" in low_conf:
        warnings.append("ffmDataInsufficient")
    if "light_consistency" in low_conf:
        warnings.append("lightExposureNotTracked")
    if "deload_compliance" in low_conf:
        warnings.append("insufficientHistoryForDeloadAssessment")

    return warnings


def _recommendation_block(result: dict) -> dict:
    """Build the standardized recommendation sub-block for all response shapes."""
    return {
        "acuteConfidence": result["acuteResult"].get("overallConfidence"),
        "resourceConfidence": result["resourceResult"].get("overallConfidence"),
        "adaptationConfidence": result["adaptationResult"].get("overallConfidence"),
        "arcPhase": result.get("arcPhase"),
        "arcDay": result.get("arcDay"),
        "arcStartDate": result.get("arcStartDate"),
        "arcTransitionReason": result.get("arcTransitionReason"),
        "lowConfidenceSignals": (
            result["acuteResult"].get("lowConfidenceKeys", []) +
            result["resourceResult"].get("lowConfidenceKeys", []) +
            result["adaptationResult"].get("lowConfidenceKeys", [])
        ),
        "warnings": _build_data_quality_warnings(result),
    }


class BaselineUpsert(BaseModel):
    hrv_year_avg: Optional[float] = None
    rhr_year_avg: Optional[float] = None
    body_weight_setpoint_lb: Optional[float] = None
    waist_setpoint_in: Optional[float] = None
    protein_floor_g: Optional[float] = 170.0
    fat_floor_avg_g: Optional[float] = 55.0
    default_kcal: Optional[float] = 2695.0
    base_protein_g: Optional[float] = None
    base_carbs_g: Optional[float] = None
    base_fat_g: Optional[float] = None
    cycle_start_date: Optional[DateType] = None


class DailyLogIn(BaseModel):
    expo_user_id: str
    date: DateType

    sleep_duration_min: Optional[float] = None
    time_in_bed_min: Optional[float] = None
    sleep_efficiency_pct: Optional[float] = None
    bedtime_local: Optional[datetime] = None
    waketime_local: Optional[datetime] = None
    sleep_midpoint_min: Optional[float] = None
    # Apple Health raw stage breakdown — enter exactly what the app shows
    sleep_awake_min: Optional[float] = None
    sleep_rem_min:   Optional[float] = None
    sleep_core_min:  Optional[float] = None
    sleep_deep_min:  Optional[float] = None
    # HH:MM onset/wake strings — accepts 23:20, 23.20, 2320, 23.2, 5.3 (single digit = ×10 min)
    sleep_onset_hhmm: Optional[str] = Field(None, pattern=r"^\d{1,2}[:\.]?\d{1,2}$")
    sleep_wake_hhmm:  Optional[str] = Field(None, pattern=r"^\d{1,2}[:\.]?\d{1,2}$")

    resting_hr_bpm: Optional[float] = None
    hrv_ms: Optional[float] = None
    walking_hr_avg_bpm: Optional[float] = None
    overnight_hr_avg_bpm: Optional[float] = None
    vo2_estimate: Optional[float] = None

    active_energy_kcal: Optional[float] = None
    exercise_min: Optional[float] = None
    step_count: Optional[int] = None

    cardio_duration_min: Optional[float] = None
    cardio_avg_hr_bpm: Optional[float] = None
    cardio_zone2_min: Optional[float] = None
    cardio_zone3_min: Optional[float] = None
    actual_cardio_mode: Optional[str] = None
    cardio_strain_score: Optional[float] = None

    morning_temp_f: Optional[float] = None
    morning_temp_c: Optional[float] = None
    body_weight_lb: Optional[float] = None
    body_fat_pct: Optional[float] = None
    fat_mass_lb: Optional[float] = None
    fat_free_mass_lb: Optional[float] = None
    skeletal_muscle_pct: Optional[float] = None
    skeletal_muscle_lb: Optional[float] = None
    tbw_pct: Optional[float] = None
    body_comp_confidence: Optional[float] = None

    waist_at_navel_in: Optional[float] = None
    waist_measure_confidence: Optional[float] = None
    waist_notes: Optional[str] = None

    libido_score: Optional[int] = Field(None, ge=1, le=5)
    morning_erection_score: Optional[int] = Field(None, ge=0, le=3)
    motivation_score: Optional[int] = Field(None, ge=1, le=5)
    mood_stability_score: Optional[int] = Field(None, ge=1, le=5)
    soreness_score: Optional[int] = Field(None, ge=1, le=5)
    joint_friction_score: Optional[int] = Field(None, ge=1, le=5)
    mental_drive_score: Optional[int] = Field(None, ge=1, le=5)
    stress_load_score: Optional[int] = Field(None, ge=1, le=5)

    planned_lift_mode: Optional[str] = None
    completed_lift_mode: Optional[str] = None
    lift_readiness_self_score: Optional[int] = None
    top_set_load_index: Optional[float] = None
    top_set_rpe: Optional[float] = None
    strength_output_index: Optional[float] = None
    pump_quality_score: Optional[int] = None
    rep_speed_subjective_score: Optional[int] = None
    session_density_score: Optional[float] = None
    lift_strain_score: Optional[float] = None

    kcal_target: Optional[float] = None
    kcal_actual: Optional[float] = None
    protein_g_target: Optional[float] = None
    protein_g_actual: Optional[float] = None
    carbs_g_target: Optional[float] = None
    carbs_g_actual: Optional[float] = None
    fat_g_target: Optional[float] = None
    fat_g_actual: Optional[float] = None

    notes: Optional[str] = None

    @validator("actual_cardio_mode")
    def validate_cardio_mode(cls, v):
        if v is None:
            return v
        _normalize = {"zone1": "recovery_walk", "zone2": "zone_2", "zone3": "zone_3"}
        v = _normalize.get(v, v)
        if v not in CARDIO_MODES:
            raise ValueError(f"actual_cardio_mode must be one of {CARDIO_MODES}")
        return v

    @validator("planned_lift_mode", "completed_lift_mode")
    def validate_lift_mode(cls, v):
        if v is not None and v not in LIFT_MODES:
            raise ValueError(f"lift_mode must be one of {LIFT_MODES}")
        return v


class CardioSessionIn(BaseModel):
    expo_user_id: str
    date: DateType
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_min: Optional[float] = None
    avg_hr_bpm: Optional[float] = None
    max_hr_bpm: Optional[float] = None
    zone2_min: Optional[float] = None
    zone3_min: Optional[float] = None
    mode: str
    strain_score: Optional[float] = None
    source: Optional[str] = "manual"

    @validator("mode")
    def validate_mode(cls, v):
        _normalize = {"zone1": "recovery_walk", "zone2": "zone_2", "zone3": "zone_3"}
        v = _normalize.get(v, v)
        if v not in CARDIO_MODES:
            raise ValueError(f"mode must be one of {CARDIO_MODES}")
        return v


class LiftSessionIn(BaseModel):
    expo_user_id: str
    date: DateType
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_min: Optional[float] = None
    planned_lift_mode: Optional[str] = None
    completed_lift_mode: Optional[str] = None
    lift_readiness_self_score: Optional[int] = None
    top_set_load_index: Optional[float] = None
    top_set_rpe: Optional[float] = None
    strength_output_index: Optional[float] = None
    session_density_score: Optional[float] = None
    pump_quality_score: Optional[int] = None
    rep_speed_subjective_score: Optional[int] = None
    lift_strain_score: Optional[float] = None
    notes: Optional[str] = None


class NutritionTargetIn(BaseModel):
    expo_user_id: str
    date: DateType
    macro_day_type: str
    kcal_target: float
    protein_g_target: float
    carbs_g_target: float
    fat_g_target: float
    pre_cardio_carbs_g: Optional[float] = None
    post_cardio_protein_g: Optional[float] = None
    post_cardio_carbs_g: Optional[float] = None
    post_cardio_fat_g: Optional[float] = None
    meal2_protein_g: Optional[float] = None
    meal2_carbs_g: Optional[float] = None
    meal2_fat_g: Optional[float] = None
    pre_lift_protein_g: Optional[float] = None
    pre_lift_carbs_g: Optional[float] = None
    pre_lift_fat_g: Optional[float] = None
    post_lift_protein_g: Optional[float] = None
    post_lift_carbs_g: Optional[float] = None
    post_lift_fat_g: Optional[float] = None
    final_meal_protein_g: Optional[float] = None
    final_meal_carbs_g: Optional[float] = None
    final_meal_fat_g: Optional[float] = None

    @validator("macro_day_type")
    def validate_macro_day(cls, v):
        if v not in MACRO_DAY_TYPES:
            raise ValueError(f"macro_day_type must be one of {MACRO_DAY_TYPES}")
        return v


def _log_to_dict(row: VitalsDailyLog) -> dict:
    return {
        "id": row.id,
        "expo_user_id": row.expo_user_id,
        "date": str(row.date),
        "sleep_duration_min": float(row.sleep_duration_min) if row.sleep_duration_min else None,
        "hrv_ms": float(row.hrv_ms) if row.hrv_ms else None,
        "resting_hr_bpm": float(row.resting_hr_bpm) if row.resting_hr_bpm else None,
        "body_weight_lb": float(row.body_weight_lb) if row.body_weight_lb else None,
        "fat_free_mass_lb": float(row.fat_free_mass_lb) if row.fat_free_mass_lb else None,
        "waist_at_navel_in": float(row.waist_at_navel_in) if row.waist_at_navel_in else None,
        "acute_score": float(row.acute_score) if row.acute_score else None,
        "resource_score": float(row.resource_score) if row.resource_score else None,
        "seasonal_score": float(row.seasonal_score) if row.seasonal_score else None,
        "oscillator_composite_score": float(row.oscillator_composite_score) if row.oscillator_composite_score else None,
        "oscillator_class": row.oscillator_class,
        "recommended_cardio_mode": row.recommended_cardio_mode,
        "recommended_lift_mode": row.recommended_lift_mode,
        "recommended_macro_day": row.recommended_macro_day,
        "kcal_actual": float(row.kcal_actual) if row.kcal_actual else None,
        "protein_g_actual": float(row.protein_g_actual) if row.protein_g_actual else None,
        "carbs_g_actual": float(row.carbs_g_actual) if row.carbs_g_actual else None,
        "fat_g_actual": float(row.fat_g_actual) if row.fat_g_actual else None,
    }


@router.get("/baselines/{expo_user_id}")
def get_baselines(expo_user_id: str, db: Session = Depends(get_db)):
    row = db.query(VitalsUserBaselines).filter(VitalsUserBaselines.expo_user_id == expo_user_id).first()
    if not row:
        return {"expo_user_id": expo_user_id, "baselines": None, "using_defaults": True}
    return {
        "expo_user_id": expo_user_id,
        "baselines": {
            "hrv_year_avg": float(row.hrv_year_avg) if row.hrv_year_avg else None,
            "rhr_year_avg": float(row.rhr_year_avg) if row.rhr_year_avg else None,
            "body_weight_setpoint_lb": float(row.body_weight_setpoint_lb) if row.body_weight_setpoint_lb else None,
            "waist_setpoint_in": float(row.waist_setpoint_in) if row.waist_setpoint_in else None,
            "protein_floor_g": float(row.protein_floor_g) if row.protein_floor_g else None,
            "fat_floor_avg_g": float(row.fat_floor_avg_g) if row.fat_floor_avg_g else None,
            "default_kcal": float(row.default_kcal) if row.default_kcal else None,
            "base_protein_g": float(row.base_protein_g) if row.base_protein_g else None,
            "base_carbs_g": float(row.base_carbs_g) if row.base_carbs_g else None,
            "base_fat_g": float(row.base_fat_g) if row.base_fat_g else None,
            "cycle_start_date": str(row.cycle_start_date) if row.cycle_start_date else None,
        },
        "using_defaults": False,
    }


# ── displaySpec helpers (module-level so GET endpoint can reuse them) ─────────

def _ds_score_color(score):
    if score is None: return "grey"
    if score >= 67:   return "green"
    if score >= 34:   return "yellow"
    return "red"

def _ds_min_to_hhmm(mins):
    if mins is None: return None
    h = int(float(mins)) // 60
    m = int(float(mins)) % 60
    return f"{h}h {m:02d}m"

def _ds_midpoint_clock(mins):
    if mins is None: return None
    h = int(float(mins)) // 60
    m = int(float(mins)) % 60
    suffix = "AM" if h < 12 else "PM"
    h12 = h if h <= 12 else h - 12
    if h12 == 0: h12 = 12
    return f"{h12}:{m:02d} {suffix}"

def build_display_spec(result, log_row):
    """Build a display-ready spec from a computed recommendation result + log row.
    Every value has a human-readable .display string — Expo loops and renders, no logic needed.
    """
    _sleep_dur = float(log_row.sleep_duration_min)   if log_row.sleep_duration_min  else None
    _sleep_eff = float(log_row.sleep_efficiency_pct) if log_row.sleep_efficiency_pct else None
    _sleep_mid = float(log_row.sleep_midpoint_min)   if log_row.sleep_midpoint_min   else None
    _sleep_tib = float(log_row.time_in_bed_min)      if log_row.time_in_bed_min      else None
    _rem       = float(log_row.sleep_rem_min)        if log_row.sleep_rem_min        else None
    _core      = float(log_row.sleep_core_min)       if log_row.sleep_core_min       else None
    _deep      = float(log_row.sleep_deep_min)       if log_row.sleep_deep_min       else None
    _awake     = float(log_row.sleep_awake_min)      if log_row.sleep_awake_min      else None

    sleep_summary = {
        "duration":   {"value": _sleep_dur, "display": _ds_min_to_hhmm(_sleep_dur),  "label": "Total Sleep"},
        "efficiency": {"value": _sleep_eff, "display": f"{_sleep_eff:.1f}%" if _sleep_eff else None, "label": "Efficiency"},
        "midpoint":   {"value": _sleep_mid, "display": _ds_midpoint_clock(_sleep_mid), "label": "Midpoint"},
        "timeInBed":  {"value": _sleep_tib, "display": _ds_min_to_hhmm(_sleep_tib),  "label": "Time in Bed"},
        "stages": {
            "rem":   {"value": _rem,   "display": _ds_min_to_hhmm(_rem),   "label": "REM"},
            "core":  {"value": _core,  "display": _ds_min_to_hhmm(_core),  "label": "Core"},
            "deep":  {"value": _deep,  "display": _ds_min_to_hhmm(_deep),  "label": "Deep"},
            "awake": {"value": _awake, "display": _ds_min_to_hhmm(_awake), "label": "Awake"},
        },
    }

    _a = result["acuteResult"]["score"]
    _r = result["resourceResult"]["score"]
    _s = result["adaptationResult"]["score"]
    score_cards = [
        {"id": "acute",      "label": "Acute Readiness",   "sublabel": "Today's recovery state",         "score": _a, "maxScore": 100, "color": _ds_score_color(_a), "confidence": result["acuteResult"].get("overallConfidence"),      "topDrivers": (result["acuteResult"].get("breakdown")      or [])[:3]},
        {"id": "resource",   "label": "Resource Tank",      "sublabel": "7-day training & nutrition load", "score": _r, "maxScore": 100, "color": _ds_score_color(_r), "confidence": result["resourceResult"].get("overallConfidence"),   "topDrivers": (result["resourceResult"].get("breakdown")   or [])[:3]},
        {"id": "adaptation", "label": "Adaptation Arc",     "sublabel": "28-day trend trajectory",        "score": _s, "maxScore": 100, "color": _ds_score_color(_s), "confidence": result["adaptationResult"].get("overallConfidence"), "topDrivers": (result["adaptationResult"].get("breakdown") or [])[:3]},
    ]

    _warn_map = {
        "bodyCompConfidenceLow":                  {"type": "warn", "message": "Body composition data is sparse. Add a weekly measurement to sharpen recommendations."},
        "hrvDataSparse":                          {"type": "warn", "message": "HRV baseline is still building. Keep logging daily for more accurate readiness scores."},
        "waistMeasurementStale":                  {"type": "info", "message": "Waist measurement is stale. Log a new waist reading when you get a chance."},
        "ffmDataInsufficient":                    {"type": "warn", "message": "Fat-free mass history is too short to trend. Keep logging body composition weekly."},
        "lightExposureNotTracked":                {"type": "info", "message": "Sunlight exposure isn't being tracked. This affects adaptation score accuracy."},
        "insufficientHistoryForDeloadAssessment": {"type": "info", "message": "Not enough history yet to assess deload compliance. Recommendations improve over 4+ weeks."},
    }
    _flag_map = {
        "hardStopFatigue":        {"type": "stop", "message": "Hard stop — fatigue signals are high. Today is a mandatory recovery day."},
        "lowSleep":               {"type": "warn", "message": f"Sleep was below 6 hours ({_ds_min_to_hhmm(_sleep_dur) or '—'}). Recovery mode applied."},
        "suppressedHrv":          {"type": "warn", "message": "HRV is suppressed below your baseline. Extra recovery recommended."},
        "elevatedRhr":            {"type": "warn", "message": "Resting heart rate is elevated above your baseline. Monitor recovery."},
        "resensitizePhaseActive": {"type": "info", "message": "Resensitize phase active. Reduced volume and recalibration in effect."},
        "deloadPhaseActive":      {"type": "info", "message": "Deload phase active. Reduced load is intentional — trust the process."},
    }
    notices = []
    for flag, active in result["flags"].items():
        if active and flag in _flag_map:
            notices.insert(0, _flag_map[flag])
    for w in _build_data_quality_warnings(result):
        notices.append(_warn_map.get(w, {"type": "info", "message": w}))
    cg = result.get("crossGearDiagnostics", {})
    if cg.get("strengthWithoutFfm"):
        notices.append({"type": "warn", "message": "Strength trending up but muscle mass isn't following. Check protein and recovery quality."})
    if cg.get("ffmFallingUnderLoad"):
        notices.append({"type": "stop", "message": "Muscle mass declining under training load. Increase calories and protein immediately."})
    if cg.get("waistRisingFasterThanFfm"):
        notices.append({"type": "warn", "message": "Waist growing faster than muscle. Fat gain is outpacing muscle gain — review nutrition."})

    mt = result["mealTimingTargets"]
    meal_timing = {
        "label": "Meal Timing Targets",
        "sections": [
            {"label": "Pre-Cardio",     "time": "05:30", "carbsG":   mt.get("preCardioCarbsG")},
            {"label": "Post-Cardio",    "time": "06:45", "proteinG": mt.get("postCardioProteinG"), "carbsG": mt.get("postCardioCarbsG"), "fatG": mt.get("postCardioFatG")},
            {"label": "Mid-Morning",    "time": "11:30", "proteinG": mt.get("meal2ProteinG"),       "carbsG": mt.get("meal2CarbsG"),      "fatG": mt.get("meal2FatG")},
            {"label": "Pre-Lift",       "time": "15:45", "proteinG": mt.get("preLiftProteinG"),     "carbsG": mt.get("preLiftCarbsG"),    "fatG": mt.get("preLiftFatG")},
            {"label": "Post-Lift",      "time": "18:20", "proteinG": mt.get("postLiftProteinG"),    "carbsG": mt.get("postLiftCarbsG"),   "fatG": mt.get("postLiftFatG")},
            {"label": "Evening Meal",   "time": "20:00", "proteinG": mt.get("finalMealProteinG"),   "carbsG": mt.get("finalMealCarbsG"),  "fatG": mt.get("finalMealFatG")},
            {"label": "Evening Protein","time": "21:30", "note": "Intel-managed — baseline 0g Whey"},
        ],
    }

    return {
        "scoreCards":   score_cards,
        "sleepSummary": sleep_summary,
        "notices":      notices,
        "insights":     result.get("reasoning", []),
        "mealTiming":   meal_timing,
    }


@router.put("/baselines/{expo_user_id}")
def upsert_baselines(expo_user_id: str, payload: BaselineUpsert, db: Session = Depends(get_db)):
    row = db.query(VitalsUserBaselines).filter(VitalsUserBaselines.expo_user_id == expo_user_id).first()
    if not row:
        row = VitalsUserBaselines(expo_user_id=expo_user_id)
        db.add(row)
    for field, val in payload.dict(exclude_none=True).items():
        setattr(row, field, val)
    db.commit()
    return {"ok": True, "expo_user_id": expo_user_id}


@router.post("/daily-log")
def post_daily_log(payload: DailyLogIn, db: Session = Depends(get_db)):
    _auto_register_user(db, payload.expo_user_id)

    existing = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == payload.expo_user_id,
        VitalsDailyLog.date == payload.date,
    ).first()

    if not existing:
        existing = VitalsDailyLog(expo_user_id=payload.expo_user_id, date=payload.date)
        db.add(existing)

    for field, val in payload.dict(exclude={"expo_user_id", "date"}).items():
        setattr(existing, field, val)

    # ── SLEEP AUTO-DERIVATION ─────────────────────────────────────────────────
    # All computation happens server-side so the user never does math.
    # Priority: explicit values always win; derived values fill gaps only.

    def _normalise_stage_min(val) -> float:
        """Normalise a sleep stage float to minutes.
        If the decimal part × 100 is 01-59 we treat the value as HH.MM format,
        i.e. 1.25 → 1h25m = 85 min.  Pure integers or decimals outside 01-59
        are returned unchanged (already raw minutes).
        """
        if val is None:
            return None
        val = float(val)
        frac = val - int(val)
        mm_candidate = round(frac * 100)
        if 1 <= mm_candidate <= 59:
            return int(val) * 60 + mm_candidate
        return val

    # Normalise all stage fields so users can type e.g. 1.25 for 1h25m
    for _stage_field in ("sleep_awake_min", "sleep_rem_min", "sleep_core_min", "sleep_deep_min"):
        _raw = getattr(existing, _stage_field, None)
        if _raw is not None:
            setattr(existing, _stage_field, _normalise_stage_min(_raw))

    def _hhmm_to_total_min(s: str) -> float:
        """Parse sleep time string → total minutes from midnight.
        Accepts: '23:20', '23.20', '2320', '23.2', '5.3'
        Single digit after separator = ×10 (so .2 = 20 min, .3 = 30 min).
        """
        s = s.strip()
        if ":" in s:
            h, m = s.split(":")
        elif "." in s:
            h, m = s.split(".")
        elif len(s) == 4:
            h, m = s[:2], s[2:]
        elif len(s) == 3:
            h, m = s[:1], s[1:]
        else:
            raise ValueError(f"Unrecognised time format: {s!r}")
        # Single digit after separator means tens-of-minutes (e.g. .2 = 20 min)
        if len(m) == 1:
            m = m + "0"
        return int(h) * 60 + int(m)

    # 1. sleep_duration_min — derive from stages if not provided directly
    if existing.sleep_duration_min is None:
        _stage_sum = sum(
            float(v) for v in [
                existing.sleep_rem_min, existing.sleep_core_min, existing.sleep_deep_min
            ] if v is not None
        )
        if _stage_sum > 0:
            existing.sleep_duration_min = _stage_sum

    # 2. time_in_bed_min — derive from all stages including awake
    if existing.time_in_bed_min is None:
        _bed_sum = sum(
            float(v) for v in [
                existing.sleep_awake_min, existing.sleep_rem_min,
                existing.sleep_core_min, existing.sleep_deep_min
            ] if v is not None
        )
        if _bed_sum > 0:
            existing.time_in_bed_min = _bed_sum

    # 3. sleep_efficiency_pct — derive from stages if not provided
    if existing.sleep_efficiency_pct is None:
        if existing.sleep_duration_min and existing.time_in_bed_min and existing.time_in_bed_min > 0:
            existing.sleep_efficiency_pct = round(
                float(existing.sleep_duration_min) / float(existing.time_in_bed_min) * 100, 1
            )

    # 4. sleep_midpoint_min — derive from HH:MM strings (simplest Apple Health path)
    if existing.sleep_midpoint_min is None and existing.sleep_onset_hhmm and existing.sleep_wake_hhmm:
        _onset = _hhmm_to_total_min(existing.sleep_onset_hhmm)
        _wake  = _hhmm_to_total_min(existing.sleep_wake_hhmm)
        # Handle crossing midnight (e.g. onset 23:20, wake 05:05)
        if _wake < _onset:
            _wake += 1440
        _mid = _onset + (_wake - _onset) / 2
        existing.sleep_midpoint_min = round(_mid % 1440, 1)

    # 5. Fallback: derive midpoint from bedtime_local + waketime_local datetime objects
    elif existing.sleep_midpoint_min is None and existing.bedtime_local and existing.waketime_local:
        from datetime import timedelta as _td
        _mid = existing.bedtime_local + (existing.waketime_local - existing.bedtime_local) / 2
        existing.sleep_midpoint_min = _mid.hour * 60 + _mid.minute

    # 6. Last resort: bedtime + half duration
    elif existing.sleep_midpoint_min is None and existing.bedtime_local and existing.sleep_duration_min:
        from datetime import timedelta as _td
        _mid = existing.bedtime_local + _td(minutes=float(existing.sleep_duration_min) / 2)
        existing.sleep_midpoint_min = _mid.hour * 60 + _mid.minute

    # ── TEMPERATURE AUTO-CONVERSION ───────────────────────────────────────────
    # Accept either unit; derive the other automatically.
    if existing.morning_temp_f is None and existing.morning_temp_c is not None:
        existing.morning_temp_f = round(float(existing.morning_temp_c) * 9 / 5 + 32, 2)
    elif existing.morning_temp_c is None and existing.morning_temp_f is not None:
        existing.morning_temp_c = round((float(existing.morning_temp_f) - 32) * 5 / 9, 2)

    # ── BODY COMPOSITION AUTO-DERIVATION ─────────────────────────────────────
    _wt  = float(existing.body_weight_lb)   if existing.body_weight_lb  else None
    _bfp = float(existing.body_fat_pct)     if existing.body_fat_pct    else None
    _smp = float(existing.skeletal_muscle_pct) if existing.skeletal_muscle_pct else None

    # fat_mass_lb from weight × body_fat_pct — no extra data needed from user
    if existing.fat_mass_lb is None and _wt and _bfp:
        existing.fat_mass_lb = round(_wt * _bfp / 100, 2)

    # fat_free_mass_lb from weight − fat_mass (only if user didn't supply it)
    if existing.fat_free_mass_lb is None and _wt and existing.fat_mass_lb:
        existing.fat_free_mass_lb = round(_wt - float(existing.fat_mass_lb), 2)

    # skeletal_muscle_lb from weight × skeletal_muscle_pct
    if existing.skeletal_muscle_lb is None and _wt and _smp:
        existing.skeletal_muscle_lb = round(_wt * _smp / 100, 2)

    db.flush()

    result = compute_daily_recommendation(db, payload.expo_user_id, existing)

    existing.acute_score = result["acuteResult"]["score"]
    existing.resource_score = result["resourceResult"]["score"]
    existing.seasonal_score = result["adaptationResult"]["score"]
    existing.oscillator_composite_score = result["composite"]["compositeScore"]
    existing.oscillator_class = result["composite"]["oscillatorClass"]
    existing.recommended_cardio_mode = result["recommendedCardioMode"]
    existing.recommended_lift_mode = result["recommendedLiftMode"]
    existing.recommended_macro_day = result["recommendedMacroDayType"]

    db.commit()
    persist_oscillator_state(db, payload.expo_user_id, existing, result)

    # ── CSV BACKUP — every log appended to data/daily_log.csv ────────────────
    try:
        from app.csv_log import append_log
        _csv_row = payload.dict()
        _csv_row["date"] = str(payload.date)
        # write resolved (normalised) stage values so CSV reflects actual minutes
        for _sf in ("sleep_rem_min", "sleep_core_min", "sleep_deep_min", "sleep_awake_min"):
            _csv_row[_sf] = getattr(existing, _sf, None)
        append_log(_csv_row)
    except Exception as _e:
        print(f"[csv_log] non-fatal write error: {_e}")

    display_spec = build_display_spec(result, existing)

    return {
        "ok": True,
        "date": str(payload.date),
        "expo_user_id": payload.expo_user_id,
        "displaySpec": display_spec,
        "recommendation": {
            "date": str(payload.date),
            "cycleDay28": result["cycleDay28"],
            "arcPhase": result["arcPhase"],
            "arcDay": result["arcDay"],
            "arcStartDate": result.get("arcStartDate"),
            "scores": result["composite"],
            "acuteConfidence": result["acuteResult"].get("overallConfidence"),
            "resourceConfidence": result["resourceResult"].get("overallConfidence"),
            "adaptationConfidence": result["adaptationResult"].get("overallConfidence"),
            "lowConfidenceSignals": (
                result["acuteResult"].get("lowConfidenceKeys", []) +
                result["resourceResult"].get("lowConfidenceKeys", []) +
                result["adaptationResult"].get("lowConfidenceKeys", [])
            ),
            "warnings": _build_data_quality_warnings(result),
            "flags": result["flags"],
            "recommendedCardioMode": result["recommendedCardioMode"],
            "recommendedLiftMode": result["recommendedLiftMode"],
            "recommendedMacroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "macroDelta": result["macroDelta"],
            "mealTimingTargets": result["mealTimingTargets"],
            "reasoning": result["reasoning"],
        },
        "cycles": result["cycles"],
        "crossGearDiagnostics": result.get("crossGearDiagnostics", {}),
        "scoreBreakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "adaptation": result["adaptationResult"]["breakdown"],
        },
        "rawInputs": result["rawInputs"],
    }


@router.get("/dashboard")
def get_dashboard(
    expo_user_id: str = Query(...),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    target_date = DateType.fromisoformat(date) if date else DateType.today()
    log_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == target_date,
    ).first()

    if not log_row:
        raise HTTPException(status_code=404, detail=f"No vitals log found for {expo_user_id} on {target_date}")

    result = compute_daily_recommendation(db, expo_user_id, log_row)
    refs = result["refs"]

    return {
        "date": str(target_date),
        "expo_user_id": expo_user_id,
        "scores": result["composite"],
        "today": {
            "bodyWeightLb": float(log_row.body_weight_lb) if log_row.body_weight_lb else None,
            "bodyFatPct": float(log_row.body_fat_pct) if log_row.body_fat_pct else None,
            "fatFreeMassLb": float(log_row.fat_free_mass_lb) if log_row.fat_free_mass_lb else None,
            "waistAtNavelIn": float(log_row.waist_at_navel_in) if log_row.waist_at_navel_in else None,
            "restingHrBpm": float(log_row.resting_hr_bpm) if log_row.resting_hr_bpm else None,
            "hrvMs": float(log_row.hrv_ms) if log_row.hrv_ms else None,
            "sleepDurationMin": float(log_row.sleep_duration_min) if log_row.sleep_duration_min else None,
            "kcalActual": float(log_row.kcal_actual) if log_row.kcal_actual else None,
            "proteinGActual": float(log_row.protein_g_actual) if log_row.protein_g_actual else None,
            "carbsGActual": float(log_row.carbs_g_actual) if log_row.carbs_g_actual else None,
            "fatGActual": float(log_row.fat_g_actual) if log_row.fat_g_actual else None,
        },
        "trends": {
            "weightTrend14dLbPerWeek": refs["weightTrend14dLbPerWeek"],
            "ffmTrend14dLbPerWeek": refs["ffmTrend14dLbPerWeek"],
            "strengthTrend14dPct": refs["strengthTrend14dPct"],
            "waistChange14dIn": refs["waistChange14dIn"],
            "hrv28dAvg": refs["hrv28dAvg"],
            "rhr28dAvg": refs["rhr28dAvg"],
        },
        "weeklyDistribution": {
            "zone2Count7d": refs["cardioZone2Count7d"],
            "zone3Count7d": refs["cardioZone3Count7d"],
            "recoveryCount7d": refs["cardioRecoveryCount7d"],
            "neuralLiftCount7d": refs["neuralLiftCount7d"],
        },
        "cycleDay28": result["cycleDay28"],
        "arcPhase": result["arcPhase"],
        "arcDay": result["arcDay"],
        "arcStartDate": result.get("arcStartDate"),
        "recommendation": {
            "cardioMode": result["recommendedCardioMode"],
            "liftMode": result["recommendedLiftMode"],
            "macroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "mealTimingTargets": result["mealTimingTargets"],
        },
        "flags": result["flags"],
        "reasoning": result["reasoning"],
        "cycles": result["cycles"],
        "breakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "adaptation": result["adaptationResult"]["breakdown"],
        },
    }


@router.get("/display-spec")
def get_display_spec(
    expo_user_id: str = Query(..., description="Expo device UUID for this user"),
    date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD (defaults to today)"),
    db: Session = Depends(get_db)
):
    """
    Returns the fully formatted displaySpec for the user's vitals log on a given date.

    This is the exact same displaySpec block returned inside POST /daily-log,
    available as a standalone GET so the Today screen can load it without resubmitting.

    Every value has a human-readable .display string. No math or conditionals needed in Expo.

    scoreCards[]  — Acute / Resource / Adaptation scores with color + topDrivers
    sleepSummary  — duration, efficiency, midpoint, timeInBed, stages (rem/core/deep/awake)
    notices[]     — type: "stop" | "warn" | "info" with pre-written message strings
    insights[]    — Plain-text reasoning sentences
    mealTiming    — Per-meal protein/carbs/fat targets in grams
    """
    target_date = DateType.fromisoformat(date) if date else DateType.today()
    log_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == target_date,
    ).first()

    if not log_row:
        raise HTTPException(
            status_code=404,
            detail=f"No vitals log found for {expo_user_id} on {target_date}. POST /vitals/daily-log first."
        )

    result = compute_daily_recommendation(db, expo_user_id, log_row)
    return {
        "ok": True,
        "date": str(target_date),
        "expo_user_id": expo_user_id,
        "displaySpec": build_display_spec(result, log_row),
    }


@router.get("/recommendation")
def get_recommendation(
    expo_user_id: str = Query(...),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    target_date = DateType.fromisoformat(date) if date else DateType.today()
    log_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == target_date,
    ).first()

    if not log_row:
        raise HTTPException(status_code=404, detail=f"No vitals log for {expo_user_id} on {target_date}")

    result = compute_daily_recommendation(db, expo_user_id, log_row)
    conf = _recommendation_block(result)
    return {
        "date": str(target_date),
        "expo_user_id": expo_user_id,
        "recommendation": {
            "date": str(target_date),
            "cycleDay28": result["cycleDay28"],
            "arcPhase": result["arcPhase"],
            "arcDay": result["arcDay"],
            "arcStartDate": result.get("arcStartDate"),
            "scores": result["composite"],
            **conf,
            "flags": result["flags"],
            "recommendedCardioMode": result["recommendedCardioMode"],
            "recommendedLiftMode": result["recommendedLiftMode"],
            "recommendedMacroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "macroDelta": result["macroDelta"],
            "mealTimingTargets": result["mealTimingTargets"],
            "reasoning": result["reasoning"],
        },
        "cycles": result["cycles"],
        "crossGearDiagnostics": result.get("crossGearDiagnostics", {}),
        "scoreBreakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "adaptation": result["adaptationResult"]["breakdown"],
        },
        "rawInputs": result["rawInputs"],
    }


@router.post("/cardio-session")
def post_cardio_session(payload: CardioSessionIn, db: Session = Depends(get_db)):
    session = VitalsCardioSession(
        expo_user_id=payload.expo_user_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_min=payload.duration_min,
        avg_hr_bpm=payload.avg_hr_bpm,
        max_hr_bpm=payload.max_hr_bpm,
        zone2_min=payload.zone2_min,
        zone3_min=payload.zone3_min,
        mode=payload.mode,
        strain_score=payload.strain_score,
        source=payload.source or "manual",
    )
    db.add(session)
    db.commit()
    return {"ok": True, "id": session.id}


@router.post("/lift-session")
def post_lift_session(payload: LiftSessionIn, db: Session = Depends(get_db)):
    session = VitalsLiftSession(
        expo_user_id=payload.expo_user_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_min=payload.duration_min,
        planned_lift_mode=payload.planned_lift_mode,
        completed_lift_mode=payload.completed_lift_mode,
        lift_readiness_self_score=payload.lift_readiness_self_score,
        top_set_load_index=payload.top_set_load_index,
        top_set_rpe=payload.top_set_rpe,
        strength_output_index=payload.strength_output_index,
        session_density_score=payload.session_density_score,
        pump_quality_score=payload.pump_quality_score,
        rep_speed_subjective_score=payload.rep_speed_subjective_score,
        lift_strain_score=payload.lift_strain_score,
        notes=payload.notes,
    )
    db.add(session)
    db.commit()
    return {"ok": True, "id": session.id}


@router.post("/nutrition-target")
def post_nutrition_target(payload: NutritionTargetIn, db: Session = Depends(get_db)):
    existing = db.query(VitalsNutritionDayTarget).filter(
        VitalsNutritionDayTarget.expo_user_id == payload.expo_user_id,
        VitalsNutritionDayTarget.date == payload.date,
    ).first()
    if not existing:
        existing = VitalsNutritionDayTarget(expo_user_id=payload.expo_user_id, date=payload.date)
        db.add(existing)
    for field, val in payload.dict(exclude={"expo_user_id", "date"}).items():
        setattr(existing, field, val)
    db.commit()
    return {"ok": True, "id": existing.id}


@router.post("/recompute")
def recompute(
    expo_user_id: str = Query(...),
    date: str = Query(...),
    db: Session = Depends(get_db)
):
    target_date = DateType.fromisoformat(date)
    log_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date == target_date,
    ).first()
    if not log_row:
        raise HTTPException(status_code=404, detail=f"No vitals log for {expo_user_id} on {target_date}")

    # Backfill sleep_midpoint_min from stored bedtime/waketime if still null
    if log_row.sleep_midpoint_min is None and log_row.bedtime_local and log_row.waketime_local:
        from datetime import timedelta as _td
        _mid = log_row.bedtime_local + (log_row.waketime_local - log_row.bedtime_local) / 2
        log_row.sleep_midpoint_min = _mid.hour * 60 + _mid.minute
    elif log_row.sleep_midpoint_min is None and log_row.bedtime_local and log_row.sleep_duration_min:
        from datetime import timedelta as _td
        _mid = log_row.bedtime_local + _td(minutes=float(log_row.sleep_duration_min) / 2)
        log_row.sleep_midpoint_min = _mid.hour * 60 + _mid.minute

    result = compute_daily_recommendation(db, expo_user_id, log_row)
    log_row.acute_score = result["acuteResult"]["score"]
    log_row.resource_score = result["resourceResult"]["score"]
    log_row.seasonal_score = result["adaptationResult"]["score"]
    log_row.oscillator_composite_score = result["composite"]["compositeScore"]
    log_row.oscillator_class = result["composite"]["oscillatorClass"]
    log_row.recommended_cardio_mode = result["recommendedCardioMode"]
    log_row.recommended_lift_mode = result["recommendedLiftMode"]
    log_row.recommended_macro_day = result["recommendedMacroDayType"]
    db.commit()
    persist_oscillator_state(db, expo_user_id, log_row, result)

    return {"ok": True, "recomputed": True, "date": date, "composite": result["composite"]}


@router.get("/history")
def get_history(
    expo_user_id: str = Query(...),
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    from datetime import timedelta
    cutoff = DateType.today() - timedelta(days=days)
    rows = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.date >= cutoff,
    ).order_by(VitalsDailyLog.date.desc()).all()

    return {
        "expo_user_id": expo_user_id,
        "days": days,
        "count": len(rows),
        "logs": [_log_to_dict(r) for r in rows],
    }


@router.get("/recommendation/latest")
def get_latest_recommendation(
    expo_user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    log_row = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == expo_user_id,
        VitalsDailyLog.oscillator_composite_score.isnot(None),
    ).order_by(VitalsDailyLog.date.desc()).first()

    if not log_row:
        raise HTTPException(status_code=404, detail=f"No computed recommendation found for {expo_user_id}")

    result = compute_daily_recommendation(db, expo_user_id, log_row)
    conf = _recommendation_block(result)
    return {
        "date": str(log_row.date),
        "expo_user_id": expo_user_id,
        "recommendation": {
            "date": str(log_row.date),
            "cycleDay28": result["cycleDay28"],
            "arcPhase": result["arcPhase"],
            "arcDay": result["arcDay"],
            "arcStartDate": result.get("arcStartDate"),
            "scores": result["composite"],
            **conf,
            "flags": result["flags"],
            "recommendedCardioMode": result["recommendedCardioMode"],
            "recommendedLiftMode": result["recommendedLiftMode"],
            "recommendedMacroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "macroDelta": result["macroDelta"],
            "mealTimingTargets": result["mealTimingTargets"],
            "reasoning": result["reasoning"],
        },
        "cycles": result["cycles"],
        "scoreBreakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "adaptation": result["adaptationResult"]["breakdown"],
        },
        "rawInputs": result["rawInputs"],
    }
