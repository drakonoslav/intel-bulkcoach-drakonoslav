import re
from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
)
from app.pec_zones import (
    allocate_pec_zones_for_signal,
    aggregate_pec_zones,
    get_base_pec_zone_shares,
    adjust_pec_zone_shares,
)

router = APIRouter(prefix="/reports/pec-zones", tags=["pec-zones"])

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")

ZONE_LABELS = {"upper": "Upper Pec", "mid": "Mid Pec", "lower": "Lower Pec"}

PECTORALS_NAME = "Pectorals"
FRONT_DELT_NAME = "Front/Anterior Delt"
TRICEPS_NAME = "Triceps"


def _iso_week_bounds(week_str: str):
    m = _WEEK_RE.match(week_str)
    if not m:
        raise HTTPException(status_code=400, detail=f"Invalid week format: '{week_str}'. Expected YYYY-WNN.")
    year, wk = int(m.group(1)), int(m.group(2))
    if wk < 1 or wk > 53:
        raise HTTPException(status_code=400, detail=f"Week number must be 01-53, got {wk:02d}.")
    jan4 = date(year, 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = start_of_w1 + timedelta(weeks=wk - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _resolve_muscle_ids(db: Session):
    muscles = db.query(Muscle).all()
    name_to_id = {m.name: m.id for m in muscles}
    pec_id = name_to_id.get(PECTORALS_NAME)
    fd_id = name_to_id.get(FRONT_DELT_NAME)
    tri_id = name_to_id.get(TRICEPS_NAME)
    if pec_id is None:
        raise HTTPException(status_code=500, detail="Pectorals muscle not found in database")
    return pec_id, fd_id, tri_id


def _build_lookups(db: Session, exercise_ids):
    act_lookup = {}
    role_lookup = {}
    if exercise_ids:
        for a in db.query(ActivationMatrixV2).filter(
            ActivationMatrixV2.exercise_id.in_(exercise_ids)
        ).all():
            act_lookup[(a.exercise_id, a.muscle_id)] = a.activation_value
        for r in db.query(RoleWeightedMatrixV2).filter(
            RoleWeightedMatrixV2.exercise_id.in_(exercise_ids)
        ).all():
            role_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight
    return act_lookup, role_lookup


def _compute_pec_zone_records(sets, ex_name_map, act_lookup, role_lookup, pec_id, fd_id, tri_id):
    records = []
    for s in sets:
        pec_act = act_lookup.get((s.exercise_id, pec_id), 0)
        if pec_act <= 0:
            continue

        pec_rw = role_lookup.get((s.exercise_id, pec_id), 0)
        pec_total = s.tonnage * (pec_act / 5.0)
        pec_direct = s.tonnage * pec_rw

        fd_act = act_lookup.get((s.exercise_id, fd_id), 0) if fd_id else 0
        tri_act = act_lookup.get((s.exercise_id, tri_id), 0) if tri_id else 0
        fd_signal = s.tonnage * (fd_act / 5.0)
        tri_signal = s.tonnage * (tri_act / 5.0)

        ex_name = ex_name_map.get(s.exercise_id, "Unknown")

        rec = allocate_pec_zones_for_signal(
            exercise_name=ex_name,
            pectorals_total_dose=pec_total,
            pectorals_direct_dose=pec_direct,
            front_delt_signal=fd_signal,
            triceps_signal=tri_signal,
        )
        rec["exercise"] = ex_name
        records.append(rec)

    return records


def _format_zone_response(agg, pec_total, pec_direct):
    zones = []
    for z in ("upper", "mid", "lower"):
        zones.append({
            "zone": ZONE_LABELS[z],
            "total_dose": round(agg["total_dose"][z], 4),
            "direct_dose": round(agg["direct_dose"][z], 4),
            "share": round(agg["shares"][z], 4),
        })
    return {
        "zones": zones,
        "pectorals": {
            "total_dose": round(pec_total, 4),
            "direct_dose": round(pec_direct, 4),
        },
        "meta": {
            "method": "base_profile_plus_proxy_adjustment_v1",
            "canonical_muscle_unchanged": True,
        },
    }


@router.get("/day", summary="Pec zone proxy breakdown for a single day")
def pec_zones_day(
    date_param: date = Query(..., alias="date", description="Date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    pec_id, fd_id, tri_id = _resolve_muscle_ids(db)

    sets = (
        db.query(LiftSet)
        .filter(LiftSet.performed_at == date_param)
        .all()
    )

    if not sets:
        return {
            "date": str(date_param),
            "zones": [
                {"zone": ZONE_LABELS[z], "total_dose": 0, "direct_dose": 0, "share": round(s, 4)}
                for z, s in [("upper", 0.33), ("mid", 0.34), ("lower", 0.33)]
            ],
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "meta": {"method": "base_profile_plus_proxy_adjustment_v1", "canonical_muscle_unchanged": True},
        }

    exercise_ids = list({s.exercise_id for s in sets})
    ex_objs = db.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
    ex_name_map = {e.id: e.name for e in ex_objs}
    act_lookup, role_lookup = _build_lookups(db, exercise_ids)

    records = _compute_pec_zone_records(sets, ex_name_map, act_lookup, role_lookup, pec_id, fd_id, tri_id)

    if not records:
        return {
            "date": str(date_param),
            "zones": [
                {"zone": ZONE_LABELS[z], "total_dose": 0, "direct_dose": 0, "share": round(s, 4)}
                for z, s in [("upper", 0.33), ("mid", 0.34), ("lower", 0.33)]
            ],
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "meta": {"method": "base_profile_plus_proxy_adjustment_v1", "canonical_muscle_unchanged": True},
        }

    agg = aggregate_pec_zones(records)
    pec_total = sum(r["total_dose"]["upper"] + r["total_dose"]["mid"] + r["total_dose"]["lower"] for r in records)
    pec_direct = sum(r["direct_dose"]["upper"] + r["direct_dose"]["mid"] + r["direct_dose"]["lower"] for r in records)

    result = _format_zone_response(agg, pec_total, pec_direct)
    result["date"] = str(date_param)
    return result


@router.get("/week", summary="Pec zone proxy breakdown for a week")
def pec_zones_week(
    week: str = Query(..., description="ISO week YYYY-WNN", examples=["2026-W09"]),
    db: Session = Depends(get_db),
):
    monday, sunday = _iso_week_bounds(week)
    pec_id, fd_id, tri_id = _resolve_muscle_ids(db)

    sets = (
        db.query(LiftSet)
        .filter(LiftSet.performed_at >= monday, LiftSet.performed_at <= sunday)
        .all()
    )

    if not sets:
        return {
            "week": week,
            "window": {"start_date": str(monday), "end_date": str(sunday), "days": 7},
            "zones": [
                {"zone": ZONE_LABELS[z], "total_dose": 0, "direct_dose": 0, "share": round(s, 4)}
                for z, s in [("upper", 0.33), ("mid", 0.34), ("lower", 0.33)]
            ],
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "meta": {"method": "base_profile_plus_proxy_adjustment_v1", "canonical_muscle_unchanged": True},
        }

    exercise_ids = list({s.exercise_id for s in sets})
    ex_objs = db.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
    ex_name_map = {e.id: e.name for e in ex_objs}
    act_lookup, role_lookup = _build_lookups(db, exercise_ids)

    records = _compute_pec_zone_records(sets, ex_name_map, act_lookup, role_lookup, pec_id, fd_id, tri_id)

    if not records:
        return {
            "week": week,
            "window": {"start_date": str(monday), "end_date": str(sunday), "days": 7},
            "zones": [
                {"zone": ZONE_LABELS[z], "total_dose": 0, "direct_dose": 0, "share": round(s, 4)}
                for z, s in [("upper", 0.33), ("mid", 0.34), ("lower", 0.33)]
            ],
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "meta": {"method": "base_profile_plus_proxy_adjustment_v1", "canonical_muscle_unchanged": True},
        }

    agg = aggregate_pec_zones(records)
    pec_total = sum(r["total_dose"]["upper"] + r["total_dose"]["mid"] + r["total_dose"]["lower"] for r in records)
    pec_direct = sum(r["direct_dose"]["upper"] + r["direct_dose"]["mid"] + r["direct_dose"]["lower"] for r in records)

    result = _format_zone_response(agg, pec_total, pec_direct)
    result["week"] = week
    result["window"] = {"start_date": str(monday), "end_date": str(sunday), "days": 7}
    return result


@router.get("/explain", summary="Explain pec zone profile for an exercise")
def pec_zones_explain(
    exercise_name: str = Query(..., alias="exercise", description="Canonical exercise name"),
    db: Session = Depends(get_db),
):
    ex = db.query(Exercise).filter(Exercise.name == exercise_name).first()
    if not ex:
        all_names = sorted(e.name for e in db.query(Exercise).all())
        raise HTTPException(status_code=404, detail=f"Unknown exercise: '{exercise_name}'. Valid: {all_names}")

    pec_id, fd_id, tri_id = _resolve_muscle_ids(db)

    act_lookup = {}
    for a in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id == ex.id).all():
        act_lookup[a.muscle_id] = a.activation_value

    pec_act = act_lookup.get(pec_id, 0)
    fd_act = act_lookup.get(fd_id, 0) if fd_id else 0
    tri_act = act_lookup.get(tri_id, 0) if tri_id else 0

    base, source = get_base_pec_zone_shares(exercise_name)
    adjusted, proxy_applied = adjust_pec_zone_shares(
        dict(base),
        front_delt_signal=fd_act,
        triceps_signal=tri_act,
    )

    return {
        "exercise_name": exercise_name,
        "pectorals_activation": pec_act,
        "base_shares": {k: round(v, 4) for k, v in base.items()},
        "proxy_inputs": {
            "front_delt_signal": fd_act,
            "triceps_signal": tri_act,
        },
        "adjusted_shares": {k: round(v, 4) for k, v in adjusted.items()},
        "meta": {
            "base_profile_source": source,
            "proxy_adjustment_applied": proxy_applied,
        },
    }
