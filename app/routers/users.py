from datetime import date as DateType, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.vitals_models import ArcForgeUser, VitalsUserBaselines

router = APIRouter(prefix="/users", tags=["users"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _compute_age_mode(dob: DateType) -> str:
    today = DateType.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 35:
        return "early_adult"
    elif age < 50:
        return "mature_adult"
    else:
        return "preservation"


class UserRegisterIn(BaseModel):
    expo_user_id: str = Field(..., min_length=36, max_length=36,
                              description="UUID-v4 generated on device at first launch")
    username: str = Field(..., min_length=1, max_length=80)
    date_of_birth: DateType = Field(..., description="YYYY-MM-DD")


class UserUpdateIn(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=80)
    date_of_birth: Optional[DateType] = None


@router.post("/register")
def register_user(payload: UserRegisterIn, db: Session = Depends(get_db)):
    """
    Called once at first launch of ArcForge. Idempotent — calling again with
    the same expo_user_id updates username/DOB but never reassigns the UUID.
    """
    age_mode = _compute_age_mode(payload.date_of_birth)

    existing = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == payload.expo_user_id
    ).first()

    if existing:
        existing.username      = payload.username
        existing.date_of_birth = payload.date_of_birth
        existing.age_mode      = age_mode
        db.commit()
        db.refresh(existing)
    else:
        user = ArcForgeUser(
            expo_user_id  = payload.expo_user_id,
            username      = payload.username,
            date_of_birth = payload.date_of_birth,
            age_mode      = age_mode,
        )
        db.add(user)

        baselines = db.query(VitalsUserBaselines).filter(
            VitalsUserBaselines.expo_user_id == payload.expo_user_id
        ).first()
        if not baselines:
            db.add(VitalsUserBaselines(
                expo_user_id  = payload.expo_user_id,
                age_mode      = age_mode,
                protein_floor_g  = 170,
                fat_floor_avg_g  = 55,
                default_kcal     = 2695,
            ))

        db.commit()
        db.refresh(user)

    return {
        "ok":           True,
        "expo_user_id": payload.expo_user_id,
        "username":     payload.username,
        "age_mode":     age_mode,
        "age_mode_description": {
            "early_adult":  "Ages 18–34 — standard thresholds",
            "mature_adult": "Ages 35–49 — adjusted HRV/virility baselines",
            "preservation": "Ages 50+ — conservative arc transitions",
        }[age_mode],
    }


@router.get("/{expo_user_id}")
def get_user(expo_user_id: str, db: Session = Depends(get_db)):
    user = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == expo_user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {expo_user_id} not found")
    return {
        "expo_user_id":  user.expo_user_id,
        "username":      user.username,
        "date_of_birth": str(user.date_of_birth),
        "age_mode":      user.age_mode,
        "created_at":    str(user.created_at),
    }


@router.patch("/{expo_user_id}")
def update_user(expo_user_id: str, payload: UserUpdateIn, db: Session = Depends(get_db)):
    user = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == expo_user_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {expo_user_id} not found")

    if payload.username:
        user.username = payload.username
    if payload.date_of_birth:
        user.date_of_birth = payload.date_of_birth
        user.age_mode = _compute_age_mode(payload.date_of_birth)

        baselines = db.query(VitalsUserBaselines).filter(
            VitalsUserBaselines.expo_user_id == expo_user_id
        ).first()
        if baselines:
            baselines.age_mode = user.age_mode

    db.commit()
    return {
        "ok":           True,
        "expo_user_id": expo_user_id,
        "username":     user.username,
        "age_mode":     user.age_mode,
    }
