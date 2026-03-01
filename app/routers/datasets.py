from fastapi import APIRouter
from app.data import v2, v3, v4, v5, composite

router = APIRouter(prefix="/datasets", tags=["datasets"])

VERSIONS = {
    "v2": v2,
    "v3": v3,
    "v4": v4,
    "v5": v5,
    "composite": composite,
}


@router.get("", summary="List all available dataset versions")
def list_datasets():
    return {
        "versions": [
            {
                "version": mod.DATASET_VERSION,
                "name": mod.DATASET_NAME,
                "description": mod.DATASET_DESCRIPTION,
                "exercises": list(mod.EXERCISE_DEFAULTS.keys()),
            }
            for mod in VERSIONS.values()
        ]
    }
