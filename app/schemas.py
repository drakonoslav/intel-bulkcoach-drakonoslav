from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import date as DateType


class VolumeIngest(BaseModel):
    exercise: str = Field(..., description="Exercise name, e.g. 'squat'")
    weight_kg: float = Field(..., gt=0, description="Load in kilograms")
    reps: int = Field(..., gt=0, le=100)
    sets: int = Field(1, gt=0, le=20)
    date: DateType = Field(..., description="Training date YYYY-MM-DD")
    notes: Optional[str] = None


class VolumeLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise: str
    weight_kg: float
    reps: int
    sets: int
    date: DateType
    week: str
    tonnage: float
    estimated_1rm: float
    notes: Optional[str]


class WeeklyReport(BaseModel):
    week: str
    preset: str
    exercises: List[str]
    total_sets: int
    total_reps: int
    total_tonnage_kg: float
    avg_intensity_pct: Optional[float]
    breakdown: List[Dict[str, Any]]
    recommendations: List[str]


class OptimizerResult(BaseModel):
    goal: str
    n_slots: int
    selected_exercises: List[Dict[str, Any]]
    weekly_volume: Dict[str, Any]
    notes: List[str]
