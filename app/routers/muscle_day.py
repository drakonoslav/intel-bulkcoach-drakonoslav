from collections import defaultdict
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LiftSet, Exercise, Muscle, ActivationMatrixV2, RoleWeightedMatrixV2

router = APIRouter(prefix="/muscle", tags=["muscle"])


@router.get("/day", summary="Per-muscle load for a single date (all 26 regions)")
def muscle_day(
    date_param: date = Query(..., alias="date", examples=["2026-03-01"]),
    db: Session = Depends(get_db),
):
    muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_map = {m.id: m.name for m in muscles}
    muscle_ids = [m.id for m in muscles]

    sets = db.query(LiftSet).filter(LiftSet.performed_at == date_param).all()

    ex_ids = list({s.exercise_id for s in sets})

    act_rows = db.query(ActivationMatrixV2).filter(
        ActivationMatrixV2.exercise_id.in_(ex_ids)
    ).all() if ex_ids else []
    act_lookup = {}
    for r in act_rows:
        act_lookup[(r.exercise_id, r.muscle_id)] = r.activation_value

    rw_rows = db.query(RoleWeightedMatrixV2).filter(
        RoleWeightedMatrixV2.exercise_id.in_(ex_ids)
    ).all() if ex_ids else []
    rw_lookup = {}
    for r in rw_rows:
        rw_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight

    total_dose = defaultdict(float)
    direct_dose = defaultdict(float)

    for s in sets:
        for mid in muscle_ids:
            av = act_lookup.get((s.exercise_id, mid), 0)
            rw = rw_lookup.get((s.exercise_id, mid), 0.0)
            total_dose[mid] += s.tonnage * (av / 5.0)
            direct_dose[mid] += s.tonnage * rw

    ex_name_map = {e.id: e.name for e in db.query(Exercise).filter(Exercise.id.in_(ex_ids)).all()} if ex_ids else {}

    total_tonnage = sum(s.tonnage for s in sets)

    regions = []
    for mid in muscle_ids:
        regions.append({
            "muscle": muscle_map[mid],
            "muscle_id": mid,
            "total_dose": round(total_dose[mid], 2),
            "direct_dose": round(direct_dose[mid], 2),
        })

    exercises_used = []
    for s in sets:
        exercises_used.append({
            "set_id": s.id,
            "exercise": ex_name_map.get(s.exercise_id, f"id:{s.exercise_id}"),
            "weight": s.weight,
            "reps": s.reps,
            "tonnage": s.tonnage,
        })

    return {
        "date": str(date_param),
        "source": "intel",
        "total_sets": len(sets),
        "total_tonnage": round(total_tonnage, 2),
        "exercises": exercises_used,
        "regions": regions,
    }
