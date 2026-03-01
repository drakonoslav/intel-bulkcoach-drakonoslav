"""
Import Exercise_Muscle_Matrix_v2.csv as the single source of truth.
Populates: exercises (92), muscles (26), activation_matrix_v2 (2392).
Activation values are integers 0–5 as provided — no normalization.
"""
import csv
import os
from sqlalchemy.orm import Session
from app.models import Exercise, Muscle, ActivationMatrixV2

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "attached_assets",
    "Exercise_Muscle_Matrix_v2_1772329150478.csv",
)


def seed_from_csv(db: Session) -> bool:
    if db.query(Exercise).count() > 0:
        return False

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
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
    return True
