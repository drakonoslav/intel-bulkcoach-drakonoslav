from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CompositeMuscleIndex, Muscle

router = APIRouter(prefix="/composite", tags=["composite"])


@router.get("/muscles", summary="Composite muscle profile index (26 muscles)")
def get_composite_muscles(db: Session = Depends(get_db)):
    rows = (
        db.query(CompositeMuscleIndex, Muscle.name)
        .join(Muscle, Muscle.id == CompositeMuscleIndex.muscle_id)
        .order_by(CompositeMuscleIndex.composite_score.desc())
        .all()
    )
    return [
        {
            "muscle": name,
            "composite_score": row.composite_score,
            "payload": row.payload,
        }
        for row, name in rows
    ]
