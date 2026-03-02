import math
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
BALANCE_SCHEMA_VERSION = 3
RECOVERY_SCHEMA_VERSION = 1
ROLLING_WINDOW_DAYS = 7
DECAY_LOOKBACK_DAYS = 30
EPS = 1e-6

DEFAULT_TAU = 3.5
TAU_TABLE = {
    "Quads": 4.0,
    "Hamstrings": 4.0,
    "Glutes": 4.0,
    "Lower Back": 4.0,
    "Pectorals": 3.5,
    "Lats": 3.5,
    "Upper Back": 3.0,
    "Middle Back": 3.0,
    "Deltoids": 3.0,
    "Front/Anterior Delt": 3.0,
    "Rear/Posterior Delt": 3.0,
    "Side/Lateral Delt": 3.0,
    "Traps": 3.0,
    "Upper Traps": 3.0,
    "Mid Traps": 3.0,
    "Lower Traps": 3.0,
    "Triceps": 2.5,
    "Biceps": 2.5,
    "Forearms": 2.5,
    "Hands/Grip": 2.5,
    "Abs": 2.5,
    "Obliques": 2.5,
    "Adductors": 3.5,
    "Abductors": 3.5,
    "Calves": 2.5,
    "Shins": 2.5,
    "Neck": 2.5,
}

FRESHNESS_K = 1000.0

PUSH_MEMBERS = [
    "Pectorals", "Front/Anterior Delt", "Side/Lateral Delt", "Triceps",
    "Quads", "Calves", "Shins",
]
PULL_MEMBERS = [
    "Lats", "Upper Back", "Middle Back", "Rear/Posterior Delt", "Biceps",
    "Forearms", "Hands/Grip", "Traps", "Upper Traps", "Mid Traps", "Lower Traps",
    "Hamstrings", "Lower Back", "Glutes",
]
ANTERIOR_MEMBERS = ["Pectorals", "Quads", "Front/Anterior Delt", "Abs"]
POSTERIOR_MEMBERS = [
    "Hamstrings", "Glutes", "Lower Back", "Middle Back", "Upper Back",
    "Rear/Posterior Delt", "Lats",
]
UPPER_MEMBERS = [
    "Pectorals", "Lats", "Upper Back", "Middle Back",
    "Deltoids", "Front/Anterior Delt", "Rear/Posterior Delt", "Side/Lateral Delt",
    "Traps", "Upper Traps", "Mid Traps", "Lower Traps",
    "Triceps", "Biceps", "Forearms", "Hands/Grip", "Neck",
]
LOWER_MEMBERS = [
    "Glutes", "Quads", "Hamstrings", "Calves", "Shins",
    "Adductors", "Abductors",
]
AXIAL_MEMBERS = [
    "Neck", "Abs", "Obliques", "Lower Back",
    "Upper Back", "Middle Back", "Lats",
    "Traps", "Upper Traps", "Mid Traps", "Lower Traps",
    "Pectorals",
]
APPENDICULAR_MEMBERS = [
    "Deltoids", "Front/Anterior Delt", "Rear/Posterior Delt", "Side/Lateral Delt",
    "Triceps", "Biceps", "Forearms", "Hands/Grip",
    "Glutes", "Quads", "Hamstrings", "Calves", "Shins",
    "Adductors", "Abductors",
]


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


def _balance(dose_map, label, a_ids, b_ids, a_key, b_key):
    a_sum = sum(dose_map[mid] for mid in a_ids)
    b_sum = sum(dose_map[mid] for mid in b_ids)
    if a_sum == 0 and b_sum == 0:
        ratio = None
        log_ratio = None
    else:
        ratio = round(a_sum / max(b_sum, EPS), 4)
        log_ratio = round(math.log((a_sum + EPS) / (b_sum + EPS)), 4)
    return {
        "mode": label,
        a_key: round(a_sum, 2),
        b_key: round(b_sum, 2),
        "ratio": ratio,
        "log_ratio": log_ratio,
        "eps": EPS,
    }


@router.get("/day", summary="Per-muscle load for a single date (all 27 regions) + 7-day rolling + recovery")
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

    decay_from = date_param - timedelta(days=DECAY_LOOKBACK_DAYS - 1)
    window_from = date_param - timedelta(days=ROLLING_WINDOW_DAYS - 1)
    window_to = date_param

    all_sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= decay_from,
        LiftSet.performed_at <= window_to,
    ).all()

    all_ex_ids = list({s.exercise_id for s in all_sets})

    act_lookup = {}
    rw_lookup = {}
    if all_ex_ids:
        for r in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id.in_(all_ex_ids)).all():
            act_lookup[(r.exercise_id, r.muscle_id)] = r.activation_value
        for r in db.query(RoleWeightedMatrixV2).filter(RoleWeightedMatrixV2.exercise_id.in_(all_ex_ids)).all():
            rw_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight

    sets_by_day = defaultdict(list)
    for s in all_sets:
        sets_by_day[s.performed_at].append(s)

    today_sets = sets_by_day.get(date_param, [])

    today_total, today_direct = _compute_day_doses(
        today_sets, muscle_ids, act_lookup, rw_lookup, forearm_id, hands_grip_id
    )

    load_7d_total = defaultdict(float)
    load_7d_direct = defaultdict(float)
    fatigue_total = defaultdict(float)
    fatigue_direct = defaultdict(float)
    last_hit = {}

    tau_by_id = {}
    for mid in muscle_ids:
        tau_by_id[mid] = TAU_TABLE.get(muscle_map[mid], DEFAULT_TAU)

    for day_offset in range(DECAY_LOOKBACK_DAYS):
        d = decay_from + timedelta(days=day_offset)
        day_sets = sets_by_day.get(d, [])
        if not day_sets:
            continue

        day_total, day_direct = _compute_day_doses(
            day_sets, muscle_ids, act_lookup, rw_lookup, forearm_id, hands_grip_id
        )

        days_ago = (date_param - d).days
        in_7d_window = d >= window_from

        for mid in muscle_ids:
            dt = day_total[mid]
            dd = day_direct[mid]

            if dt > 0 or dd > 0:
                tau = tau_by_id[mid]
                weight = math.exp(-days_ago / tau)
                fatigue_total[mid] += dt * weight
                fatigue_direct[mid] += dd * weight

                if mid not in last_hit or d > last_hit[mid]:
                    last_hit[mid] = d

            if in_7d_window:
                load_7d_total[mid] += dt
                load_7d_direct[mid] += dd

    today_ex_ids = list({s.exercise_id for s in today_sets})
    ex_name_map = {e.id: e.name for e in db.query(Exercise).filter(Exercise.id.in_(today_ex_ids)).all()} if today_ex_ids else {}

    total_tonnage = sum(s.tonnage for s in today_sets)

    regions = []
    for mid in muscle_ids:
        derived = (mid == hands_grip_id and forearm_id is not None
                   and not any((eid, mid) in act_lookup for eid in today_ex_ids))

        ft = fatigue_total[mid]
        fd = fatigue_direct[mid]
        fresh_t = round(1.0 / (1.0 + ft / FRESHNESS_K), 4)
        fresh_d = round(1.0 / (1.0 + fd / FRESHNESS_K), 4)

        entry = {
            "muscle": muscle_map[mid],
            "muscle_id": mid,
            "total_dose": round(today_total[mid], 2),
            "direct_dose": round(today_direct[mid], 2),
            "load_7d_total": round(load_7d_total[mid], 2),
            "load_7d_direct": round(load_7d_direct[mid], 2),
            "recovery": {
                "model": "exp_decay_v1",
                "tau_days": tau_by_id[mid],
                "fatigue_total": round(ft, 2),
                "fatigue_direct": round(fd, 2),
                "freshness_total": fresh_t,
                "freshness_direct": fresh_d,
                "last_hit": str(last_hit[mid]) if mid in last_hit else None,
            },
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

    name_to_id = {v: k for k, v in muscle_map.items()}

    def _resolve_ids(members):
        return [name_to_id[n] for n in members if n in name_to_id]

    push_ids = _resolve_ids(PUSH_MEMBERS)
    pull_ids = _resolve_ids(PULL_MEMBERS)
    ant_ids = _resolve_ids(ANTERIOR_MEMBERS)
    post_ids = _resolve_ids(POSTERIOR_MEMBERS)
    upper_ids = _resolve_ids(UPPER_MEMBERS)
    lower_ids = _resolve_ids(LOWER_MEMBERS)
    axial_ids = _resolve_ids(AXIAL_MEMBERS)
    append_ids = _resolve_ids(APPENDICULAR_MEMBERS)

    balances = {
        "push_pull_total": _balance(today_total, "total", push_ids, pull_ids, "push_sum", "pull_sum"),
        "push_pull_direct": _balance(today_direct, "direct", push_ids, pull_ids, "push_sum", "pull_sum"),
        "ant_post_total": _balance(today_total, "total", ant_ids, post_ids, "anterior_sum", "posterior_sum"),
        "ant_post_direct": _balance(today_direct, "direct", ant_ids, post_ids, "anterior_sum", "posterior_sum"),
        "upper_lower_total": _balance(today_total, "total", upper_ids, lower_ids, "upper_sum", "lower_sum"),
        "upper_lower_direct": _balance(today_direct, "direct", upper_ids, lower_ids, "upper_sum", "lower_sum"),
        "axial_appendicular_total": _balance(today_total, "total", axial_ids, append_ids, "axial_sum", "appendicular_sum"),
        "axial_appendicular_direct": _balance(today_direct, "direct", axial_ids, append_ids, "axial_sum", "appendicular_sum"),
    }

    balances_scope = {
        "push_pull": "full_body",
        "ant_post": "full_body",
        "upper_lower": "full_body",
        "axial_appendicular": "full_body",
    }

    balances_definitions = {
        "push_pull": {
            "push_muscle_ids": push_ids,
            "push_muscles": PUSH_MEMBERS,
            "pull_muscle_ids": pull_ids,
            "pull_muscles": PULL_MEMBERS,
        },
        "ant_post": {
            "anterior_muscle_ids": ant_ids,
            "anterior_muscles": ANTERIOR_MEMBERS,
            "posterior_muscle_ids": post_ids,
            "posterior_muscles": POSTERIOR_MEMBERS,
        },
        "upper_lower": {
            "upper_muscle_ids": upper_ids,
            "upper_muscles": UPPER_MEMBERS,
            "lower_muscle_ids": lower_ids,
            "lower_muscles": LOWER_MEMBERS,
        },
        "axial_appendicular": {
            "axial_muscle_ids": axial_ids,
            "axial_muscles": AXIAL_MEMBERS,
            "appendicular_muscle_ids": append_ids,
            "appendicular_muscles": APPENDICULAR_MEMBERS,
        },
    }

    return {
        "date": str(date_param),
        "source": "intel",
        "muscle_schema_version": MUSCLE_SCHEMA_VERSION,
        "balance_schema_version": BALANCE_SCHEMA_VERSION,
        "recovery_schema_version": RECOVERY_SCHEMA_VERSION,
        "window_from": str(window_from),
        "window_to": str(window_to),
        "total_sets": len(today_sets),
        "total_tonnage": round(total_tonnage, 2),
        "exercises": exercises_used,
        "regions": regions,
        "balances": balances,
        "balances_scope": balances_scope,
        "balances_definitions": balances_definitions,
    }
