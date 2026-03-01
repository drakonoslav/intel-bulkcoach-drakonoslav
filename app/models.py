from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, CheckConstraint
)
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
