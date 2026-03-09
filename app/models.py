from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)


class Muscle(Base):
    __tablename__ = "muscles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)


class ActivationMatrixV2(Base):
    __tablename__ = "activation_matrix_v2"
    __table_args__ = (
        CheckConstraint("activation_value BETWEEN 0 AND 5", name="ck_act_range"),
    )

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), primary_key=True)
    activation_value = Column(Integer, nullable=False)

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class RoleWeightedMatrixV2(Base):
    __tablename__ = "role_weighted_matrix_v2"
    __table_args__ = (
        CheckConstraint("role_weight BETWEEN 0 AND 1", name="ck_rw_range"),
    )

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), primary_key=True)
    role_weight = Column(Float, nullable=False)

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class PhaseMatrixV3(Base):
    __tablename__ = "phase_matrix_v3"
    __table_args__ = (
        CheckConstraint("phase IN ('initiation','midrange','lockout')", name="ck_phase_val"),
        CheckConstraint("phase_value BETWEEN 0 AND 5", name="ck_pv_range"),
    )

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), primary_key=True)
    phase = Column(Text, primary_key=True)
    phase_value = Column(Float, nullable=False)

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class BottleneckMatrixV4(Base):
    __tablename__ = "bottleneck_matrix_v4"
    __table_args__ = (
        CheckConstraint("bottleneck_coeff BETWEEN 0 AND 1", name="ck_bn_range"),
    )

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), primary_key=True)
    bottleneck_coeff = Column(Float, nullable=False)

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class StabilizationMatrixV5(Base):
    __tablename__ = "stabilization_matrix_v5"
    __table_args__ = (
        CheckConstraint("component IN ('dynamic','stability')", name="ck_comp_val"),
        CheckConstraint("value BETWEEN 0 AND 1", name="ck_stab_range"),
    )

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), primary_key=True)
    component = Column(Text, primary_key=True)
    value = Column(Float, nullable=False)

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class CompositeMuscleIndex(Base):
    __tablename__ = "composite_muscle_index"
    __table_args__ = (
        CheckConstraint("composite_score BETWEEN 0 AND 100", name="ck_cmi_range"),
    )

    muscle_id = Column(Integer, ForeignKey("muscles.id"), primary_key=True)
    composite_score = Column(Float, nullable=False)
    payload = Column(JSONB, nullable=False)

    muscle = relationship("Muscle")


class ExerciseTag(Base):
    __tablename__ = "exercise_tags"
    __table_args__ = (
        CheckConstraint("slot IN ('hinge','squat','push','pull','carry','oly')", name="ck_slot_val"),
    )

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    slot = Column(Text, primary_key=True)

    exercise = relationship("Exercise")


class Preset(Base):
    __tablename__ = "presets"

    name = Column(Text, primary_key=True)
    weights = Column(JSONB, nullable=False)


class LiftSet(Base):
    __tablename__ = "lift_sets"
    __table_args__ = (
        CheckConstraint("weight >= 0", name="ck_lift_weight"),
        CheckConstraint("reps >= 0", name="ck_lift_reps"),
        CheckConstraint("tonnage >= 0", name="ck_lift_tonnage"),
    )

    id = Column(Integer, primary_key=True, index=True)
    performed_at = Column(Date, nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    weight = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    tonnage = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    event_id = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    exercise = relationship("Exercise")


class Equipment(Base):
    __tablename__ = "equipment"

    tag = Column(Text, primary_key=True)


class ExerciseEquipment(Base):
    __tablename__ = "exercise_equipment"

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    equipment_tag = Column(Text, ForeignKey("equipment.tag"), primary_key=True)
    required = Column(Integer, nullable=False, default=1)

    exercise = relationship("Exercise")
    equipment = relationship("Equipment")


class SessionPlan(Base):
    __tablename__ = "session_plans"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    planned_for = Column(Date, nullable=False, index=True)
    mode = Column(Text, nullable=False)
    preset = Column(Text, nullable=False)
    slots = Column(JSONB, nullable=False)
    plan = Column(JSONB, nullable=False)
    no_history = Column("no_history", Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("mode IN ('compound','isolation')", name="ck_sp_mode"),
    )


class SessionPlanSet(Base):
    __tablename__ = "session_plan_sets"

    plan_id = Column(Integer, ForeignKey("session_plans.id"), primary_key=True)
    set_id = Column(Integer, ForeignKey("lift_sets.id"), primary_key=True)

    plan = relationship("SessionPlan")
    lift_set = relationship("LiftSet")


class GameBridgeSet(Base):
    __tablename__ = "game_bridge_sets"
    __table_args__ = (
        CheckConstraint("dose_estimate >= 0", name="ck_gbs_dose"),
        CheckConstraint("rpe BETWEEN 1 AND 10", name="ck_gbs_rpe"),
        CheckConstraint("movement_type IN ('compound','isolation')", name="ck_gbs_mvmt"),
        UniqueConstraint("event_id", "muscle_id", name="uq_gbs_event_muscle"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Text, nullable=True, index=True)
    performed_at = Column(Date, nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False)
    dose_estimate = Column(Float, nullable=False)
    rpe = Column(Integer, nullable=True)
    movement_type = Column(Text, nullable=False)
    session_id = Column(Text, nullable=True, index=True)
    source = Column(Text, nullable=False, server_default="expo_game_bridge")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    muscle = relationship("Muscle")


class ExerciseBiomechanics(Base):
    __tablename__ = "exercise_biomechanics"

    exercise_id = Column(Integer, ForeignKey("exercises.id"), primary_key=True)
    implement_type = Column(Text, nullable=False)
    body_position = Column(Text, nullable=False)
    laterality = Column(Text, nullable=False)
    resistance_origin = Column(Text, nullable=True)
    resistance_direction = Column(Text, nullable=True)
    grip_style = Column(Text, nullable=True)
    bench_angle = Column(Float, nullable=True)
    stretch_bias = Column(Float, nullable=True)
    shortened_bias = Column(Float, nullable=True)
    stability_demand = Column(Float, nullable=True)
    convergence_arc = Column(Integer, nullable=True)
    humeral_plane = Column(Text, nullable=True)
    elbow_path = Column(Text, nullable=True)
    movement_family = Column(Text, nullable=True)
    pattern_class = Column(Text, nullable=True)
    biomechanics_version = Column(Integer, nullable=False, server_default="1")
    metadata_tier = Column(Text, nullable=False, server_default="core")

    exercise = relationship("Exercise")


class VolumeLog(Base):
    __tablename__ = "volume_logs"

    id = Column(Integer, primary_key=True, index=True)
    exercise = Column(String(200), nullable=False, index=True)
    weight_kg = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    sets = Column(Integer, nullable=False, default=1)
    date = Column(Date, nullable=False, index=True)
    week = Column(String(8), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def tonnage(self):
        return self.weight_kg * self.reps * self.sets

    @property
    def estimated_1rm(self):
        if self.reps == 1:
            return self.weight_kg
        return self.weight_kg * (1 + self.reps / 30.0)
