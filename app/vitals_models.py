from sqlalchemy import (
    Column, Integer, String, Float, Numeric, Date, Text, Boolean,
    UniqueConstraint, CheckConstraint, Enum, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base
import enum


CARDIO_MODES = ("recovery_walk", "zone_2", "zone_3")
LIFT_MODES = ("off", "mobility", "recovery_patterning", "pump", "hypertrophy_build", "neural_tension")
MACRO_DAY_TYPES = ("surge", "build", "reset", "resensitize")
OSCILLATOR_CLASSES = ("peak", "strong_build", "controlled_build", "reset", "resensitize")
CYCLE_WEEK_TYPES = ("prime", "overload", "peak", "resensitize")
SESSION_SOURCES = ("apple_health", "manual", "imported")


class MovementPattern(enum.Enum):
    horizontal_push = "horizontal_push"
    vertical_push = "vertical_push"
    horizontal_pull = "horizontal_pull"
    vertical_pull = "vertical_pull"
    hip_hinge = "hip_hinge"
    squat = "squat"
    lunge = "lunge"
    carry = "carry"
    isolation = "isolation"
    core = "core"
    conditioning = "conditioning"


class VitalsUserBaselines(Base):
    __tablename__ = "vitals_user_baselines"

    expo_user_id = Column(String, primary_key=True)
    hrv_year_avg = Column(Numeric(8, 2))
    rhr_year_avg = Column(Numeric(8, 2))
    body_weight_setpoint_lb = Column(Numeric(8, 2))
    waist_setpoint_in = Column(Numeric(8, 2))
    protein_floor_g = Column(Numeric(8, 2), nullable=False, default=170)
    fat_floor_avg_g = Column(Numeric(8, 2), nullable=False, default=55)
    default_kcal = Column(Numeric(8, 2), nullable=False, default=2695)
    base_protein_g = Column(Numeric(8, 2))
    base_carbs_g = Column(Numeric(8, 2))
    base_fat_g = Column(Numeric(8, 2))
    cycle_start_date = Column(Date)
    # Age-mode governs oscillator thresholds across developmental eras:
    # early_adult | mature_adult | preservation
    age_mode = Column(String(20), default="early_adult")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ArcForgeUser(Base):
    """
    One row per registered ArcForge user.
    expo_user_id is the UUID-v4 generated on the user's device at first launch.
    This is the single partition key for all physiological data in every table.
    """
    __tablename__ = "arcforge_users"

    expo_user_id  = Column(String, primary_key=True)
    username      = Column(String(80), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    age_mode      = Column(String(20), nullable=False, default="early_adult")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VitalsDailyLog(Base):
    __tablename__ = "vitals_daily_log"
    __table_args__ = (
        UniqueConstraint("expo_user_id", "date", name="uq_vitals_daily_log_user_date"),
        CheckConstraint("libido_score IS NULL OR libido_score BETWEEN 1 AND 5", name="chk_vdl_libido"),
        CheckConstraint("morning_erection_score IS NULL OR morning_erection_score BETWEEN 0 AND 3", name="chk_vdl_erection"),
        CheckConstraint("motivation_score IS NULL OR motivation_score BETWEEN 1 AND 5", name="chk_vdl_motivation"),
        CheckConstraint("mood_stability_score IS NULL OR mood_stability_score BETWEEN 1 AND 5", name="chk_vdl_mood"),
        CheckConstraint("soreness_score IS NULL OR soreness_score BETWEEN 1 AND 5", name="chk_vdl_soreness"),
        CheckConstraint("joint_friction_score IS NULL OR joint_friction_score BETWEEN 1 AND 5", name="chk_vdl_joint"),
        CheckConstraint("mental_drive_score IS NULL OR mental_drive_score BETWEEN 1 AND 5", name="chk_vdl_drive"),
        CheckConstraint("stress_load_score IS NULL OR stress_load_score BETWEEN 1 AND 5", name="chk_vdl_stress"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    expo_user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)

    sleep_duration_min = Column(Numeric(8, 2))
    time_in_bed_min = Column(Numeric(8, 2))
    sleep_efficiency_pct = Column(Numeric(5, 2))
    bedtime_local = Column(DateTime(timezone=True))
    waketime_local = Column(DateTime(timezone=True))
    sleep_midpoint_min = Column(Numeric(8, 2))
    # Apple Health raw stage breakdown — brain computes derived fields from these
    sleep_awake_min = Column(Numeric(8, 2))
    sleep_rem_min   = Column(Numeric(8, 2))
    sleep_core_min  = Column(Numeric(8, 2))
    sleep_deep_min  = Column(Numeric(8, 2))
    # HH:MM strings (e.g. "23:20" / "05:05") — brain computes midpoint from these
    sleep_onset_hhmm = Column(String(5))
    sleep_wake_hhmm  = Column(String(5))

    resting_hr_bpm = Column(Numeric(8, 2))
    hrv_ms = Column(Numeric(8, 2))
    walking_hr_avg_bpm = Column(Numeric(8, 2))
    overnight_hr_avg_bpm = Column(Numeric(8, 2))
    vo2_estimate = Column(Numeric(8, 2))

    active_energy_kcal = Column(Numeric(8, 2))
    exercise_min = Column(Numeric(8, 2))
    step_count = Column(Integer)

    cardio_duration_min = Column(Numeric(8, 2))
    cardio_avg_hr_bpm = Column(Numeric(8, 2))
    cardio_zone2_min = Column(Numeric(8, 2))
    cardio_zone3_min = Column(Numeric(8, 2))
    actual_cardio_mode = Column(String(30))
    cardio_strain_score = Column(Numeric(8, 2))

    morning_temp_f = Column(Numeric(5, 2))
    morning_temp_c = Column(Numeric(5, 2))
    body_weight_lb = Column(Numeric(8, 2))
    body_fat_pct = Column(Numeric(8, 2))
    fat_mass_lb = Column(Numeric(8, 2))
    fat_free_mass_lb = Column(Numeric(8, 2))
    skeletal_muscle_pct = Column(Numeric(5, 2))
    skeletal_muscle_lb = Column(Numeric(8, 2))
    tbw_pct = Column(Numeric(8, 2))
    body_comp_confidence = Column(Numeric(4, 3))

    waist_at_navel_in = Column(Numeric(8, 2))
    waist_measure_confidence = Column(Numeric(4, 3))
    waist_notes = Column(Text)

    libido_score = Column(Integer)
    morning_erection_score = Column(Integer)
    motivation_score = Column(Integer)
    mood_stability_score = Column(Integer)
    soreness_score = Column(Integer)
    joint_friction_score = Column(Integer)
    mental_drive_score = Column(Integer)
    stress_load_score = Column(Integer)

    planned_lift_mode = Column(String(30))
    completed_lift_mode = Column(String(30))
    lift_readiness_self_score = Column(Integer)
    top_set_load_index = Column(Numeric(8, 2))
    top_set_rpe = Column(Numeric(8, 2))
    strength_output_index = Column(Numeric(8, 2))
    pump_quality_score = Column(Integer)
    rep_speed_subjective_score = Column(Integer)
    session_density_score = Column(Numeric(8, 2))
    lift_strain_score = Column(Numeric(8, 2))

    kcal_target = Column(Numeric(8, 2))
    kcal_actual = Column(Numeric(8, 2))
    protein_g_target = Column(Numeric(8, 2))
    protein_g_actual = Column(Numeric(8, 2))
    carbs_g_target = Column(Numeric(8, 2))
    carbs_g_actual = Column(Numeric(8, 2))
    fat_g_target = Column(Numeric(8, 2))
    fat_g_actual = Column(Numeric(8, 2))

    acute_score = Column(Numeric(8, 2))
    resource_score = Column(Numeric(8, 2))
    seasonal_score = Column(Numeric(8, 2))
    oscillator_composite_score = Column(Numeric(8, 2))
    oscillator_class = Column(String(30))

    recommended_cardio_mode = Column(String(30))
    recommended_lift_mode = Column(String(30))
    recommended_macro_day = Column(String(30))

    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VitalsCardioSession(Base):
    __tablename__ = "vitals_cardio_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expo_user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_min = Column(Numeric(8, 2))
    avg_hr_bpm = Column(Numeric(8, 2))
    max_hr_bpm = Column(Numeric(8, 2))
    zone2_min = Column(Numeric(8, 2))
    zone3_min = Column(Numeric(8, 2))
    mode = Column(String(30), nullable=False)
    strain_score = Column(Numeric(8, 2))
    source = Column(String(20), nullable=False, default="manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VitalsLiftSession(Base):
    __tablename__ = "vitals_lift_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expo_user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    duration_min = Column(Numeric(8, 2))
    planned_lift_mode = Column(String(30))
    completed_lift_mode = Column(String(30))
    lift_readiness_self_score = Column(Integer)
    top_set_load_index = Column(Numeric(8, 2))
    top_set_rpe = Column(Numeric(8, 2))
    strength_output_index = Column(Numeric(8, 2))
    session_density_score = Column(Numeric(8, 2))
    pump_quality_score = Column(Integer)
    rep_speed_subjective_score = Column(Integer)
    lift_strain_score = Column(Numeric(8, 2))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VitalsNutritionDayTarget(Base):
    __tablename__ = "vitals_nutrition_day_target"
    __table_args__ = (
        UniqueConstraint("expo_user_id", "date", name="uq_vitals_nutrition_user_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    expo_user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    macro_day_type = Column(String(20), nullable=False)
    kcal_target = Column(Numeric(8, 2), nullable=False)
    protein_g_target = Column(Numeric(8, 2), nullable=False)
    carbs_g_target = Column(Numeric(8, 2), nullable=False)
    fat_g_target = Column(Numeric(8, 2), nullable=False)

    pre_cardio_carbs_g = Column(Numeric(8, 2))
    post_cardio_protein_g = Column(Numeric(8, 2))
    post_cardio_carbs_g = Column(Numeric(8, 2))
    post_cardio_fat_g = Column(Numeric(8, 2))
    meal2_protein_g = Column(Numeric(8, 2))
    meal2_carbs_g = Column(Numeric(8, 2))
    meal2_fat_g = Column(Numeric(8, 2))
    pre_lift_protein_g = Column(Numeric(8, 2))
    pre_lift_carbs_g = Column(Numeric(8, 2))
    pre_lift_fat_g = Column(Numeric(8, 2))
    post_lift_protein_g = Column(Numeric(8, 2))
    post_lift_carbs_g = Column(Numeric(8, 2))
    post_lift_fat_g = Column(Numeric(8, 2))
    final_meal_protein_g = Column(Numeric(8, 2))
    final_meal_carbs_g = Column(Numeric(8, 2))
    final_meal_fat_g = Column(Numeric(8, 2))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VitalsOscillatorState(Base):
    __tablename__ = "vitals_oscillator_state"
    __table_args__ = (
        UniqueConstraint("expo_user_id", "date", name="uq_vitals_oscillator_user_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    expo_user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    cycle_day_28 = Column(Integer)        # reporting only — not phase authority
    cycle_week_type = Column(String(20))  # legacy reporting field

    # Adaptive Infradian Arc — state-driven phase (replaces calendar week mandate)
    arc_phase = Column(String(20))        # accumulation | expansion | deload | resensitize
    arc_day = Column(Integer, default=1)  # day within current phase
    arc_start_date = Column(Date)         # date current phase began
    arc_transition_reason = Column(String(80))  # why phase changed (diagnostic)

    acute_score = Column(Numeric(8, 2))
    resource_score = Column(Numeric(8, 2))
    adaptation_score = Column(Numeric(8, 2))   # renamed from seasonal_score
    seasonal_score = Column(Numeric(8, 2))     # kept for backward compat — mirrors adaptation_score
    oscillator_composite_score = Column(Numeric(8, 2))
    oscillator_class = Column(String(30))

    rolling_zone2_count_7d = Column(Integer, default=0)
    rolling_zone3_count_7d = Column(Integer, default=0)
    rolling_recovery_count_7d = Column(Integer, default=0)
    rolling_neural_lift_count_7d = Column(Integer, default=0)
    rolling_reset_day_count_28d = Column(Integer, default=0)

    fatigue_flag = Column(Boolean, default=False)
    monotony_flag = Column(Boolean, default=False)
    deload_compliance_flag = Column(Boolean, default=False)
    resensitize_phase_flag = Column(Boolean, default=False)

    acute_breakdown = Column(JSONB)
    resource_breakdown = Column(JSONB)
    seasonal_breakdown = Column(JSONB)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ExerciseMaster(Base):
    """Biomechanical exercise catalog — 122 exercises with movement pattern classification."""
    __tablename__ = "exercise_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True)
    movement_pattern = Column(
        Enum(MovementPattern, name="movement_pattern_enum"),
        nullable=False
    )
    primary_muscles = Column(JSONB, nullable=False, default=list)
    secondary_muscles = Column(JSONB, nullable=False, default=list)
    equipment_required = Column(String(60))
    bilateral = Column(Boolean, default=True)
    compound = Column(Boolean, default=True)
    neural_demand = Column(Numeric(4, 2), default=0.5)   # 0.0–1.0
    hypertrophy_stimulus = Column(Numeric(4, 2), default=0.5)  # 0.0–1.0
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiftExerciseEntry(Base):
    """Individual exercise sets within a lift session — ties to ExerciseMaster."""
    __tablename__ = "lift_exercise_entry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    expo_user_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    lift_session_id = Column(Integer, ForeignKey("vitals_lift_session.id",
                                                  ondelete="CASCADE"), nullable=True)
    exercise_id = Column(Integer, ForeignKey("exercise_master.id"), nullable=True)
    exercise_name_raw = Column(String(120))   # freeform fallback before mapping

    sets_completed = Column(Integer)
    reps_per_set = Column(Integer)
    load_kg = Column(Numeric(8, 2))
    load_lbs = Column(Numeric(8, 2))
    rpe = Column(Numeric(4, 2))
    rir = Column(Integer)                     # Reps In Reserve
    tempo_string = Column(String(20))         # e.g. "4-1-2-0"
    set_type = Column(String(30))             # "working", "warmup", "drop", "myo"

    # Per-set computed outputs
    top_set_e1rm_lbs = Column(Numeric(8, 2))  # Epley estimated 1RM
    volume_load_lbs = Column(Numeric(10, 2))  # sets * reps * load
    set_strength_output_index = Column(Numeric(8, 2))

    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
