from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.data import v2, v3, v4, v5, composite

router = APIRouter(prefix="/matrix", tags=["matrix"])

VERSIONS = {
    "v2": v2,
    "v3": v3,
    "v4": v4,
    "v5": v5,
    "composite": composite,
}


@router.get("/{version}", summary="Get intensity matrix for a dataset version")
def get_matrix(
    version: str,
    exercise: Optional[str] = Query(None, description="Filter to a specific exercise"),
):
    mod = VERSIONS.get(version)
    if not mod:
        raise HTTPException(
            status_code=404,
            detail=f"Version '{version}' not found. Available: {list(VERSIONS.keys())}",
        )
    return mod.get_matrix(exercise)
