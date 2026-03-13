from datetime import date as DateType, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.vitals_models import ArcForgeUser, VitalsUserBaselines

router = APIRouter(prefix="/users", tags=["users"])

_DEFAULT_DOB = DateType(1990, 1, 1)


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


def _default_baselines(expo_user_id: str, age_mode: str) -> VitalsUserBaselines:
    return VitalsUserBaselines(
        expo_user_id    = expo_user_id,
        age_mode        = age_mode,
        protein_floor_g = 170,
        fat_floor_avg_g = 55,
        default_kcal    = 2695,
    )


def _user_response(user: ArcForgeUser) -> dict:
    return {
        "ok":           True,
        "expo_user_id": user.expo_user_id,
        "username":     user.username,
        "date_of_birth": str(user.date_of_birth),
        "age_mode":     user.age_mode,
        "age_mode_description": {
            "early_adult":  "Ages 18–34 — standard thresholds",
            "mature_adult": "Ages 35–49 — adjusted HRV/virility baselines",
            "preservation": "Ages 50+ — conservative arc transitions",
        }.get(user.age_mode, ""),
        "created_at": str(user.created_at),
    }


def ensure_user(db: Session, expo_user_id: str, username: str = "Athlete", dob: DateType = None) -> ArcForgeUser:
    """Get or create a user record. Always succeeds — never raises. Used internally by daily-log."""
    user = db.query(ArcForgeUser).filter(ArcForgeUser.expo_user_id == expo_user_id).first()
    if not user:
        dob = dob or _DEFAULT_DOB
        age_mode = _compute_age_mode(dob)
        user = ArcForgeUser(
            expo_user_id  = expo_user_id,
            username      = username,
            date_of_birth = dob,
            age_mode      = age_mode,
        )
        db.add(user)
        baselines = db.query(VitalsUserBaselines).filter(
            VitalsUserBaselines.expo_user_id == expo_user_id
        ).first()
        if not baselines:
            db.add(_default_baselines(expo_user_id, age_mode))
        db.commit()
        db.refresh(user)
    return user


class UserRegisterIn(BaseModel):
    expo_user_id:   str            = Field(..., min_length=6, max_length=80,
                                           description="UUID-v4 generated on device at first launch")
    username:       str            = Field("Athlete", min_length=1, max_length=80)
    date_of_birth:  Optional[DateType] = Field(None, description="YYYY-MM-DD — optional, defaults to 1990-01-01")


class UserEnsureIn(BaseModel):
    expo_user_id: str           = Field(..., min_length=6, max_length=80,
                                        description="UUID-v4 from device")
    username:     Optional[str] = Field(None, min_length=1, max_length=80,
                                        description="Display name — only updates if provided")


class UserUpdateIn(BaseModel):
    username:      Optional[str]       = Field(None, min_length=1, max_length=80)
    date_of_birth: Optional[DateType]  = None


@router.post("/register")
def register_user(payload: UserRegisterIn, db: Session = Depends(get_db)):
    """
    Called once at first launch of ArcForge. Idempotent — safe to call repeatedly.
    DOB is optional (defaults to 1990-01-01 so Expo doesn't need a DOB screen to register).
    """
    dob      = payload.date_of_birth or _DEFAULT_DOB
    age_mode = _compute_age_mode(dob)

    existing = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == payload.expo_user_id
    ).first()

    if existing:
        existing.username      = payload.username
        existing.date_of_birth = dob
        existing.age_mode      = age_mode
        db.commit()
        db.refresh(existing)
        return _user_response(existing)

    user = ArcForgeUser(
        expo_user_id  = payload.expo_user_id,
        username      = payload.username,
        date_of_birth = dob,
        age_mode      = age_mode,
    )
    db.add(user)

    baselines = db.query(VitalsUserBaselines).filter(
        VitalsUserBaselines.expo_user_id == payload.expo_user_id
    ).first()
    if not baselines:
        db.add(_default_baselines(payload.expo_user_id, age_mode))

    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.post("/ensure")
def ensure_user_endpoint(payload: UserEnsureIn, db: Session = Depends(get_db)):
    """
    Lightweight upsert — call this on every app launch instead of /register.
    No DOB needed. Creates the user if they don't exist, returns current record if they do.
    Only updates username if provided AND the current username is still the default 'Athlete'.

    Expo should call this at startup with just expo_user_id.
    When the user sets their name in Profile, call it again with username.
    """
    user = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == payload.expo_user_id
    ).first()

    if not user:
        age_mode = _compute_age_mode(_DEFAULT_DOB)
        user = ArcForgeUser(
            expo_user_id  = payload.expo_user_id,
            username      = payload.username or "Athlete",
            date_of_birth = _DEFAULT_DOB,
            age_mode      = age_mode,
        )
        db.add(user)
        baselines = db.query(VitalsUserBaselines).filter(
            VitalsUserBaselines.expo_user_id == payload.expo_user_id
        ).first()
        if not baselines:
            db.add(_default_baselines(payload.expo_user_id, age_mode))
        db.commit()
        db.refresh(user)
    elif payload.username and payload.username != "Athlete":
        user.username = payload.username
        db.commit()
        db.refresh(user)

    return _user_response(user)


@router.get("/{expo_user_id}")
def get_user(expo_user_id: str, db: Session = Depends(get_db)):
    """
    Returns the user profile. If the user isn't registered yet, returns a default
    record (instead of 404) so the Expo app never crashes on first launch.
    """
    user = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == expo_user_id
    ).first()
    if not user:
        return {
            "ok":           False,
            "expo_user_id": expo_user_id,
            "username":     "Athlete",
            "date_of_birth": None,
            "age_mode":     "early_adult",
            "registered":   False,
            "message":      "User not registered. Call POST /users/ensure or POST /users/register.",
        }
    return {**_user_response(user), "registered": True}


@router.patch("/{expo_user_id}")
def update_user(expo_user_id: str, payload: UserUpdateIn, db: Session = Depends(get_db)):
    """
    Update username or DOB. Auto-creates the user if they don't exist yet
    (so Expo can call this without needing to register first).
    """
    user = db.query(ArcForgeUser).filter(
        ArcForgeUser.expo_user_id == expo_user_id
    ).first()

    if not user:
        age_mode = _compute_age_mode(payload.date_of_birth or _DEFAULT_DOB)
        user = ArcForgeUser(
            expo_user_id  = expo_user_id,
            username      = payload.username or "Athlete",
            date_of_birth = payload.date_of_birth or _DEFAULT_DOB,
            age_mode      = age_mode,
        )
        db.add(user)
        baselines = db.query(VitalsUserBaselines).filter(
            VitalsUserBaselines.expo_user_id == expo_user_id
        ).first()
        if not baselines:
            db.add(_default_baselines(expo_user_id, age_mode))
    else:
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
