from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class VolumeLog(Base):
    __tablename__ = "volume_logs"

    id = Column(Integer, primary_key=True, index=True)
    exercise = Column(String(100), nullable=False, index=True)
    weight_kg = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    sets = Column(Integer, nullable=False, default=1)
    date = Column(Date, nullable=False, index=True)
    week = Column(String(8), nullable=False, index=True)  # YYYY-WW
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
