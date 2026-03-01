from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Preset

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("", summary="List all presets with weights")
def list_presets(db: Session = Depends(get_db)):
    rows = db.query(Preset).order_by(Preset.name).all()
    return [{"name": r.name, "weights": r.weights} for r in rows]
