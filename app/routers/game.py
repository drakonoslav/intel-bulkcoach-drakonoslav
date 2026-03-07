import logging
from datetime import date, datetime
from collections import defaultdict
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, GameBridgeSet,
)
from app.game_state import (
    MUSCLE_SCHEMA_VERSION, FRESHNESS_K, READINESS_THRESHOLD,
    W_DEFICIT, W_LOAD_DEFICIT, W_FRESHNESS, W_RECENCY, W_MODE,
    BRIDGE_DEFAULT_TONNAGE, TAU_TABLE, DEFAULT_TAU,
    PUSH_MEMBERS, PULL_MEMBERS, UPPER_MEMBERS, LOWER_MEMBERS,
    ANTERIOR_MEMBERS, POSTERIOR_MEMBERS,
    W_ACT_REL, W_ROLE, W_BN_CLEAR, W_SECONDARY, W_FRESH_BONUS,
    compute_blended_muscle_state, compute_recommended_slots,
    compute_balance_ratios, _recency_norm, _compute_queue_priority,
    compute_exercise_recommendations, build_exercise_catalog,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game", tags=["game"])

FIELD_SOURCES = {
    "muscle_id": "canonical",
    "muscle": "canonical",
    "freshness": "derived",
    "fatigue": "derived",
    "load_7d": "canonical",
    "last_hit": "canonical",
    "days_since_hit": "derived",
    "underfed_score": "derived",
    "status": "derived",
    "tau_days": "canonical",
    "heatmap_intensity": "derived",
    "queue_priority": "derived",
    "compound_suitability": "estimated",
    "isolation_suitability": "estimated",
    "data_blend": "canonical",
}


@router.get("/muscle-state", summary="27-muscle physiological state snapshot for Expo game")
def muscle_state(
    date_param: date = Query(default=None, alias="date", examples=["2026-03-07"]),
    db: Session = Depends(get_db),
):
    if date_param is None:
        date_param = date.today()

    results, muscle_ids, muscle_map, name_to_id, load_7d, *_ = compute_blended_muscle_state(date_param, db)

    balances = compute_balance_ratios(load_7d, name_to_id)

    return {
        "date": str(date_param),
        "muscle_schema_version": MUSCLE_SCHEMA_VERSION,
        "muscles": results,
        "balances": balances,
        "meta": {
            "freshness_model": "exp_decay_v1",
            "freshness_k": FRESHNESS_K,
            "priority_model": "v1_weighted",
            "freshness_interpretation": "Normalized readiness index (0-1). NOT a literal recovery percentage. Derived from exponential-decay fatigue model.",
            "field_sources": FIELD_SOURCES,
        },
    }


@router.get("/muscle-priority", summary="Ranked muscle training queue filtered by mode")
def muscle_priority(
    mode: str = Query(..., description="compound or isolation", examples=["compound"]),
    date_param: date = Query(default=None, alias="date", examples=["2026-03-07"]),
    top_n: int = Query(8, ge=1, le=27, description="Max muscles to return in queue"),
    db: Session = Depends(get_db),
):
    if mode not in ("compound", "isolation"):
        raise HTTPException(status_code=400, detail="mode must be 'compound' or 'isolation'")

    if date_param is None:
        date_param = date.today()

    (results, muscle_ids, muscle_map, name_to_id, load_7d,
     freshness_map, days_since_map, underfed_scores, statuses,
     compound_suit, isolation_suit, load_deficit_map) = compute_blended_muscle_state(date_param, db)

    suit_map = compound_suit if mode == "compound" else isolation_suit
    slots_map = compute_recommended_slots(db, muscle_ids, muscle_map)

    queue = []
    gated_out = []

    for mid in muscle_ids:
        fresh = freshness_map[mid]
        recency = _recency_norm(days_since_map[mid])
        mode_suit = suit_map.get(mid, 0.0)
        ld = load_deficit_map.get(mid, 0.5)

        if fresh < READINESS_THRESHOLD:
            gated_out.append({
                "muscle_id": mid,
                "muscle": muscle_map[mid],
                "reason": "freshness_below_threshold",
                "freshness": fresh,
            })
            continue

        priority = _compute_queue_priority(fresh, underfed_scores[mid], recency, mode_suit, ld)

        queue.append({
            "muscle_id": mid,
            "muscle": muscle_map[mid],
            "priority_score": round(priority, 4),
            "priority_breakdown": {
                "deficit_component": round(underfed_scores[mid] / 100.0, 4),
                "load_deficit_component": round(ld, 4),
                "freshness_component": fresh,
                "recency_component": round(recency, 4),
                "readiness_gate": 1.0,
                "mode_suitability": round(mode_suit, 4),
            },
            "status": statuses[mid],
            "freshness": fresh,
            "days_since_hit": days_since_map[mid],
            "recommended_slots": slots_map.get(mid, []),
        })

    queue.sort(key=lambda x: -x["priority_score"])
    for i, item in enumerate(queue):
        item["rank"] = i + 1

    return {
        "date": str(date_param),
        "mode": mode,
        "queue": queue[:top_n],
        "gated_out": gated_out,
        "meta": {
            "scoring_model": "v2_load_aware",
            "readiness_threshold": READINESS_THRESHOLD,
            "weights": {
                "deficit": W_DEFICIT,
                "load_deficit": W_LOAD_DEFICIT,
                "freshness": W_FRESHNESS,
                "recency": W_RECENCY,
                "mode_suitability": W_MODE,
            },
        },
    }


class GameLogSetRequest(BaseModel):
    event_id: Optional[str] = Field(None, examples=["evt-abc123-001"])
    exercise_id: Optional[int] = Field(None, examples=[37])
    weight: Optional[float] = Field(None, ge=0, examples=[80.0])
    reps: Optional[int] = Field(None, ge=0, examples=[8])
    muscle_targets: Optional[List[int]] = Field(None, examples=[[1, 5]])
    movement_type: Optional[str] = Field(None, examples=["compound"])
    rpe: Optional[int] = Field(None, ge=1, le=10, examples=[8])
    estimated_tonnage: Optional[float] = Field(None, ge=0, examples=[640.0])
    performed_at: date = Field(..., examples=["2026-03-07"])
    session_id: Optional[str] = Field(None, examples=["expo-session-abc123"])
    source: Optional[str] = Field(None, examples=["expo_bulkcoach"])
    notes: Optional[str] = None


@router.post("/log-set", summary="Log a workout action from Expo (exercise-level or bridge mode)")
def log_set(payload: GameLogSetRequest, db: Session = Depends(get_db)):
    has_exercise = payload.exercise_id is not None
    has_targets = payload.muscle_targets is not None and len(payload.muscle_targets) > 0

    if has_exercise and has_targets:
        raise HTTPException(status_code=400, detail="Provide exactly one of exercise_id or muscle_targets, not both.")
    if not has_exercise and not has_targets:
        raise HTTPException(status_code=400, detail="Provide exactly one of exercise_id or muscle_targets.")

    if has_exercise:
        return _log_exercise_level(payload, db)
    else:
        return _log_bridge(payload, db)


def _log_exercise_level(payload: GameLogSetRequest, db: Session):
    if payload.event_id:
        existing = db.query(LiftSet).filter(
            LiftSet.event_id == payload.event_id,
        ).first()
        if existing:
            return {
                "logged": False,
                "reason": "duplicate_event_id",
                "event_id": payload.event_id,
                "original_set_id": existing.id,
                "table": "lift_sets",
            }

    ex = db.query(Exercise).filter(Exercise.id == payload.exercise_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail=f"Unknown exercise_id: {payload.exercise_id}")

    if payload.weight is None or payload.reps is None:
        raise HTTPException(status_code=400, detail="weight and reps are required for exercise-level logging.")

    tonnage = payload.weight * payload.reps

    row = LiftSet(
        performed_at=payload.performed_at,
        exercise_id=ex.id,
        weight=payload.weight,
        reps=payload.reps,
        tonnage=tonnage,
        notes=payload.notes,
        source=payload.source or "expo_bulkcoach",
        event_id=payload.event_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    act_rows = db.query(ActivationMatrixV2).filter(
        ActivationMatrixV2.exercise_id == ex.id
    ).all()

    muscles_map = {m.id: m.name for m in db.query(Muscle).all()}
    muscles_affected = []
    for ar in act_rows:
        if ar.activation_value > 0:
            dose = tonnage * (ar.activation_value / 5.0)
            muscles_affected.append({
                "muscle_id": ar.muscle_id,
                "muscle": muscles_map.get(ar.muscle_id, f"id:{ar.muscle_id}"),
                "dose_added": round(dose, 2),
            })

    muscles_affected.sort(key=lambda x: -x["dose_added"])

    result = {
        "logged": True,
        "mode": "exercise_level",
        "set_id": row.id,
        "table": "lift_sets",
        "tonnage": round(tonnage, 2),
        "muscles_affected": muscles_affected,
    }
    if payload.event_id:
        result["event_id"] = payload.event_id
    return result


def _log_bridge(payload: GameLogSetRequest, db: Session):
    if payload.movement_type not in ("compound", "isolation"):
        raise HTTPException(status_code=400, detail="movement_type must be 'compound' or 'isolation'.")

    valid_muscles = {m.id: m.name for m in db.query(Muscle).all()}
    for mid in payload.muscle_targets:
        if mid not in valid_muscles:
            raise HTTPException(status_code=400, detail=f"Invalid muscle_id: {mid}. Must be from canonical 27.")

    if payload.event_id:
        existing = db.query(GameBridgeSet).filter(
            GameBridgeSet.event_id == payload.event_id
        ).first()
        if existing:
            all_existing = db.query(GameBridgeSet).filter(
                GameBridgeSet.event_id == payload.event_id
            ).all()
            return {
                "logged": False,
                "reason": "duplicate_event_id",
                "event_id": payload.event_id,
                "original_bridge_ids": [e.id for e in all_existing],
                "table": "game_bridge_sets",
            }

    base_tonnage = payload.estimated_tonnage if payload.estimated_tonnage is not None else BRIDGE_DEFAULT_TONNAGE[payload.movement_type]
    rpe_value = payload.rpe if payload.rpe is not None else 7
    rpe_scale = rpe_value / 10.0
    scaled_tonnage = base_tonnage * rpe_scale
    n_targets = len(payload.muscle_targets)
    dose_per_muscle = scaled_tonnage / n_targets

    rows = []
    for mid in payload.muscle_targets:
        row = GameBridgeSet(
            event_id=payload.event_id,
            performed_at=payload.performed_at,
            muscle_id=mid,
            dose_estimate=dose_per_muscle,
            rpe=payload.rpe,
            movement_type=payload.movement_type,
            session_id=payload.session_id,
            source=payload.source or "expo_game_bridge",
            notes=payload.notes,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for r in rows:
        db.refresh(r)

    result = {
        "logged": True,
        "mode": "bridge",
        "bridge_ids": [r.id for r in rows],
        "table": "game_bridge_sets",
        "dose_formula": {
            "base_tonnage": base_tonnage,
            "rpe_scale": rpe_scale,
            "scaled_tonnage": round(scaled_tonnage, 2),
            "targets": n_targets,
            "dose_per_muscle": round(dose_per_muscle, 2),
        },
        "muscles_affected": [
            {
                "muscle_id": r.muscle_id,
                "muscle": valid_muscles[r.muscle_id],
                "dose_estimate": round(dose_per_muscle, 2),
            }
            for r in rows
        ],
    }
    if payload.event_id:
        result["event_id"] = payload.event_id
    return result


class SessionCloseRequest(BaseModel):
    session_id: str = Field(..., examples=["expo-session-abc123"])
    session_start: Optional[str] = Field(None, examples=["2026-03-07T09:00:00Z"])
    session_end: Optional[str] = Field(None, examples=["2026-03-07T10:15:00Z"])
    mode: Optional[str] = Field(None, examples=["compound"])
    source: Optional[str] = Field(None, examples=["expo_bulkcoach"])


@router.post("/session-close", summary="Finalize session and return summary (read-only, optional)")
def session_close(payload: SessionCloseRequest, db: Session = Depends(get_db)):
    bridge_rows = db.query(GameBridgeSet).filter(
        GameBridgeSet.session_id == payload.session_id
    ).all()

    canonical_sets = []
    if payload.source:
        q = db.query(LiftSet).filter(LiftSet.source == payload.source)
        if payload.session_start and payload.session_end:
            try:
                start_dt = datetime.fromisoformat(payload.session_start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(payload.session_end.replace("Z", "+00:00"))
                q = q.filter(
                    LiftSet.performed_at >= start_dt.date(),
                    LiftSet.performed_at <= end_dt.date(),
                )
            except (ValueError, TypeError):
                pass
        canonical_sets = q.all()

    all_muscles = {m.id: m.name for m in db.query(Muscle).all()}

    act_lookup = {}
    if canonical_sets:
        ex_ids = list({s.exercise_id for s in canonical_sets})
        for ar in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id.in_(ex_ids)).all():
            act_lookup[(ar.exercise_id, ar.muscle_id)] = ar.activation_value

    muscle_dose_canonical = defaultdict(float)
    total_canonical_tonnage = 0.0
    for s in canonical_sets:
        total_canonical_tonnage += s.tonnage
        for mid in all_muscles:
            av = act_lookup.get((s.exercise_id, mid), 0)
            if av > 0:
                muscle_dose_canonical[mid] += s.tonnage * (av / 5.0)

    muscle_dose_bridge = defaultdict(float)
    total_bridge_tonnage = 0.0
    for br in bridge_rows:
        muscle_dose_bridge[br.muscle_id] += br.dose_estimate
        total_bridge_tonnage += br.dose_estimate

    all_muscle_ids = set(muscle_dose_canonical.keys()) | set(muscle_dose_bridge.keys())

    muscles_trained = []
    for mid in sorted(all_muscle_ids):
        c_dose = muscle_dose_canonical.get(mid, 0.0)
        b_dose = muscle_dose_bridge.get(mid, 0.0)
        total = c_dose + b_dose
        if total > 0:
            if c_dose > 0 and b_dose > 0:
                src = "blended"
            elif c_dose > 0:
                src = "canonical"
            else:
                src = "bridge_estimate"
            muscles_trained.append({
                "muscle_id": mid,
                "muscle": all_muscles.get(mid, f"id:{mid}"),
                "session_dose": round(total, 2),
                "source": src,
            })

    muscles_trained.sort(key=lambda x: -x["session_dose"])
    top_muscle = muscles_trained[0]["muscle"] if muscles_trained else None

    duration_minutes = None
    if payload.session_start and payload.session_end:
        try:
            start_dt = datetime.fromisoformat(payload.session_start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(payload.session_end.replace("Z", "+00:00"))
            duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        except (ValueError, TypeError):
            pass

    name_to_id = {v: k for k, v in all_muscles.items()}

    combined_dose = defaultdict(float)
    for mid in all_muscle_ids:
        combined_dose[mid] = muscle_dose_canonical.get(mid, 0.0) + muscle_dose_bridge.get(mid, 0.0)

    eps = 1e-6
    push_sum = sum(combined_dose.get(name_to_id.get(m, -1), 0.0) for m in PUSH_MEMBERS)
    pull_sum = sum(combined_dose.get(name_to_id.get(m, -1), 0.0) for m in PULL_MEMBERS)
    upper_sum = sum(combined_dose.get(name_to_id.get(m, -1), 0.0) for m in UPPER_MEMBERS)
    lower_sum = sum(combined_dose.get(name_to_id.get(m, -1), 0.0) for m in LOWER_MEMBERS)

    balance_impact = {
        "push_pull_shift": round((push_sum - pull_sum) / max(push_sum + pull_sum, eps), 4) if (push_sum + pull_sum) > 0 else 0.0,
        "upper_lower_shift": round((upper_sum - lower_sum) / max(upper_sum + lower_sum, eps), 4) if (upper_sum + lower_sum) > 0 else 0.0,
    }

    total_tonnage = total_canonical_tonnage + total_bridge_tonnage

    return {
        "session_id": payload.session_id,
        "session_summary": {
            "total_sets": len(canonical_sets) + len(bridge_rows),
            "total_tonnage": round(total_tonnage, 2),
            "duration_minutes": duration_minutes,
            "muscles_trained": muscles_trained,
            "top_muscle": top_muscle,
            "canonical_sets": len(canonical_sets),
            "bridge_events": len(bridge_rows),
            "balance_impact": balance_impact,
        },
        "meta": {
            "data_sources_used": sorted(set(
                (["lift_sets"] if canonical_sets else []) +
                (["game_bridge_sets"] if bridge_rows else [])
            )),
            "session_close_semantics": "finalizer_only",
        },
    }


@router.get("/exercise-catalog", summary="Full exercise catalog with slots, equipment, primary muscles")
def exercise_catalog(db: Session = Depends(get_db)):
    catalog = build_exercise_catalog(db)
    return {
        "muscle_schema_version": MUSCLE_SCHEMA_VERSION,
        **catalog,
    }


@router.get("/exercise-recommendations", summary="Scored exercise recommendations for a target muscle")
def exercise_recommendations(
    muscle_id: int = Query(..., description="Target muscle ID from canonical schema"),
    mode: str = Query("compound", description="compound or isolation"),
    date_param: date = Query(default=None, alias="date", examples=["2026-03-07"]),
    top_n: int = Query(5, ge=1, le=30, description="Max exercises to return"),
    available: Optional[str] = Query(None, description="Comma-separated equipment tags, e.g. 'barbell,rack,bench'"),
    db: Session = Depends(get_db),
):
    if mode not in ("compound", "isolation"):
        raise HTTPException(status_code=400, detail="mode must be 'compound' or 'isolation'")

    if date_param is None:
        date_param = date.today()

    muscle = db.query(Muscle).filter(Muscle.id == muscle_id).first()
    if not muscle:
        raise HTTPException(status_code=404, detail=f"muscle_id {muscle_id} not found in canonical schema")

    available_equipment = None
    if available:
        available_equipment = [tag.strip() for tag in available.split(",") if tag.strip()]

    result = compute_exercise_recommendations(
        target_muscle_id=muscle_id,
        mode=mode,
        query_date=date_param,
        db=db,
        top_n=top_n,
        available_equipment=available_equipment,
    )

    return {
        "date": str(date_param),
        "target_muscle_id": muscle_id,
        "target_muscle": muscle.name,
        "mode": mode,
        "top_n": top_n,
        "equipment_filter": available_equipment,
        **result,
        "meta": {
            "scoring_model": "exercise_rec_v1",
            "weights": {
                "activation_relevance": W_ACT_REL,
                "role_weight": W_ROLE,
                "bottleneck_clearance": W_BN_CLEAR,
                "secondary_value": W_SECONDARY,
                "freshness_bonus": W_FRESH_BONUS,
            },
        },
    }


@router.get("/muscle-schema", summary="Canonical 27-muscle schema with IDs, names, and metadata")
def muscle_schema(db: Session = Depends(get_db)):
    from app.hierarchy import build_derived_groups

    muscles = db.query(Muscle).order_by(Muscle.id).all()
    groups = build_derived_groups(db)
    parent_map = {}
    for parent_id, child_ids in groups.items():
        for cid in child_ids:
            parent_map[cid] = parent_id

    muscle_name_map = {m.id: m.name for m in muscles}

    result = []
    for m in muscles:
        tau = TAU_TABLE.get(m.name, DEFAULT_TAU)

        entry = {
            "muscle_id": m.id,
            "muscle": m.name,
            "tau_days": tau,
            "is_derived_group": m.id in groups,
        }

        if m.id in groups:
            entry["children"] = [
                {"muscle_id": cid, "muscle": muscle_name_map.get(cid, f"id:{cid}")}
                for cid in sorted(groups[m.id])
            ]

        if m.id in parent_map:
            pid = parent_map[m.id]
            entry["parent"] = {
                "muscle_id": pid,
                "muscle": muscle_name_map.get(pid, f"id:{pid}"),
            }

        result.append(entry)

    return {
        "muscle_schema_version": MUSCLE_SCHEMA_VERSION,
        "total_muscles": len(result),
        "muscles": result,
        "balance_groups": {
            "push": PUSH_MEMBERS,
            "pull": PULL_MEMBERS,
            "upper": UPPER_MEMBERS,
            "lower": LOWER_MEMBERS,
            "anterior": ANTERIOR_MEMBERS,
            "posterior": POSTERIOR_MEMBERS,
        },
        "bridge_defaults": BRIDGE_DEFAULT_TONNAGE,
    }
