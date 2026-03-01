from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Exercise, Muscle, ActivationMatrixV2

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", summary="List available dataset versions")
def list_datasets(db: Session = Depends(get_db)):
    n_exercises = db.query(func.count(Exercise.id)).scalar()
    n_muscles = db.query(func.count(Muscle.id)).scalar()
    n_activation = db.query(func.count()).select_from(ActivationMatrixV2).scalar()
    return {
        "versions": [
            {
                "version": "v2",
                "name": "Base Activation Matrix",
                "description": f"Exercise-muscle activation matrix ({n_exercises}x{n_muscles}), integer scale 0-5.",
                "exercises": n_exercises,
                "muscles": n_muscles,
                "activation_rows": n_activation,
            }
        ]
    }
