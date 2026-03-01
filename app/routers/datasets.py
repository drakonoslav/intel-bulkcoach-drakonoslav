from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import (
    Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
    PhaseMatrixV3, BottleneckMatrixV4,
    StabilizationMatrixV5, CompositeIndex,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])

DATASET_META = {
    "v2": {
        "name": "Base Activation Matrix",
        "description": "92×26 muscle activation matrix mapping exercises to muscles with activation levels (0–1).",
        "tables": ["activation_matrix_v2", "role_weighted_matrix_v2"],
    },
    "v3": {
        "name": "Phase-Expanded Matrices",
        "description": "Phase-decomposed activation: initiation, mid-range, and lockout phases per exercise×muscle pair.",
        "tables": ["phase_matrix_v3"],
    },
    "v4": {
        "name": "Bottleneck Coefficient Matrix",
        "description": "Bottleneck coefficients identifying limiting muscles per exercise. Flags muscles that constrain performance.",
        "tables": ["bottleneck_matrix_v4"],
    },
    "v5": {
        "name": "Stabilization & Dynamic Matrices",
        "description": "Decomposed stabilization vs dynamic contribution scores per exercise×muscle pair.",
        "tables": ["stabilization_matrix_v5"],
    },
    "composite": {
        "name": "Composite Muscle Profile Index",
        "description": "Weighted composite score integrating activation, phase, bottleneck, and stabilization components.",
        "tables": ["composite_index"],
    },
}

TABLE_MODEL_MAP = {
    "activation_matrix_v2": ActivationMatrixV2,
    "role_weighted_matrix_v2": RoleWeightedMatrixV2,
    "phase_matrix_v3": PhaseMatrixV3,
    "bottleneck_matrix_v4": BottleneckMatrixV4,
    "stabilization_matrix_v5": StabilizationMatrixV5,
    "composite_index": CompositeIndex,
}


@router.get("", summary="List available dataset versions and their dimensions")
def list_datasets(db: Session = Depends(get_db)):
    n_exercises = db.query(func.count(Exercise.id)).scalar()
    n_muscles = db.query(func.count(Muscle.id)).scalar()
    versions = []
    for ver, meta in DATASET_META.items():
        row_counts = {}
        for tbl in meta["tables"]:
            model = TABLE_MODEL_MAP[tbl]
            row_counts[tbl] = db.query(func.count(model.id)).scalar()
        versions.append({
            "version": ver,
            "name": meta["name"],
            "description": meta["description"],
            "tables": meta["tables"],
            "row_counts": row_counts,
            "dimensions": {"exercises": n_exercises, "muscles": n_muscles},
        })
    return {"versions": versions}
