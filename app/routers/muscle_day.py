from collections import defaultdict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LiftSet, Exercise, Muscle, ActivationMatrixV2, RoleWeightedMatrixV2

router = APIRouter(prefix="/muscle", tags=["muscle"])

HANDS_GRIP_NAME = "Hands/Grip"
FOREARMS_NAME = "Forearms"
HANDS_GRIP_SCALE = 0.85
MUSCLE_SCHEMA_VERSION = 27
ROLLING_WINDOW_DAYS = 7


def _compute_day_doses(sets, muscle_ids, act_lookup, rw_lookup, forearm_id, hands_grip_id):
    total_dose = defaultdict(float)
    direct_dose = defaultdict(float)

    for s in sets:
        for mid in muscle_ids:
            av = act_lookup.get((s.exercise_id, mid), 0)
            rw = rw_lookup.get((s.exercise_id, mid), 0.0)
            total_dose[mid] += s.tonnage * (av / 5.0)
            direct_dose[mid] += s.tonnage * rw

    if hands_grip_id and forearm_id:
        if total_dose[hands_grip_id] == 0:
            total_dose[hands_grip_id] = total_dose[forearm_id] * HANDS_GRIP_SCALE
            direct_dose[hands_grip_id] = direct_dose[forearm_id] * HANDS_GRIP_SCALE

    return total_dose, direct_dose


@router.get("/day", summary="Per-muscle load for a single date (all 27 regions) + 7-day rolling")
def muscle_day(
    date_param: date = Query(..., alias="date", examples=["2026-03-01"]),
    db: Session = Depends(get_db),
):
    muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_map = {m.id: m.name for m in muscles}
    muscle_ids = [m.id for m in muscles]

    forearm_id = None
    hands_grip_id = None
    for m in muscles:
        if m.name == FOREARMS_NAME:
            forearm_id = m.id
        elif m.name == HANDS_GRIP_NAME:
            hands_grip_id = m.id

    window_from = date_param - timedelta(days=ROLLING_WINDOW_DAYS - 1)
    window_to = date_param

    window_sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= window_from,
        LiftSet.performed_at <= window_to,
    ).all()

    today_sets = [s for s in window_sets if s.performed_at == date_param]

    all_ex_ids = list({s.exercise_id for s in window_sets})

    act_lookup = {}
    rw_lookup = {}
    if all_ex_ids:
        for r in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id.in_(all_ex_ids)).all():
            act_lookup[(r.exercise_id, r.muscle_id)] = r.activation_value
        for r in db.query(RoleWeightedMatrixV2).filter(RoleWeightedMatrixV2.exercise_id.in_(all_ex_ids)).all():
            rw_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight

    today_total, today_direct = _compute_day_doses(
        today_sets, muscle_ids, act_lookup, rw_lookup, forearm_id, hands_grip_id
    )

    load_7d_total = defaultdict(float)
    load_7d_direct = defaultdict(float)

    sets_by_day = defaultdict(list)
    for s in window_sets:
        sets_by_day[s.performed_at].append(s)

    for day in range(ROLLING_WINDOW_DAYS):
        d = window_from + timedelta(days=day)
        day_sets = sets_by_day.get(d, [])
        day_total, day_direct = _compute_day_doses(
            day_sets, muscle_ids, act_lookup, rw_lookup, forearm_id, hands_grip_id
        )
        for mid in muscle_ids:
            load_7d_total[mid] += day_total[mid]
            load_7d_direct[mid] += day_direct[mid]

    today_ex_ids = list({s.exercise_id for s in today_sets})
    ex_name_map = {e.id: e.name for e in db.query(Exercise).filter(Exercise.id.in_(today_ex_ids)).all()} if today_ex_ids else {}

    total_tonnage = sum(s.tonnage for s in today_sets)

    regions = []
    for mid in muscle_ids:
        derived = (mid == hands_grip_id and forearm_id is not None
                   and not any((eid, mid) in act_lookup for eid in today_ex_ids))
        entry = {
            "muscle": muscle_map[mid],
            "muscle_id": mid,
            "total_dose": round(today_total[mid], 2),
            "direct_dose": round(today_direct[mid], 2),
            "load_7d_total": round(load_7d_total[mid], 2),
            "load_7d_direct": round(load_7d_direct[mid], 2),
        }
        if mid == hands_grip_id:
            entry["derived_from"] = "forearms" if derived else None
            entry["scale"] = HANDS_GRIP_SCALE if derived else None
        regions.append(entry)

    exercises_used = []
    for s in today_sets:
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
        "muscle_schema_version": MUSCLE_SCHEMA_VERSION,
        "window_from": str(window_from),
        "window_to": str(window_to),
        "total_sets": len(today_sets),
        "total_tonnage": round(total_tonnage, 2),
        "exercises": exercises_used,
        "regions": regions,
    }
