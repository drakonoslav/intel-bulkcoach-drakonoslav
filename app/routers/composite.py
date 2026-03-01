from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import CompositeMuscleIndex, Muscle, Preset

router = APIRouter(prefix="/composite", tags=["composite"])


def _normalize(values):
    mn = min(values)
    mx = max(values)
    rng = mx - mn
    if rng == 0:
        return [0.0] * len(values)
    return [(v - mn) / rng for v in values]


@router.get("/muscles", summary="Composite muscle profile index (26 muscles)")
def get_composite_muscles(
    preset: Optional[str] = Query(None, description="Preset: hypertrophy, strength, or injury"),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(CompositeMuscleIndex, Muscle.name)
        .join(Muscle, Muscle.id == CompositeMuscleIndex.muscle_id)
        .order_by(CompositeMuscleIndex.composite_score.desc())
        .all()
    )

    if not preset:
        return [
            {
                "muscle": name,
                "composite_score": row.composite_score,
                "payload": row.payload,
            }
            for row, name in rows
        ]

    preset = preset.strip().lower()
    preset_row = db.query(Preset).filter(Preset.name == preset).first()
    if not preset_row:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}")

    w = preset_row.weights
    wE = w.get("Exposure", 0)
    wH = w.get("Hierarchy", 0)
    wB = w.get("Bottleneck", 0)
    wS = w.get("Stability", 0)
    wP = w.get("Phase", 0)

    raw_exposure = [r.payload.get("V1_TotalExposure", 0) for r, _ in rows]
    raw_hierarchy = [r.payload.get("V2_RoleWeightedExposure", 0) for r, _ in rows]
    raw_bottleneck = [r.payload.get("Total_Bottleneck_Pressure", 0) for r, _ in rows]
    raw_stability = [r.payload.get("Stabilization_Burden_Total", 0) for r, _ in rows]
    raw_phase = [abs(r.payload.get("V3_PhaseSkew_Index", 0)) for r, _ in rows]

    n_exp = _normalize(raw_exposure)
    n_hier = _normalize(raw_hierarchy)
    n_bot = _normalize(raw_bottleneck)
    n_stab = _normalize(raw_stability)
    n_phase = _normalize(raw_phase)

    results = []
    for i, (row, name) in enumerate(rows):
        ps = 100 * (
            n_exp[i] * wE +
            n_hier[i] * wH +
            n_bot[i] * wB +
            n_stab[i] * wS +
            n_phase[i] * wP
        )
        results.append({
            "muscle": name,
            "composite_score": row.composite_score,
            "preset_score": round(ps, 6),
            "payload": row.payload,
        })

    results.sort(key=lambda x: x["preset_score"], reverse=True)

    for rank, r in enumerate(results, 1):
        r["preset_rank"] = rank

    return results
