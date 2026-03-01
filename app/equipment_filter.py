from collections import defaultdict
from sqlalchemy.orm import Session
from app.models import ExerciseEquipment


def build_equipment_eligible(db: Session, available_tags: set):
    if not available_tags:
        return None

    rows = db.query(ExerciseEquipment).filter(ExerciseEquipment.required == 1).all()

    required_by_ex = defaultdict(set)
    for r in rows:
        required_by_ex[r.exercise_id].add(r.equipment_tag)

    eligible = set()
    all_eids_with_reqs = set(required_by_ex.keys())

    for eid, req_tags in required_by_ex.items():
        if req_tags.issubset(available_tags):
            eligible.add(eid)

    return eligible, all_eids_with_reqs


def filter_candidates_by_equipment(candidate_eids, eligible_set, all_eids_with_reqs):
    if eligible_set is None:
        return candidate_eids
    result = []
    for eid in candidate_eids:
        if eid not in all_eids_with_reqs:
            result.append(eid)
        elif eid in eligible_set:
            result.append(eid)
    return result
