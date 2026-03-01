"""
Seed data for the biomechanical modeling engine.
Populates exercises (92), muscles (26), and all matrix tables.
"""
import math
from sqlalchemy.orm import Session
from app.models import (
    Exercise, Muscle,
    ActivationMatrixV2, RoleWeightedMatrixV2,
    PhaseMatrixV3, BottleneckMatrixV4,
    StabilizationMatrixV5, CompositeIndex,
)

MUSCLES = [
    ("rectus_femoris",        "quadriceps",     "lower"),
    ("vastus_lateralis",      "quadriceps",     "lower"),
    ("vastus_medialis",       "quadriceps",     "lower"),
    ("vastus_intermedius",    "quadriceps",     "lower"),
    ("biceps_femoris",        "hamstrings",     "lower"),
    ("semitendinosus",        "hamstrings",     "lower"),
    ("semimembranosus",       "hamstrings",     "lower"),
    ("gluteus_maximus",       "glutes",         "lower"),
    ("gluteus_medius",        "glutes",         "lower"),
    ("adductor_magnus",       "adductors",      "lower"),
    ("gastrocnemius",         "calves",         "lower"),
    ("soleus",                "calves",         "lower"),
    ("tibialis_anterior",     "calves",         "lower"),
    ("pectoralis_major_sternal",   "chest",     "upper"),
    ("pectoralis_major_clavicular","chest",     "upper"),
    ("anterior_deltoid",      "deltoids",       "upper"),
    ("lateral_deltoid",       "deltoids",       "upper"),
    ("posterior_deltoid",     "deltoids",       "upper"),
    ("trapezius_upper",       "trapezius",      "upper"),
    ("trapezius_mid_lower",   "trapezius",      "upper"),
    ("latissimus_dorsi",      "back",           "upper"),
    ("biceps_brachii",        "arms",           "upper"),
    ("triceps_brachii",       "arms",           "upper"),
    ("erector_spinae",        "trunk",          "trunk"),
    ("rectus_abdominis",      "trunk",          "trunk"),
    ("external_obliques",     "trunk",          "trunk"),
]

EXERCISES = [
    ("back_squat",                "compound", "squat",          "barbell",      1),
    ("front_squat",               "compound", "squat",          "barbell",      1),
    ("overhead_squat",            "compound", "squat",          "barbell",      1),
    ("zercher_squat",             "compound", "squat",          "barbell",      1),
    ("safety_bar_squat",          "compound", "squat",          "barbell",      1),
    ("goblet_squat",              "compound", "squat",          "dumbbell",     1),
    ("bulgarian_split_squat",     "compound", "squat",          "dumbbell",     0),
    ("pistol_squat",              "compound", "squat",          "bodyweight",   0),
    ("hack_squat",                "compound", "squat",          "machine",      1),
    ("leg_press",                 "compound", "squat",          "machine",      1),
    ("conventional_deadlift",     "compound", "hinge",          "barbell",      1),
    ("sumo_deadlift",             "compound", "hinge",          "barbell",      1),
    ("romanian_deadlift",         "compound", "hinge",          "barbell",      1),
    ("stiff_leg_deadlift",        "compound", "hinge",          "barbell",      1),
    ("trap_bar_deadlift",         "compound", "hinge",          "barbell",      1),
    ("deficit_deadlift",          "compound", "hinge",          "barbell",      1),
    ("rack_pull",                 "compound", "hinge",          "barbell",      1),
    ("good_morning",              "compound", "hinge",          "barbell",      1),
    ("hip_thrust",                "compound", "hinge",          "barbell",      1),
    ("cable_pull_through",        "compound", "hinge",          "cable",        1),
    ("kettlebell_swing",          "compound", "hinge",          "kettlebell",   1),
    ("barbell_bench_press",       "compound", "horizontal_push","barbell",      1),
    ("close_grip_bench_press",    "compound", "horizontal_push","barbell",      1),
    ("incline_bench_press",       "compound", "horizontal_push","barbell",      1),
    ("decline_bench_press",       "compound", "horizontal_push","barbell",      1),
    ("dumbbell_bench_press",      "compound", "horizontal_push","dumbbell",     1),
    ("dumbbell_incline_press",    "compound", "horizontal_push","dumbbell",     1),
    ("dumbbell_fly",              "isolation","horizontal_push","dumbbell",     1),
    ("cable_fly",                 "isolation","horizontal_push","cable",        1),
    ("push_up",                   "compound", "horizontal_push","bodyweight",   1),
    ("dip",                       "compound", "horizontal_push","bodyweight",   1),
    ("machine_chest_press",       "compound", "horizontal_push","machine",      1),
    ("overhead_press",            "compound", "vertical_push",  "barbell",      1),
    ("push_press",                "compound", "vertical_push",  "barbell",      1),
    ("dumbbell_shoulder_press",   "compound", "vertical_push",  "dumbbell",     1),
    ("arnold_press",              "compound", "vertical_push",  "dumbbell",     1),
    ("landmine_press",            "compound", "vertical_push",  "barbell",      1),
    ("lateral_raise",             "isolation","vertical_push",  "dumbbell",     1),
    ("front_raise",               "isolation","vertical_push",  "dumbbell",     1),
    ("face_pull",                 "isolation","horizontal_pull","cable",        1),
    ("barbell_row",               "compound", "horizontal_pull","barbell",      1),
    ("pendlay_row",               "compound", "horizontal_pull","barbell",      1),
    ("dumbbell_row",              "compound", "horizontal_pull","dumbbell",     0),
    ("t_bar_row",                 "compound", "horizontal_pull","barbell",      1),
    ("cable_row",                 "compound", "horizontal_pull","cable",        1),
    ("chest_supported_row",       "compound", "horizontal_pull","dumbbell",     1),
    ("inverted_row",              "compound", "horizontal_pull","bodyweight",   1),
    ("machine_row",               "compound", "horizontal_pull","machine",      1),
    ("pull_up",                   "compound", "vertical_pull",  "bodyweight",   1),
    ("chin_up",                   "compound", "vertical_pull",  "bodyweight",   1),
    ("lat_pulldown",              "compound", "vertical_pull",  "cable",        1),
    ("close_grip_pulldown",       "compound", "vertical_pull",  "cable",        1),
    ("straight_arm_pulldown",     "isolation","vertical_pull",  "cable",        1),
    ("barbell_curl",              "isolation","elbow_flexion",  "barbell",      1),
    ("dumbbell_curl",             "isolation","elbow_flexion",  "dumbbell",     1),
    ("hammer_curl",               "isolation","elbow_flexion",  "dumbbell",     1),
    ("preacher_curl",             "isolation","elbow_flexion",  "barbell",      1),
    ("concentration_curl",        "isolation","elbow_flexion",  "dumbbell",     0),
    ("cable_curl",                "isolation","elbow_flexion",  "cable",        1),
    ("tricep_pushdown",           "isolation","elbow_extension","cable",        1),
    ("overhead_tricep_extension", "isolation","elbow_extension","cable",        1),
    ("skull_crusher",             "isolation","elbow_extension","barbell",      1),
    ("dumbbell_kickback",         "isolation","elbow_extension","dumbbell",     0),
    ("leg_extension",             "isolation","knee_extension", "machine",      1),
    ("leg_curl_lying",            "isolation","knee_flexion",   "machine",      1),
    ("leg_curl_seated",           "isolation","knee_flexion",   "machine",      1),
    ("nordic_hamstring_curl",     "isolation","knee_flexion",   "bodyweight",   1),
    ("glute_ham_raise",           "compound", "knee_flexion",   "bodyweight",   1),
    ("calf_raise_standing",       "isolation","ankle_plantar",  "machine",      1),
    ("calf_raise_seated",         "isolation","ankle_plantar",  "machine",      1),
    ("tibialis_raise",            "isolation","ankle_dorsi",    "bodyweight",   1),
    ("hip_abduction_machine",     "isolation","hip_abduction",  "machine",      1),
    ("hip_adduction_machine",     "isolation","hip_adduction",  "machine",      1),
    ("cable_hip_abduction",       "isolation","hip_abduction",  "cable",        0),
    ("reverse_fly",               "isolation","horizontal_pull","dumbbell",     1),
    ("shrug",                     "isolation","scapular_elev",  "barbell",      1),
    ("upright_row",               "compound", "scapular_elev",  "barbell",      1),
    ("farmers_walk",              "compound", "loaded_carry",   "dumbbell",     1),
    ("suitcase_carry",            "compound", "loaded_carry",   "dumbbell",     0),
    ("plank",                     "isolation","anti_extension", "bodyweight",   1),
    ("ab_rollout",                "isolation","anti_extension", "bodyweight",   1),
    ("hanging_leg_raise",         "isolation","trunk_flexion",  "bodyweight",   1),
    ("cable_woodchop",            "isolation","trunk_rotation", "cable",        0),
    ("pallof_press",              "isolation","anti_rotation",  "cable",        0),
    ("back_extension",            "isolation","hinge",          "bodyweight",   1),
    ("reverse_hyper",             "isolation","hinge",          "machine",      1),
    ("belt_squat",                "compound", "squat",          "machine",      1),
    ("smith_machine_squat",       "compound", "squat",          "machine",      1),
    ("power_clean",               "compound", "olympic",        "barbell",      1),
    ("hang_clean",                "compound", "olympic",        "barbell",      1),
    ("snatch",                    "compound", "olympic",        "barbell",      1),
    ("push_jerk",                 "compound", "olympic",        "barbell",      1),
    ("box_jump",                  "compound", "plyometric",     "bodyweight",   1),
]

_M_IDX = {name: i for i, (name, _, _) in enumerate(MUSCLES)}
_E_IDX = {name: i for i, (name, *_) in enumerate(EXERCISES)}

_PATTERN_ACTIVATION = {
    "squat": {
        "rectus_femoris": 0.85, "vastus_lateralis": 0.90, "vastus_medialis": 0.88,
        "vastus_intermedius": 0.80, "gluteus_maximus": 0.75, "gluteus_medius": 0.40,
        "adductor_magnus": 0.55, "biceps_femoris": 0.25, "semitendinosus": 0.20,
        "semimembranosus": 0.20, "gastrocnemius": 0.20, "soleus": 0.15,
        "erector_spinae": 0.60, "rectus_abdominis": 0.35, "external_obliques": 0.30,
    },
    "hinge": {
        "gluteus_maximus": 0.90, "biceps_femoris": 0.80, "semitendinosus": 0.75,
        "semimembranosus": 0.75, "erector_spinae": 0.85, "adductor_magnus": 0.50,
        "rectus_femoris": 0.20, "vastus_lateralis": 0.15, "vastus_medialis": 0.15,
        "vastus_intermedius": 0.15, "gluteus_medius": 0.30, "gastrocnemius": 0.15,
        "latissimus_dorsi": 0.25, "trapezius_mid_lower": 0.30,
        "rectus_abdominis": 0.30, "external_obliques": 0.25,
    },
    "horizontal_push": {
        "pectoralis_major_sternal": 0.90, "pectoralis_major_clavicular": 0.60,
        "anterior_deltoid": 0.70, "triceps_brachii": 0.75, "lateral_deltoid": 0.15,
        "rectus_abdominis": 0.15, "erector_spinae": 0.10,
    },
    "vertical_push": {
        "anterior_deltoid": 0.85, "lateral_deltoid": 0.60, "triceps_brachii": 0.70,
        "pectoralis_major_clavicular": 0.40, "trapezius_upper": 0.45,
        "erector_spinae": 0.30, "rectus_abdominis": 0.25, "external_obliques": 0.20,
    },
    "horizontal_pull": {
        "latissimus_dorsi": 0.75, "trapezius_mid_lower": 0.80,
        "posterior_deltoid": 0.70, "biceps_brachii": 0.55,
        "erector_spinae": 0.40, "rectus_abdominis": 0.15,
    },
    "vertical_pull": {
        "latissimus_dorsi": 0.90, "biceps_brachii": 0.70,
        "trapezius_mid_lower": 0.50, "posterior_deltoid": 0.45,
        "pectoralis_major_sternal": 0.15, "rectus_abdominis": 0.25,
        "external_obliques": 0.20,
    },
    "elbow_flexion": {
        "biceps_brachii": 0.95, "anterior_deltoid": 0.10,
    },
    "elbow_extension": {
        "triceps_brachii": 0.95, "anterior_deltoid": 0.05,
    },
    "knee_extension": {
        "rectus_femoris": 0.90, "vastus_lateralis": 0.92, "vastus_medialis": 0.90,
        "vastus_intermedius": 0.85,
    },
    "knee_flexion": {
        "biceps_femoris": 0.90, "semitendinosus": 0.85, "semimembranosus": 0.85,
        "gastrocnemius": 0.30,
    },
    "ankle_plantar": {
        "gastrocnemius": 0.90, "soleus": 0.85,
    },
    "ankle_dorsi": {
        "tibialis_anterior": 0.95,
    },
    "hip_abduction": {
        "gluteus_medius": 0.90, "gluteus_maximus": 0.30,
    },
    "hip_adduction": {
        "adductor_magnus": 0.90, "rectus_femoris": 0.15,
    },
    "scapular_elev": {
        "trapezius_upper": 0.90, "lateral_deltoid": 0.30,
        "trapezius_mid_lower": 0.20,
    },
    "loaded_carry": {
        "erector_spinae": 0.70, "external_obliques": 0.65, "rectus_abdominis": 0.60,
        "trapezius_upper": 0.60, "gluteus_medius": 0.50, "gluteus_maximus": 0.40,
        "gastrocnemius": 0.30, "soleus": 0.30,
    },
    "anti_extension": {
        "rectus_abdominis": 0.90, "external_obliques": 0.70,
        "erector_spinae": 0.30,
    },
    "trunk_flexion": {
        "rectus_abdominis": 0.90, "external_obliques": 0.55,
    },
    "trunk_rotation": {
        "external_obliques": 0.90, "rectus_abdominis": 0.50,
        "erector_spinae": 0.30,
    },
    "anti_rotation": {
        "external_obliques": 0.85, "rectus_abdominis": 0.70,
        "erector_spinae": 0.35, "gluteus_medius": 0.25,
    },
    "olympic": {
        "rectus_femoris": 0.75, "vastus_lateralis": 0.80, "vastus_medialis": 0.75,
        "vastus_intermedius": 0.70, "gluteus_maximus": 0.85, "biceps_femoris": 0.55,
        "semitendinosus": 0.50, "semimembranosus": 0.50, "erector_spinae": 0.80,
        "trapezius_upper": 0.70, "trapezius_mid_lower": 0.55,
        "anterior_deltoid": 0.50, "lateral_deltoid": 0.35, "gastrocnemius": 0.45,
        "soleus": 0.40, "rectus_abdominis": 0.45, "external_obliques": 0.40,
        "latissimus_dorsi": 0.30,
    },
    "plyometric": {
        "rectus_femoris": 0.70, "vastus_lateralis": 0.75, "vastus_medialis": 0.70,
        "vastus_intermedius": 0.65, "gluteus_maximus": 0.80, "gastrocnemius": 0.60,
        "soleus": 0.55, "gluteus_medius": 0.35, "rectus_abdominis": 0.30,
    },
}

_EXERCISE_OVERRIDES = {
    "front_squat":       {"pectoralis_major_clavicular": 0.10, "anterior_deltoid": 0.30, "erector_spinae": 0.70, "rectus_abdominis": 0.45},
    "overhead_squat":    {"anterior_deltoid": 0.50, "lateral_deltoid": 0.40, "trapezius_upper": 0.55, "erector_spinae": 0.75, "rectus_abdominis": 0.50, "external_obliques": 0.45},
    "zercher_squat":     {"biceps_brachii": 0.40, "anterior_deltoid": 0.25, "erector_spinae": 0.70, "rectus_abdominis": 0.45},
    "goblet_squat":      {"anterior_deltoid": 0.25, "biceps_brachii": 0.20},
    "bulgarian_split_squat": {"gluteus_medius": 0.65, "gluteus_maximus": 0.80},
    "pistol_squat":      {"gluteus_medius": 0.70, "rectus_abdominis": 0.45},
    "sumo_deadlift":     {"adductor_magnus": 0.75, "gluteus_maximus": 0.85, "erector_spinae": 0.65},
    "romanian_deadlift": {"gluteus_maximus": 0.80, "biceps_femoris": 0.85, "semitendinosus": 0.80, "erector_spinae": 0.70},
    "stiff_leg_deadlift":{"biceps_femoris": 0.90, "semitendinosus": 0.85, "erector_spinae": 0.75},
    "hip_thrust":        {"gluteus_maximus": 0.95, "biceps_femoris": 0.40, "erector_spinae": 0.20, "rectus_femoris": 0.15},
    "incline_bench_press":    {"pectoralis_major_clavicular": 0.80, "pectoralis_major_sternal": 0.55, "anterior_deltoid": 0.75},
    "decline_bench_press":    {"pectoralis_major_sternal": 0.92, "pectoralis_major_clavicular": 0.35, "anterior_deltoid": 0.50},
    "close_grip_bench_press": {"triceps_brachii": 0.85, "pectoralis_major_sternal": 0.70, "anterior_deltoid": 0.55},
    "dumbbell_fly":      {"pectoralis_major_sternal": 0.85, "pectoralis_major_clavicular": 0.60, "anterior_deltoid": 0.30, "triceps_brachii": 0.10},
    "cable_fly":         {"pectoralis_major_sternal": 0.80, "pectoralis_major_clavicular": 0.55, "anterior_deltoid": 0.25, "triceps_brachii": 0.08},
    "dip":               {"pectoralis_major_sternal": 0.80, "triceps_brachii": 0.80, "anterior_deltoid": 0.60},
    "chin_up":           {"biceps_brachii": 0.80, "latissimus_dorsi": 0.85},
    "close_grip_pulldown":{"latissimus_dorsi": 0.85, "biceps_brachii": 0.75},
    "straight_arm_pulldown":{"latissimus_dorsi": 0.80, "biceps_brachii": 0.15, "triceps_brachii": 0.25},
    "pendlay_row":       {"erector_spinae": 0.55, "latissimus_dorsi": 0.80, "trapezius_mid_lower": 0.75},
    "face_pull":         {"posterior_deltoid": 0.85, "trapezius_mid_lower": 0.60, "lateral_deltoid": 0.30, "biceps_brachii": 0.20, "latissimus_dorsi": 0.10},
    "reverse_fly":       {"posterior_deltoid": 0.90, "trapezius_mid_lower": 0.55, "latissimus_dorsi": 0.15, "biceps_brachii": 0.10},
    "arnold_press":      {"anterior_deltoid": 0.80, "lateral_deltoid": 0.65, "triceps_brachii": 0.60, "pectoralis_major_clavicular": 0.35},
    "lateral_raise":     {"lateral_deltoid": 0.90, "anterior_deltoid": 0.20, "trapezius_upper": 0.30},
    "front_raise":       {"anterior_deltoid": 0.90, "pectoralis_major_clavicular": 0.30, "lateral_deltoid": 0.15},
    "hammer_curl":       {"biceps_brachii": 0.80, "anterior_deltoid": 0.08},
    "preacher_curl":     {"biceps_brachii": 0.92, "anterior_deltoid": 0.05},
    "glute_ham_raise":   {"biceps_femoris": 0.85, "semitendinosus": 0.80, "semimembranosus": 0.80, "gluteus_maximus": 0.50, "erector_spinae": 0.35},
    "nordic_hamstring_curl": {"biceps_femoris": 0.95, "semitendinosus": 0.90, "semimembranosus": 0.90, "gastrocnemius": 0.25},
    "calf_raise_seated": {"soleus": 0.92, "gastrocnemius": 0.30},
    "suitcase_carry":    {"external_obliques": 0.80, "gluteus_medius": 0.60},
    "power_clean":       {"trapezius_upper": 0.80, "anterior_deltoid": 0.55},
    "snatch":            {"trapezius_upper": 0.75, "lateral_deltoid": 0.50, "anterior_deltoid": 0.55},
}

ROLE_THRESHOLDS = {"prime_mover": 0.70, "synergist": 0.30, "stabilizer": 0.0}
ROLE_WEIGHTS = {"prime_mover": 1.0, "synergist": 0.6, "stabilizer": 0.25}

PHASE_MODIFIERS = {
    "squat":           {"initiation": {"gluteus_maximus": 1.2, "erector_spinae": 1.1}, "mid": {}, "lockout": {"vastus_medialis": 1.15, "rectus_femoris": 1.1}},
    "hinge":           {"initiation": {"erector_spinae": 1.2, "latissimus_dorsi": 1.1}, "mid": {"gluteus_maximus": 1.15}, "lockout": {"gluteus_maximus": 1.25}},
    "horizontal_push": {"initiation": {"pectoralis_major_sternal": 1.2}, "mid": {"anterior_deltoid": 1.1}, "lockout": {"triceps_brachii": 1.3}},
    "vertical_push":   {"initiation": {"anterior_deltoid": 1.15}, "mid": {"lateral_deltoid": 1.1}, "lockout": {"triceps_brachii": 1.25}},
    "horizontal_pull": {"initiation": {"latissimus_dorsi": 1.1}, "mid": {"trapezius_mid_lower": 1.15}, "lockout": {"posterior_deltoid": 1.2, "trapezius_mid_lower": 1.2}},
    "vertical_pull":   {"initiation": {"latissimus_dorsi": 1.15}, "mid": {"biceps_brachii": 1.1}, "lockout": {"trapezius_mid_lower": 1.15, "posterior_deltoid": 1.1}},
}


def _get_activation(exercise_name, movement_pattern, muscle_name):
    base = _PATTERN_ACTIVATION.get(movement_pattern, {}).get(muscle_name, 0.0)
    overrides = _EXERCISE_OVERRIDES.get(exercise_name, {})
    if muscle_name in overrides:
        return overrides[muscle_name]
    return base


def _classify_role(activation):
    if activation >= ROLE_THRESHOLDS["prime_mover"]:
        return "prime_mover"
    elif activation >= ROLE_THRESHOLDS["synergist"]:
        return "synergist"
    elif activation > 0:
        return "stabilizer"
    return None


def seed_all(db: Session):
    if db.query(Exercise).count() > 0:
        return False

    muscle_objs = {}
    for name, group, region in MUSCLES:
        m = Muscle(name=name, group_name=group, region=region)
        db.add(m)
        db.flush()
        muscle_objs[name] = m

    exercise_objs = {}
    for name, cat, pattern, equip, bi in EXERCISES:
        e = Exercise(name=name, category=cat, movement_pattern=pattern, equipment=equip, bilateral=bi)
        db.add(e)
        db.flush()
        exercise_objs[name] = e

    for ex_name, ex_cat, ex_pattern, _, _ in EXERCISES:
        ex = exercise_objs[ex_name]
        for mu_name, _, _ in MUSCLES:
            mu = muscle_objs[mu_name]
            act = _get_activation(ex_name, ex_pattern, mu_name)
            if act <= 0:
                continue

            db.add(ActivationMatrixV2(
                exercise_id=ex.id, muscle_id=mu.id, activation=round(act, 4)
            ))

            role = _classify_role(act)
            rw = ROLE_WEIGHTS.get(role, 0.25)
            db.add(RoleWeightedMatrixV2(
                exercise_id=ex.id, muscle_id=mu.id,
                role=role, weight=rw,
                weighted_activation=round(act * rw, 4),
            ))

            phase_mods = PHASE_MODIFIERS.get(ex_pattern, {})
            for phase in ("initiation", "mid", "lockout"):
                modifier = phase_mods.get(phase, {}).get(mu_name, 1.0)
                phase_act = min(act * modifier, 1.0)
                db.add(PhaseMatrixV3(
                    exercise_id=ex.id, muscle_id=mu.id,
                    phase=phase, activation=round(phase_act, 4),
                ))

            all_acts_for_ex = [
                _get_activation(ex_name, ex_pattern, mn)
                for mn, _, _ in MUSCLES
                if _get_activation(ex_name, ex_pattern, mn) > 0
            ]
            max_act = max(all_acts_for_ex) if all_acts_for_ex else 1.0
            bottleneck = act / max_act if max_act > 0 else 0.0
            is_lim = 1 if (role == "prime_mover" and bottleneck < 0.85) else 0
            db.add(BottleneckMatrixV4(
                exercise_id=ex.id, muscle_id=mu.id,
                bottleneck_coefficient=round(bottleneck, 4),
                is_limiting=is_lim,
            ))

            if role == "stabilizer":
                stab = act
                dyn = act * 0.3
            elif role == "synergist":
                stab = act * 0.4
                dyn = act * 0.8
            else:
                stab = act * 0.15
                dyn = act
            db.add(StabilizationMatrixV5(
                exercise_id=ex.id, muscle_id=mu.id,
                stabilization_score=round(stab, 4),
                dynamic_score=round(dyn, 4),
            ))

            phase_avg = 0.0
            for phase in ("initiation", "mid", "lockout"):
                modifier = phase_mods.get(phase, {}).get(mu_name, 1.0)
                phase_avg += min(act * modifier, 1.0)
            phase_avg /= 3.0

            comp = (
                0.35 * act +
                0.25 * phase_avg +
                0.20 * bottleneck +
                0.10 * stab +
                0.10 * dyn
            )
            db.add(CompositeIndex(
                exercise_id=ex.id, muscle_id=mu.id,
                composite_score=round(comp, 4),
                activation_component=round(act, 4),
                phase_component=round(phase_avg, 4),
                bottleneck_component=round(bottleneck, 4),
                stabilization_component=round((stab + dyn) / 2, 4),
            ))

    db.commit()
    return True
