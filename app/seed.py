"""
Import source files as single sources of truth.
- Exercise_Muscle_Matrix_v2.csv → exercises, muscles, activation_matrix_v2
- Role_Weighted_Matrix_v2.csv → role_weighted_matrix_v2
- V3_Phase_Model_Outputs.xlsx → phase_matrix_v3
"""
import csv
import os
from sqlalchemy.orm import Session
from app.models import (
    Exercise, Muscle, ActivationMatrixV2, RoleWeightedMatrixV2, PhaseMatrixV3,
    BottleneckMatrixV4, StabilizationMatrixV5, CompositeMuscleIndex, Preset
)

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "attached_assets")

ACTIVATION_CSV = os.path.join(ASSETS_DIR, "Exercise_Muscle_Matrix_v2_1772329150478.csv")
ROLE_WEIGHTED_CSV = os.path.join(ASSETS_DIR, "Role_Weighted_Matrix_v2_1772329858110.csv")
PHASE_V3_XLSX = os.path.join(ASSETS_DIR, "V3_Phase_Model_Outputs_1772330146444.xlsx")
BOTTLENECK_CSV = os.path.join(ASSETS_DIR, "V4_Bottleneck_Coefficient_Matrix_1772330621400.csv")
V5_DYNAMIC_CSV = os.path.join(ASSETS_DIR, "V5_Dynamic_Matrix_1772330962718.csv")
V5_STABILITY_CSV = os.path.join(ASSETS_DIR, "V5_Stability_Matrix_1772330962718.csv")
COMPOSITE_MUSCLE_CSV = os.path.join(ASSETS_DIR, "Composite_Muscle_Profile_Index_1772331293343.csv")


def _get_muscle_map(db: Session):
    return {m.name: m.id for m in db.query(Muscle).all()}


def _get_exercise_map(db: Session):
    return {e.name: e.id for e in db.query(Exercise).all()}


def seed_from_csv(db: Session) -> bool:
    if db.query(Exercise).count() > 0:
        _seed_role_weighted(db)
        _seed_phase_v3(db)
        _seed_bottleneck_v4(db)
        _seed_stabilization_v5(db)
        _seed_composite_muscle(db)
        _seed_presets(db)
        return False

    with open(ACTIVATION_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

        muscle_names = [h.strip() for h in header[1:]]
        muscle_objs = {}
        for name in muscle_names:
            m = Muscle(name=name)
            db.add(m)
            db.flush()
            muscle_objs[name] = m

        for row in reader:
            exercise_name = row[0].strip()
            if not exercise_name:
                continue
            ex = Exercise(name=exercise_name)
            db.add(ex)
            db.flush()

            for i, muscle_name in enumerate(muscle_names):
                val = int(row[i + 1].strip())
                db.add(ActivationMatrixV2(
                    exercise_id=ex.id,
                    muscle_id=muscle_objs[muscle_name].id,
                    activation_value=val,
                ))

    db.commit()
    _seed_role_weighted(db)
    _seed_phase_v3(db)
    _seed_bottleneck_v4(db)
    _seed_stabilization_v5(db)
    _seed_composite_muscle(db)
    _seed_presets(db)
    return True


def _seed_role_weighted(db: Session):
    if db.query(RoleWeightedMatrixV2).count() > 0:
        return
    if not os.path.exists(ROLE_WEIGHTED_CSV):
        return

    muscle_map = _get_muscle_map(db)
    exercise_map = _get_exercise_map(db)

    with open(ROLE_WEIGHTED_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        muscle_names = [h.strip() for h in header[1:]]

        for row in reader:
            exercise_name = row[0].strip()
            if not exercise_name:
                continue
            ex_id = exercise_map.get(exercise_name)
            if ex_id is None:
                continue

            for i, muscle_name in enumerate(muscle_names):
                mu_id = muscle_map.get(muscle_name)
                if mu_id is None:
                    continue
                val = float(row[i + 1].strip())
                db.add(RoleWeightedMatrixV2(
                    exercise_id=ex_id,
                    muscle_id=mu_id,
                    role_weight=val,
                ))

    db.commit()


def _seed_phase_v3(db: Session):
    if db.query(PhaseMatrixV3).count() > 0:
        return
    if not os.path.exists(PHASE_V3_XLSX):
        return

    import openpyxl
    muscle_map = _get_muscle_map(db)
    exercise_map = _get_exercise_map(db)

    wb = openpyxl.load_workbook(PHASE_V3_XLSX, data_only=True)

    sheet_phase_map = {
        "Initiation": "initiation",
        "Midrange": "midrange",
        "Lockout": "lockout",
    }

    for sheet_name, phase_key in sheet_phase_map.items():
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        header = rows[0]
        muscle_names = [str(h).strip() for h in header[1:] if h is not None]

        for row in rows[1:]:
            exercise_name = row[0]
            if not exercise_name:
                continue
            exercise_name = str(exercise_name).strip()
            ex_id = exercise_map.get(exercise_name)
            if ex_id is None:
                continue

            for i, muscle_name in enumerate(muscle_names):
                mu_id = muscle_map.get(muscle_name)
                if mu_id is None:
                    continue
                val = row[i + 1]
                if val is None:
                    val = 0.0
                db.add(PhaseMatrixV3(
                    exercise_id=ex_id,
                    muscle_id=mu_id,
                    phase=phase_key,
                    phase_value=float(val),
                ))

    wb.close()
    db.commit()


def _seed_bottleneck_v4(db: Session):
    if db.query(BottleneckMatrixV4).count() > 0:
        return
    if not os.path.exists(BOTTLENECK_CSV):
        return

    muscle_map = _get_muscle_map(db)
    exercise_map = _get_exercise_map(db)

    with open(BOTTLENECK_CSV, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        muscle_names = [h.strip() for h in header[1:]]

        for row in reader:
            exercise_name = row[0].strip()
            if not exercise_name:
                continue
            ex_id = exercise_map.get(exercise_name)
            if ex_id is None:
                continue

            for i, muscle_name in enumerate(muscle_names):
                mu_id = muscle_map.get(muscle_name)
                if mu_id is None:
                    continue
                val = float(row[i + 1].strip())
                db.add(BottleneckMatrixV4(
                    exercise_id=ex_id,
                    muscle_id=mu_id,
                    bottleneck_coeff=val,
                ))

    db.commit()


def _seed_stabilization_v5(db: Session):
    if db.query(StabilizationMatrixV5).count() > 0:
        return

    muscle_map = _get_muscle_map(db)
    exercise_map = _get_exercise_map(db)

    csv_component_map = {
        V5_DYNAMIC_CSV: "dynamic",
        V5_STABILITY_CSV: "stability",
    }

    for csv_path, component_key in csv_component_map.items():
        if not os.path.exists(csv_path):
            continue

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            muscle_names = [h.strip() for h in header[1:]]

            for row in reader:
                exercise_name = row[0].strip()
                if not exercise_name:
                    continue
                ex_id = exercise_map.get(exercise_name)
                if ex_id is None:
                    continue

                for i, muscle_name in enumerate(muscle_names):
                    mu_id = muscle_map.get(muscle_name)
                    if mu_id is None:
                        continue
                    val = float(row[i + 1].strip())
                    db.add(StabilizationMatrixV5(
                        exercise_id=ex_id,
                        muscle_id=mu_id,
                        component=component_key,
                        value=val,
                    ))

    db.commit()


def _seed_composite_muscle(db: Session):
    if db.query(CompositeMuscleIndex).count() > 0:
        return
    if not os.path.exists(COMPOSITE_MUSCLE_CSV):
        return

    import json
    muscle_map = _get_muscle_map(db)

    with open(COMPOSITE_MUSCLE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            muscle_name = row["Muscle"].strip()
            mu_id = muscle_map.get(muscle_name)
            if mu_id is None:
                continue
            score = float(row["Composite_Index_0to100"])
            payload = {k: _auto_type(v) for k, v in row.items()
                       if k not in ("Muscle", "Composite_Index_0to100")}
            db.add(CompositeMuscleIndex(
                muscle_id=mu_id,
                composite_score=score,
                payload=payload,
            ))

    db.commit()


def _auto_type(v):
    v = v.strip()
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


PRESET_DATA = {
    "hypertrophy": {
        "Exposure": 0.35,
        "Hierarchy": 0.25,
        "Bottleneck": 0.10,
        "Stability": 0.10,
        "Phase": 0.20,
    },
    "strength": {
        "Exposure": 0.20,
        "Hierarchy": 0.30,
        "Bottleneck": 0.30,
        "Stability": 0.10,
        "Phase": 0.10,
    },
    "injury": {
        "Exposure": 0.15,
        "Hierarchy": 0.15,
        "Bottleneck": 0.30,
        "Stability": 0.30,
        "Phase": 0.10,
    },
}


def _seed_presets(db: Session):
    if db.query(Preset).count() > 0:
        return
    for name, weights in PRESET_DATA.items():
        db.add(Preset(name=name, weights=weights))
    db.commit()
