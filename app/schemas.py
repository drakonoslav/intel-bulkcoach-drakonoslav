from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import date as DateType


class MatrixV2Response(BaseModel):
    exercises: List[str]
    muscles: List[str]
    matrix: List[List[int]]


class DatasetInfo(BaseModel):
    version: str
    name: str
    description: str
    exercises: int
    muscles: int
    rows: int


class VolumeIngest(BaseModel):
    exercise: str = Field(..., description="Exercise name")
    weight_kg: float = Field(..., gt=0)
    reps: int = Field(..., gt=0, le=100)
    sets: int = Field(1, gt=0, le=50)
    date: DateType = Field(...)
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
    exercises: List[str]
    total_sets: int
    total_reps: int
    total_tonnage_kg: float
    muscle_stimulus: Dict[str, float]
    breakdown: List[Dict[str, Any]]


class OptimizerResult(BaseModel):
    goal: str
    n_slots: int
    selected: List[Dict[str, Any]]
    coverage: Dict[str, float]
    notes: List[str]
