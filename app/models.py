from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, CheckConstraint
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
