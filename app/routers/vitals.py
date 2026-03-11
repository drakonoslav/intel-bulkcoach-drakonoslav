from datetime import date as DateType, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.vitals_models import (
    VitalsDailyLog, VitalsCardioSession, VitalsLiftSession,
    VitalsNutritionDayTarget, VitalsUserBaselines,
    CARDIO_MODES, LIFT_MODES, MACRO_DAY_TYPES,
)
from app.vitals_engine import compute_daily_recommendation, persist_oscillator_state

router = APIRouter(prefix="/vitals", tags=["vitals"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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

    body_weight_lb: Optional[float] = None
    body_fat_pct: Optional[float] = None
    fat_mass_lb: Optional[float] = None
    fat_free_mass_lb: Optional[float] = None
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
        if v is not None and v not in CARDIO_MODES:
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
    existing = db.query(VitalsDailyLog).filter(
        VitalsDailyLog.expo_user_id == payload.expo_user_id,
        VitalsDailyLog.date == payload.date,
    ).first()

    if not existing:
        existing = VitalsDailyLog(expo_user_id=payload.expo_user_id, date=payload.date)
        db.add(existing)

    for field, val in payload.dict(exclude={"expo_user_id", "date"}).items():
        setattr(existing, field, val)

    db.flush()

    result = compute_daily_recommendation(db, payload.expo_user_id, existing)

    existing.acute_score = result["acuteResult"]["score"]
    existing.resource_score = result["resourceResult"]["score"]
    existing.seasonal_score = result["seasonalResult"]["score"]
    existing.oscillator_composite_score = result["composite"]["compositeScore"]
    existing.oscillator_class = result["composite"]["oscillatorClass"]
    existing.recommended_cardio_mode = result["recommendedCardioMode"]
    existing.recommended_lift_mode = result["recommendedLiftMode"]
    existing.recommended_macro_day = result["recommendedMacroDayType"]

    db.commit()
    persist_oscillator_state(db, payload.expo_user_id, existing, result)

    return {
        "ok": True,
        "date": str(payload.date),
        "expo_user_id": payload.expo_user_id,
        "recommendation": {
            "date": str(payload.date),
            "cycleDay28": result["cycleDay28"],
            "cycleWeekType": result["cycleWeekType"],
            "scores": result["composite"],
            "flags": result["flags"],
            "recommendedCardioMode": result["recommendedCardioMode"],
            "recommendedLiftMode": result["recommendedLiftMode"],
            "recommendedMacroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "macroDelta": result["macroDelta"],
            "mealTimingTargets": result["mealTimingTargets"],
            "reasoning": result["reasoning"],
        },
        "scoreBreakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "seasonal": result["seasonalResult"]["breakdown"],
        },
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
        "cycleWeekType": result["cycleWeekType"],
        "recommendation": {
            "cardioMode": result["recommendedCardioMode"],
            "liftMode": result["recommendedLiftMode"],
            "macroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "mealTimingTargets": result["mealTimingTargets"],
        },
        "flags": result["flags"],
        "reasoning": result["reasoning"],
        "breakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "seasonal": result["seasonalResult"]["breakdown"],
        },
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
    return {
        "date": str(target_date),
        "expo_user_id": expo_user_id,
        "recommendation": {
            "date": str(target_date),
            "cycleDay28": result["cycleDay28"],
            "cycleWeekType": result["cycleWeekType"],
            "scores": result["composite"],
            "flags": result["flags"],
            "recommendedCardioMode": result["recommendedCardioMode"],
            "recommendedLiftMode": result["recommendedLiftMode"],
            "recommendedMacroDayType": result["recommendedMacroDayType"],
            "macroTargets": result["macroTargets"],
            "macroDelta": result["macroDelta"],
            "mealTimingTargets": result["mealTimingTargets"],
            "reasoning": result["reasoning"],
        },
        "scoreBreakdowns": {
            "acute": result["acuteResult"]["breakdown"],
            "resource": result["resourceResult"]["breakdown"],
            "seasonal": result["seasonalResult"]["breakdown"],
        },
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

    result = compute_daily_recommendation(db, expo_user_id, log_row)
    log_row.acute_score = result["acuteResult"]["score"]
    log_row.resource_score = result["resourceResult"]["score"]
    log_row.seasonal_score = result["seasonalResult"]["score"]
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
