from collections import defaultdict
from sqlalchemy.orm import Session
from app.models import Muscle

DELTOIDS_NAME = "Deltoids"
TRAPS_NAME = "Traps"
DELTOID_CHILDREN = ["Front/Anterior Delt", "Side/Lateral Delt", "Rear/Posterior Delt"]
TRAP_CHILDREN = ["Upper Traps", "Mid Traps", "Lower Traps"]


def build_derived_groups(db: Session):
    muscles = db.query(Muscle).all()
    name_to_id = {m.name: m.id for m in muscles}

    groups = {}
    deltoids_id = name_to_id.get(DELTOIDS_NAME)
    traps_id = name_to_id.get(TRAPS_NAME)

    if deltoids_id:
        groups[deltoids_id] = [name_to_id[n] for n in DELTOID_CHILDREN if n in name_to_id]
    if traps_id:
        groups[traps_id] = [name_to_id[n] for n in TRAP_CHILDREN if n in name_to_id]

    return groups


def apply_derived_rollup(stim_dict, derived_groups):
    for group_id, child_ids in derived_groups.items():
        stim_dict[group_id] = sum(stim_dict.get(cid, 0) for cid in child_ids)


def derived_group_ids(derived_groups):
    return set(derived_groups.keys())


def sum_vec_leaf_only(vec, derived_groups, mid_index):
    exclude = set()
    for gid in derived_groups:
        if gid in mid_index:
            exclude.add(mid_index[gid])
    return sum(v for i, v in enumerate(vec) if i not in exclude)
