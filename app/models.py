from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    category = Column(String(60), nullable=False, index=True)
    movement_pattern = Column(String(60), nullable=False)
    equipment = Column(String(60), nullable=True)
    bilateral = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Muscle(Base):
    __tablename__ = "muscles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False, index=True)
    group_name = Column(String(60), nullable=False, index=True)
    region = Column(String(40), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ActivationMatrixV2(Base):
    __tablename__ = "activation_matrix_v2"
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_id", name="uq_actv2_ex_mu"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    activation = Column(Float, nullable=False)
    version = Column(String(10), nullable=False, default="v2")

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class RoleWeightedMatrixV2(Base):
    __tablename__ = "role_weighted_matrix_v2"
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_id", name="uq_rwv2_ex_mu"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    weight = Column(Float, nullable=False)
    weighted_activation = Column(Float, nullable=False)
    version = Column(String(10), nullable=False, default="v2")

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class PhaseMatrixV3(Base):
    __tablename__ = "phase_matrix_v3"
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_id", "phase", name="uq_pv3_ex_mu_ph"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    phase = Column(String(20), nullable=False)
    activation = Column(Float, nullable=False)
    version = Column(String(10), nullable=False, default="v3")

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class BottleneckMatrixV4(Base):
    __tablename__ = "bottleneck_matrix_v4"
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_id", name="uq_bv4_ex_mu"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    bottleneck_coefficient = Column(Float, nullable=False)
    is_limiting = Column(Integer, nullable=False, default=0)
    version = Column(String(10), nullable=False, default="v4")

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class StabilizationMatrixV5(Base):
    __tablename__ = "stabilization_matrix_v5"
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_id", name="uq_sv5_ex_mu"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    stabilization_score = Column(Float, nullable=False)
    dynamic_score = Column(Float, nullable=False)
    version = Column(String(10), nullable=False, default="v5")

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class CompositeIndex(Base):
    __tablename__ = "composite_index"
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_id", name="uq_ci_ex_mu"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    composite_score = Column(Float, nullable=False)
    activation_component = Column(Float, nullable=False)
    phase_component = Column(Float, nullable=False)
    bottleneck_component = Column(Float, nullable=False)
    stabilization_component = Column(Float, nullable=False)
    version = Column(String(10), nullable=False, default="composite")

    exercise = relationship("Exercise")
    muscle = relationship("Muscle")


class VolumeLog(Base):
    __tablename__ = "volume_logs"

    id = Column(Integer, primary_key=True, index=True)
    exercise = Column(String(120), nullable=False, index=True)
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
