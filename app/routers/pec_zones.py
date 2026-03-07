import re
from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2, PhaseMatrixV3,
    StabilizationMatrixV5,
)
from app.pec_zones import (
    allocate_pec_zones_for_signal,
    aggregate_pec_zones,
    get_base_pec_zone_shares,
    compute_v2_shares,
)

router = APIRouter(prefix="/reports/pec-zones", tags=["pec-zones"])

_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")

ZONE_LABELS = {"upper": "Upper Pec", "mid": "Mid Pec", "lower": "Lower Pec"}
METHOD_TAG = "v2.5_overlay_geometry_phase_proxy_grip"

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


def _build_lookups(db: Session, exercise_ids, pec_id):
    act_lookup = {}
    role_lookup = {}
    phase_lookup = {}
    stab_lookup = {}
    if exercise_ids:
        for a in db.query(ActivationMatrixV2).filter(
            ActivationMatrixV2.exercise_id.in_(exercise_ids)
        ).all():
            act_lookup[(a.exercise_id, a.muscle_id)] = a.activation_value
        for r in db.query(RoleWeightedMatrixV2).filter(
            RoleWeightedMatrixV2.exercise_id.in_(exercise_ids)
        ).all():
            role_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight
        for p in db.query(PhaseMatrixV3).filter(
            PhaseMatrixV3.exercise_id.in_(exercise_ids),
            PhaseMatrixV3.muscle_id == pec_id,
        ).all():
            phase_lookup[(p.exercise_id, p.phase)] = p.phase_value
        for s in db.query(StabilizationMatrixV5).filter(
            StabilizationMatrixV5.exercise_id.in_(exercise_ids),
            StabilizationMatrixV5.component == "stability",
        ).all():
            stab_lookup[(s.exercise_id, s.muscle_id)] = s.value
    return act_lookup, role_lookup, phase_lookup, stab_lookup


def _compute_pec_zone_records(sets, ex_name_map, act_lookup, role_lookup,
                               phase_lookup, stab_lookup,
                               pec_id, fd_id, tri_id):
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

        fd_stab = stab_lookup.get((s.exercise_id, fd_id), 0) if fd_id else 0
        tri_stab = stab_lookup.get((s.exercise_id, tri_id), 0) if tri_id else 0

        fd_signal = s.tonnage * (fd_act / 5.0) + s.tonnage * fd_stab * 0.3
        tri_signal = s.tonnage * (tri_act / 5.0) + s.tonnage * tri_stab * 0.3

        pec_init = phase_lookup.get((s.exercise_id, "initiation"), 0)
        pec_mid = phase_lookup.get((s.exercise_id, "midrange"), 0)
        pec_lock = phase_lookup.get((s.exercise_id, "lockout"), 0)

        ex_name = ex_name_map.get(s.exercise_id, "Unknown")

        rec = allocate_pec_zones_for_signal(
            exercise_name=ex_name,
            pectorals_total_dose=pec_total,
            pectorals_direct_dose=pec_direct,
            front_delt_signal=fd_signal,
            triceps_signal=tri_signal,
            pec_init=pec_init,
            pec_mid=pec_mid,
            pec_lock=pec_lock,
        )
        rec["exercise"] = ex_name
        records.append(rec)

    return records


def _empty_zone_response():
    return [
        {"zone": ZONE_LABELS[z], "total_dose": 0, "direct_dose": 0, "share": round(s, 4)}
        for z, s in [("upper", 0.33), ("mid", 0.34), ("lower", 0.33)]
    ]


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
        "confidence": agg.get("confidence", 0.30),
        "meta": {
            "method": METHOD_TAG,
            "canonical_muscle_unchanged": True,
            "data_provenance": "authored_biomechanics_priors",
        },
    }


@router.get("/day", summary="Pec zone proxy breakdown for a single day")
def pec_zones_day(
    date_param: date = Query(..., alias="date", description="Date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    pec_id, fd_id, tri_id = _resolve_muscle_ids(db)

    sets = db.query(LiftSet).filter(LiftSet.performed_at == date_param).all()

    _empty_meta = {"method": METHOD_TAG, "canonical_muscle_unchanged": True, "data_provenance": "authored_biomechanics_priors"}

    if not sets:
        return {
            "date": str(date_param),
            "zones": _empty_zone_response(),
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "confidence": None,
            "meta": _empty_meta,
        }

    exercise_ids = list({s.exercise_id for s in sets})
    ex_objs = db.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
    ex_name_map = {e.id: e.name for e in ex_objs}
    act_lookup, role_lookup, phase_lookup, stab_lookup = _build_lookups(db, exercise_ids, pec_id)

    records = _compute_pec_zone_records(
        sets, ex_name_map, act_lookup, role_lookup, phase_lookup, stab_lookup,
        pec_id, fd_id, tri_id
    )

    if not records:
        return {
            "date": str(date_param),
            "zones": _empty_zone_response(),
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "confidence": None,
            "meta": _empty_meta,
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

    sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= monday, LiftSet.performed_at <= sunday
    ).all()

    _empty_meta = {"method": METHOD_TAG, "canonical_muscle_unchanged": True, "data_provenance": "authored_biomechanics_priors"}

    if not sets:
        return {
            "week": week,
            "window": {"start_date": str(monday), "end_date": str(sunday), "days": 7},
            "zones": _empty_zone_response(),
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "confidence": None,
            "meta": _empty_meta,
        }

    exercise_ids = list({s.exercise_id for s in sets})
    ex_objs = db.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
    ex_name_map = {e.id: e.name for e in ex_objs}
    act_lookup, role_lookup, phase_lookup, stab_lookup = _build_lookups(db, exercise_ids, pec_id)

    records = _compute_pec_zone_records(
        sets, ex_name_map, act_lookup, role_lookup, phase_lookup, stab_lookup,
        pec_id, fd_id, tri_id
    )

    if not records:
        return {
            "week": week,
            "window": {"start_date": str(monday), "end_date": str(sunday), "days": 7},
            "zones": _empty_zone_response(),
            "pectorals": {"total_dose": 0, "direct_dose": 0},
            "confidence": None,
            "meta": _empty_meta,
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

    phase_lookup = {}
    for p in db.query(PhaseMatrixV3).filter(
        PhaseMatrixV3.exercise_id == ex.id,
        PhaseMatrixV3.muscle_id == pec_id,
    ).all():
        phase_lookup[p.phase] = p.phase_value

    stab_lookup = {}
    for s in db.query(StabilizationMatrixV5).filter(
        StabilizationMatrixV5.exercise_id == ex.id,
        StabilizationMatrixV5.component == "stability",
    ).all():
        stab_lookup[s.muscle_id] = s.value

    pec_act = act_lookup.get(pec_id, 0)
    fd_act = act_lookup.get(fd_id, 0) if fd_id else 0
    tri_act = act_lookup.get(tri_id, 0) if tri_id else 0
    fd_stab = stab_lookup.get(fd_id, 0) if fd_id else 0
    tri_stab = stab_lookup.get(tri_id, 0) if tri_id else 0

    fd_signal = fd_act / 5.0 + fd_stab * 0.3
    tri_signal = tri_act / 5.0 + tri_stab * 0.3

    pec_init = phase_lookup.get("initiation", 0)
    pec_mid = phase_lookup.get("midrange", 0)
    pec_lock = phase_lookup.get("lockout", 0)

    base, source, overlay_features, confidence, drivers = get_base_pec_zone_shares(exercise_name)
    final, _, adjustments, _, _ = compute_v2_shares(
        exercise_name, fd_signal, tri_signal,
        pec_init, pec_mid, pec_lock,
    )

    return {
        "exercise_name": exercise_name,
        "pectorals_activation": pec_act,
        "base_shares": {k: round(v, 4) for k, v in base.items()},
        "adjusted_shares": {k: round(v, 4) for k, v in final.items()},
        "confidence": round(confidence, 4),
        "drivers": drivers,
        "adjustments": adjustments,
        "meta": {
            "method": METHOD_TAG,
            "base_profile_source": source,
            "data_provenance": "authored_biomechanics_priors",
        },
    }


@router.get("/analysis", summary="Full v2.5 pipeline analysis for an exercise")
def pec_zones_analysis(
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

    phase_lookup = {}
    for p in db.query(PhaseMatrixV3).filter(
        PhaseMatrixV3.exercise_id == ex.id,
        PhaseMatrixV3.muscle_id == pec_id,
    ).all():
        phase_lookup[p.phase] = p.phase_value

    stab_lookup = {}
    for s in db.query(StabilizationMatrixV5).filter(
        StabilizationMatrixV5.exercise_id == ex.id,
        StabilizationMatrixV5.component == "stability",
    ).all():
        stab_lookup[s.muscle_id] = s.value

    pec_act = act_lookup.get(pec_id, 0)
    fd_act = act_lookup.get(fd_id, 0) if fd_id else 0
    tri_act = act_lookup.get(tri_id, 0) if tri_id else 0
    fd_stab = stab_lookup.get(fd_id, 0) if fd_id else 0
    tri_stab = stab_lookup.get(tri_id, 0) if tri_id else 0

    fd_signal = fd_act / 5.0 + fd_stab * 0.3
    tri_signal = tri_act / 5.0 + tri_stab * 0.3

    pec_init = phase_lookup.get("initiation", 0)
    pec_mid = phase_lookup.get("midrange", 0)
    pec_lock = phase_lookup.get("lockout", 0)

    base, source, overlay_features, confidence, drivers = get_base_pec_zone_shares(exercise_name)
    final, _, adjustments, _, _ = compute_v2_shares(
        exercise_name, fd_signal, tri_signal,
        pec_init, pec_mid, pec_lock,
    )

    return {
        "exercise": exercise_name,
        "pectorals_activation": pec_act,
        "base_profile": {k: round(v, 4) for k, v in base.items()},
        "base_profile_source": source,
        "overlay": {
            "source": source,
            "features": {k: round(v, 4) for k, v in overlay_features.items()},
            "computed_base_shares": {k: round(v, 4) for k, v in base.items()},
        },
        "confidence": round(confidence, 4),
        "drivers": drivers,
        "geometry_adjustment": adjustments["geometry"],
        "phase_adjustment": adjustments["phase"],
        "proxy_adjustment": adjustments["proxy"],
        "grip_adjustment": adjustments["grip"],
        "final_shares": {k: round(v, 4) for k, v in final.items()},
        "raw_inputs": {
            "front_delt_activation": fd_act,
            "triceps_activation": tri_act,
            "front_delt_stability": fd_stab,
            "triceps_stability": tri_stab,
            "pec_phase_init": pec_init,
            "pec_phase_mid": pec_mid,
            "pec_phase_lock": pec_lock,
        },
        "meta": {
            "method": METHOD_TAG,
            "canonical_muscle_unchanged": True,
            "data_provenance": "authored_biomechanics_priors",
        },
    }
