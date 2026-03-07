import math
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import (
    LiftSet, Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
    BottleneckMatrixV4, ExerciseTag,
    GameBridgeSet,
)
from app.hierarchy import build_derived_groups, apply_derived_rollup

MUSCLE_SCHEMA_VERSION = 27
FRESHNESS_K = 1000.0
DECAY_LOOKBACK_DAYS = 30
ROLLING_WINDOW_DAYS = 7
READINESS_THRESHOLD = 0.30
COMPOUND_SLOTS = {"hinge", "squat", "push", "pull"}
COMPOUND_ACTIVATION_MIN = 3
ISOLATION_ROLE_WEIGHT_MIN = 0.60

BRIDGE_DEFAULT_TONNAGE = {"compound": 500.0, "isolation": 200.0}

W_DEFICIT = 0.35
W_FRESHNESS = 0.25
W_RECENCY = 0.20
W_MODE = 0.20

HANDS_GRIP_NAME = "Hands/Grip"
FOREARMS_NAME = "Forearms"
HANDS_GRIP_SCALE = 0.85

DEFAULT_TAU = 3.5
TAU_TABLE = {
    "Quads": 4.0, "Hamstrings": 4.0, "Glutes": 4.0, "Lower Back": 4.0,
    "Pectorals": 3.5, "Lats": 3.5, "Adductors": 3.5, "Abductors": 3.5,
    "Upper Back": 3.0, "Middle Back": 3.0,
    "Deltoids": 3.0, "Front/Anterior Delt": 3.0, "Rear/Posterior Delt": 3.0, "Side/Lateral Delt": 3.0,
    "Traps": 3.0, "Upper Traps": 3.0, "Mid Traps": 3.0, "Lower Traps": 3.0,
    "Triceps": 2.5, "Biceps": 2.5, "Forearms": 2.5, "Hands/Grip": 2.5,
    "Abs": 2.5, "Obliques": 2.5, "Calves": 2.5, "Shins": 2.5, "Neck": 2.5,
}

PUSH_MEMBERS = [
    "Pectorals", "Front/Anterior Delt", "Side/Lateral Delt", "Triceps",
    "Quads", "Calves", "Shins",
]
PULL_MEMBERS = [
    "Lats", "Upper Back", "Middle Back", "Rear/Posterior Delt", "Biceps",
    "Forearms", "Hands/Grip", "Upper Traps", "Mid Traps", "Lower Traps",
    "Hamstrings", "Lower Back",
]
UPPER_MEMBERS = [
    "Pectorals", "Lats", "Upper Back", "Middle Back",
    "Front/Anterior Delt", "Rear/Posterior Delt", "Side/Lateral Delt",
    "Upper Traps", "Mid Traps", "Lower Traps",
    "Triceps", "Biceps", "Forearms", "Hands/Grip", "Neck",
]
LOWER_MEMBERS = [
    "Glutes", "Quads", "Hamstrings", "Calves", "Shins",
    "Adductors", "Abductors",
]
ANTERIOR_MEMBERS = ["Pectorals", "Quads", "Front/Anterior Delt", "Abs"]
POSTERIOR_MEMBERS = [
    "Hamstrings", "Glutes", "Lower Back", "Middle Back", "Upper Back",
    "Rear/Posterior Delt", "Lats",
]


def _percentile_ranks(values):
    n = len(values)
    if n == 0:
        return []
    sorted_vals = sorted(values)
    result = []
    for v in values:
        count_below = sum(1 for sv in sorted_vals if sv < v)
        count_equal = sum(1 for sv in sorted_vals if sv == v)
        pr = (count_below + 0.5 * count_equal) / n
        result.append(pr * 100)
    return result


def _normalize_01(values):
    mn = min(values)
    mx = max(values)
    rng = mx - mn
    if rng == 0:
        return [0.0] * len(values)
    return [(v - mn) / rng for v in values]


def compute_blended_muscle_state(query_date: date, db: Session):
    muscles = db.query(Muscle).order_by(Muscle.id).all()
    muscle_map = {m.id: m.name for m in muscles}
    muscle_ids = [m.id for m in muscles]
    name_to_id = {m.name: m.id for m in muscles}

    forearm_id = name_to_id.get(FOREARMS_NAME)
    hands_grip_id = name_to_id.get(HANDS_GRIP_NAME)

    derived_groups = build_derived_groups(db)

    tau_by_id = {}
    for mid in muscle_ids:
        tau_by_id[mid] = TAU_TABLE.get(muscle_map[mid], DEFAULT_TAU)

    decay_from = query_date - timedelta(days=DECAY_LOOKBACK_DAYS - 1)
    window_from = query_date - timedelta(days=ROLLING_WINDOW_DAYS - 1)

    all_sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= decay_from,
        LiftSet.performed_at <= query_date,
    ).all()

    all_ex_ids = list({s.exercise_id for s in all_sets})
    act_lookup = {}
    rw_lookup = {}
    if all_ex_ids:
        for r in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id.in_(all_ex_ids)).all():
            act_lookup[(r.exercise_id, r.muscle_id)] = r.activation_value
        for r in db.query(RoleWeightedMatrixV2).filter(RoleWeightedMatrixV2.exercise_id.in_(all_ex_ids)).all():
            rw_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight

    canonical_dose_by_day = defaultdict(lambda: defaultdict(float))
    canonical_direct_by_day = defaultdict(lambda: defaultdict(float))
    for s in all_sets:
        for mid in muscle_ids:
            av = act_lookup.get((s.exercise_id, mid), 0)
            rw = rw_lookup.get((s.exercise_id, mid), 0.0)
            canonical_dose_by_day[s.performed_at][mid] += s.tonnage * (av / 5.0)
            canonical_direct_by_day[s.performed_at][mid] += s.tonnage * rw

    bridge_sets = db.query(GameBridgeSet).filter(
        GameBridgeSet.performed_at >= decay_from,
        GameBridgeSet.performed_at <= query_date,
    ).all()

    bridge_dose_by_day = defaultdict(lambda: defaultdict(float))
    for bs in bridge_sets:
        bridge_dose_by_day[bs.performed_at][bs.muscle_id] += bs.dose_estimate

    has_canonical = defaultdict(bool)
    has_bridge = defaultdict(bool)

    fatigue_total = defaultdict(float)
    load_7d = defaultdict(float)
    last_hit = {}

    for day_offset in range(DECAY_LOOKBACK_DAYS):
        d = decay_from + timedelta(days=day_offset)
        days_ago = (query_date - d).days
        in_7d = d >= window_from

        for mid in muscle_ids:
            c_dose = canonical_dose_by_day[d][mid]
            b_dose = bridge_dose_by_day[d][mid]

            if c_dose > 0:
                has_canonical[mid] = True
            if b_dose > 0:
                has_bridge[mid] = True

            total_day = c_dose + b_dose
            if total_day > 0:
                tau = tau_by_id[mid]
                weight = math.exp(-days_ago / tau)
                fatigue_total[mid] += total_day * weight
                if mid not in last_hit or d > last_hit[mid]:
                    last_hit[mid] = d

            if in_7d:
                load_7d[mid] += c_dose + b_dose

    if hands_grip_id and forearm_id:
        if fatigue_total[hands_grip_id] == 0 and load_7d[hands_grip_id] == 0:
            fatigue_total[hands_grip_id] = fatigue_total[forearm_id] * HANDS_GRIP_SCALE
            load_7d[hands_grip_id] = load_7d[forearm_id] * HANDS_GRIP_SCALE
            if forearm_id in last_hit and hands_grip_id not in last_hit:
                last_hit[hands_grip_id] = last_hit[forearm_id]
                has_canonical[hands_grip_id] = has_canonical[forearm_id]
                has_bridge[hands_grip_id] = has_bridge[forearm_id]

    for group_id, child_ids in derived_groups.items():
        fatigue_total[group_id] = sum(fatigue_total[cid] for cid in child_ids)
        load_7d[group_id] = sum(load_7d[cid] for cid in child_ids)
        group_last = None
        for cid in child_ids:
            if cid in last_hit:
                if group_last is None or last_hit[cid] > group_last:
                    group_last = last_hit[cid]
            if has_canonical[cid]:
                has_canonical[group_id] = True
            if has_bridge[cid]:
                has_bridge[group_id] = True
        if group_last:
            last_hit[group_id] = group_last

    freshness = {}
    for mid in muscle_ids:
        freshness[mid] = round(1.0 / (1.0 + fatigue_total[mid] / FRESHNESS_K), 4)

    days_since = {}
    for mid in muscle_ids:
        if mid in last_hit:
            days_since[mid] = (query_date - last_hit[mid]).days
        else:
            days_since[mid] = None

    underfed_scores, statuses = _compute_underfed_canonical(
        query_date, db, muscle_ids, muscle_map, derived_groups
    )

    compound_suit, isolation_suit = _compute_suitability(db, muscle_ids)

    max_load = max(load_7d[mid] for mid in muscle_ids) if muscle_ids else 0

    results = []
    for mid in muscle_ids:
        recency_norm = _recency_norm(days_since[mid])
        load_norm = (load_7d[mid] / max_load) if max_load > 0 else 0.0
        heatmap = max(0.0, min(1.0,
            0.50 * (1.0 - freshness[mid]) +
            0.30 * load_norm +
            0.20 * (1.0 - recency_norm)
        ))

        priority = _compute_queue_priority(
            freshness[mid], underfed_scores[mid],
            recency_norm, compound_suit.get(mid, 0.0)
        )

        hc = has_canonical[mid]
        hb = has_bridge[mid]
        if hc and hb:
            blend = "blended"
        elif hc:
            blend = "canonical_only"
        elif hb:
            blend = "bridge_only"
        else:
            blend = "no_data"

        results.append({
            "muscle_id": mid,
            "muscle": muscle_map[mid],
            "freshness": freshness[mid],
            "fatigue": round(fatigue_total[mid], 2),
            "load_7d": round(load_7d[mid], 2),
            "last_hit": str(last_hit[mid]) if mid in last_hit else None,
            "days_since_hit": days_since[mid],
            "underfed_score": underfed_scores[mid],
            "status": statuses[mid],
            "tau_days": tau_by_id[mid],
            "heatmap_intensity": round(heatmap, 4),
            "queue_priority": round(priority, 4),
            "compound_suitability": round(compound_suit.get(mid, 0.0), 4),
            "isolation_suitability": round(isolation_suit.get(mid, 0.0), 4),
            "data_blend": blend,
        })

    return results, muscle_ids, muscle_map, name_to_id, load_7d, freshness, days_since, underfed_scores, statuses, compound_suit, isolation_suit


def _recency_norm(days_since_hit):
    if days_since_hit is None:
        return 1.0
    return min(days_since_hit, 7) / 7.0


def _compute_queue_priority(fresh, underfed_score, recency_norm, mode_suit):
    if fresh < READINESS_THRESHOLD:
        return 0.0
    deficit_norm = underfed_score / 100.0
    return (
        W_DEFICIT * deficit_norm +
        W_FRESHNESS * fresh +
        W_RECENCY * recency_norm +
        W_MODE * mode_suit
    )


def _compute_underfed_canonical(query_date, db, muscle_ids, muscle_map, derived_groups):
    cal = query_date.isocalendar()
    jan4 = date(cal[0], 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = start_of_w1 + timedelta(weeks=cal[1] - 1)
    sunday = monday + timedelta(days=6)

    sets = db.query(LiftSet).filter(
        LiftSet.performed_at >= monday,
        LiftSet.performed_at <= sunday,
    ).all()

    exercise_ids = list({s.exercise_id for s in sets})
    role_lookup = {}
    act_lookup = {}
    bn_lookup = {}
    stab_lookup = {}

    if exercise_ids:
        for r in db.query(RoleWeightedMatrixV2).filter(RoleWeightedMatrixV2.exercise_id.in_(exercise_ids)).all():
            role_lookup[(r.exercise_id, r.muscle_id)] = r.role_weight
        for a in db.query(ActivationMatrixV2).filter(ActivationMatrixV2.exercise_id.in_(exercise_ids)).all():
            act_lookup[(a.exercise_id, a.muscle_id)] = a.activation_value
        from app.models import BottleneckMatrixV4, StabilizationMatrixV5
        for b in db.query(BottleneckMatrixV4).filter(BottleneckMatrixV4.exercise_id.in_(exercise_ids)).all():
            bn_lookup[(b.exercise_id, b.muscle_id)] = b.bottleneck_coeff
        for s in db.query(StabilizationMatrixV5).filter(
            StabilizationMatrixV5.exercise_id.in_(exercise_ids),
            StabilizationMatrixV5.component == "stability",
        ).all():
            stab_lookup[(s.exercise_id, s.muscle_id)] = s.value

    direct_dose = {mid: 0.0 for mid in muscle_ids}
    total_dose = {mid: 0.0 for mid in muscle_ids}
    bn_pressure = {mid: 0.0 for mid in muscle_ids}
    stab_load = {mid: 0.0 for mid in muscle_ids}

    for s in sets:
        for mid in muscle_ids:
            rw = role_lookup.get((s.exercise_id, mid), 0.0)
            act = act_lookup.get((s.exercise_id, mid), 0)
            bn = bn_lookup.get((s.exercise_id, mid), 0.0)
            st = stab_lookup.get((s.exercise_id, mid), 0.0)
            direct_dose[mid] += s.tonnage * rw
            total_dose[mid] += s.tonnage * (act / 5.0)
            bn_pressure[mid] += s.tonnage * bn
            stab_load[mid] += s.tonnage * st

    apply_derived_rollup(direct_dose, derived_groups)
    apply_derived_rollup(total_dose, derived_groups)
    apply_derived_rollup(bn_pressure, derived_groups)
    apply_derived_rollup(stab_load, derived_groups)

    dd_values = [direct_dose[mid] for mid in muscle_ids]
    max_dd = max(dd_values) if dd_values else 0
    underfed_raw = [max(0, max_dd - dd) for dd in dd_values]
    underfed_scores_list = _percentile_ranks(underfed_raw)

    td_values = [total_dose[mid] for mid in muscle_ids]
    bn_values = [bn_pressure[mid] for mid in muscle_ids]
    stab_values = [stab_load[mid] for mid in muscle_ids]
    n_td = _normalize_01(td_values)
    n_bn = _normalize_01(bn_values)
    n_stab = _normalize_01(stab_values)

    overtaxed_scores_list = [
        100 * (0.45 * n_bn[i] + 0.35 * n_stab[i] + 0.20 * n_td[i])
        for i in range(len(muscle_ids))
    ]

    underfed_scores = {}
    statuses = {}
    for i, mid in enumerate(muscle_ids):
        us = round(underfed_scores_list[i], 2)
        os_ = overtaxed_scores_list[i]
        underfed_scores[mid] = us
        if us >= 70 and os_ < 70:
            statuses[mid] = "underfed"
        elif os_ >= 70:
            statuses[mid] = "overtaxed"
        else:
            statuses[mid] = "balanced"

    return underfed_scores, statuses


def _compute_suitability(db, muscle_ids):
    tags = db.query(ExerciseTag).filter(ExerciseTag.slot.in_(list(COMPOUND_SLOTS))).all()
    compound_ex_ids = list({t.exercise_id for t in tags})

    slot_by_ex = defaultdict(set)
    for t in tags:
        slot_by_ex[t.exercise_id].add(t.slot)

    act_rows = []
    if compound_ex_ids:
        act_rows = db.query(ActivationMatrixV2).filter(
            ActivationMatrixV2.exercise_id.in_(compound_ex_ids)
        ).all()

    compound_count = defaultdict(int)
    for r in act_rows:
        if r.activation_value >= COMPOUND_ACTIVATION_MIN:
            compound_count[r.muscle_id] += 1

    max_compound = max(compound_count.values()) if compound_count else 0
    compound_suit = {}
    for mid in muscle_ids:
        compound_suit[mid] = (compound_count.get(mid, 0) / max_compound) if max_compound > 0 else 0.0

    all_act = db.query(ActivationMatrixV2).all()
    all_rw = db.query(RoleWeightedMatrixV2).all()
    all_bn = db.query(BottleneckMatrixV4).all()

    rw_by_ex_muscle = {}
    for r in all_rw:
        rw_by_ex_muscle[(r.exercise_id, r.muscle_id)] = r.role_weight

    bn_sum_by_ex = defaultdict(float)
    for b in all_bn:
        bn_sum_by_ex[b.exercise_id] += b.bottleneck_coeff

    all_ex_ids = list(bn_sum_by_ex.keys())
    if all_ex_ids:
        bn_sums = sorted(bn_sum_by_ex.values())
        median_bn = bn_sums[len(bn_sums) // 2] if bn_sums else 0
    else:
        median_bn = 0

    isolation_count = defaultdict(int)
    exercise_ids_with_rw = set()
    for (eid, mid), rw in rw_by_ex_muscle.items():
        exercise_ids_with_rw.add(eid)

    for eid in exercise_ids_with_rw:
        if bn_sum_by_ex.get(eid, 999) >= median_bn:
            continue
        for mid in muscle_ids:
            rw = rw_by_ex_muscle.get((eid, mid), 0.0)
            if rw >= ISOLATION_ROLE_WEIGHT_MIN:
                isolation_count[mid] += 1

    max_iso = max(isolation_count.values()) if isolation_count else 0
    isolation_suit = {}
    for mid in muscle_ids:
        isolation_suit[mid] = (isolation_count.get(mid, 0) / max_iso) if max_iso > 0 else 0.0

    return compound_suit, isolation_suit


def compute_recommended_slots(db, muscle_ids, muscle_map):
    tags = db.query(ExerciseTag).all()
    slot_by_ex = defaultdict(set)
    for t in tags:
        slot_by_ex[t.exercise_id].add(t.slot)

    act_rows = db.query(ActivationMatrixV2).all()
    act_by_ex = defaultdict(dict)
    for r in act_rows:
        act_by_ex[r.exercise_id][r.muscle_id] = r.activation_value

    muscle_slots = defaultdict(set)
    for eid, slots in slot_by_ex.items():
        for mid in muscle_ids:
            if act_by_ex.get(eid, {}).get(mid, 0) >= COMPOUND_ACTIVATION_MIN:
                muscle_slots[mid].update(slots)

    return {mid: sorted(muscle_slots.get(mid, set())) for mid in muscle_ids}


def compute_balance_ratios(load_7d, name_to_id):
    def _ratio(members):
        return sum(load_7d.get(name_to_id.get(m, -1), 0.0) for m in members)

    eps = 1e-6
    push_sum = _ratio(PUSH_MEMBERS)
    pull_sum = _ratio(PULL_MEMBERS)
    upper_sum = _ratio(UPPER_MEMBERS)
    lower_sum = _ratio(LOWER_MEMBERS)
    ant_sum = _ratio(ANTERIOR_MEMBERS)
    post_sum = _ratio(POSTERIOR_MEMBERS)

    return {
        "push_pull_ratio": round(push_sum / max(pull_sum, eps), 4) if (push_sum + pull_sum) > 0 else None,
        "upper_lower_ratio": round(upper_sum / max(lower_sum, eps), 4) if (upper_sum + lower_sum) > 0 else None,
        "anterior_posterior_ratio": round(ant_sum / max(post_sum, eps), 4) if (ant_sum + post_sum) > 0 else None,
    }
