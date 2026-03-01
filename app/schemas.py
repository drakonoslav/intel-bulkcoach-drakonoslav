from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import date as DateType


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    movement_pattern: str
    equipment: Optional[str]
    bilateral: int


class MuscleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    group_name: str
    region: str


class ActivationEntry(BaseModel):
    exercise: str
    muscle: str
    activation: float
    role: Optional[str] = None
    weight: Optional[float] = None
    weighted_activation: Optional[float] = None


class PhaseEntry(BaseModel):
    exercise: str
    muscle: str
    phase: str
    activation: float


class BottleneckEntry(BaseModel):
    exercise: str
    muscle: str
    bottleneck_coefficient: float
    is_limiting: bool


class StabilizationEntry(BaseModel):
    exercise: str
    muscle: str
    stabilization_score: float
    dynamic_score: float


class CompositeEntry(BaseModel):
    exercise: str
    muscle: str
    composite_score: float
    activation_component: float
    phase_component: float
    bottleneck_component: float
    stabilization_component: float


class DatasetInfo(BaseModel):
    version: str
    name: str
    description: str
    dimensions: Dict[str, int]


class MatrixResponse(BaseModel):
    version: str
    dimensions: Dict[str, int]
    data: List[Dict[str, Any]]


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
