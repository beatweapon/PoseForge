"""Experimental joint-position-and-orientation refinement of a rigid handle grip.

This evaluates a *single* hand pose against several coupled constraints, rather
than independently optimizing wrist roll and palm placement. The grip remains
a skeletal approximation; real surface contact and joint limits are NOT solved.
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from palm_anchor import palm_anchor
from rig import semantic_bones, wrist_bone_name


WEIGHTS = {
    "joint_balanced": (1.0, 0.45, 0.16),
    "joint_position": (1.5, 0.30, 0.20),
    "joint_orientation": (0.6, 1.0, 0.18),
}


def score_proxy(palm_error_m, plane_deg, forward_deg, wrist_error_m,
                weights):
    """Dimensionless comparison score; NOT a physical contact probability."""
    if min(palm_error_m, plane_deg, forward_deg, wrist_error_m) < 0:
        raise ValueError("Pose metrics must be nonnegative")
    a, b, c = weights
    return (a * palm_error_m / 0.05
            + b * (0.6 * plane_deg + 0.4 * forward_deg) / 90.0
            + c * wrist_error_m / 0.025)


def refine_joint_grip(rig, item, variant, *, wrist_budget_m=0.025):
    """Search bounded wrist rotations with a coupled, rollback-safe objective.

    The existing arm-position IK already ran. We preserve its wrist position
    while searching orientation; the palm position changes as the wrist turns.
    Candidate rotations are applied to the same baseline matrix each time.
    """
    if variant not in WEIGHTS:
        raise ValueError("Unsupported joint grip variant: " + variant)

    from grip_targets import _palm_metrics

    bones = rig.pose.bones
    names = semantic_bones(bones.keys())
    side = item["hand"]
    wrist = bones[wrist_bone_name(side)]
    base = wrist.matrix.copy()
    pivot = wrist.head.copy()
    transform = rig.matrix_world.inverted().to_3x3()

    desired_forward = (transform @ Vector(item["approach_axis_world"])).normalized()
    desired_normal = (transform @ Vector(
        item.get("palm_normal_world", (0, -1, 0)))).normalized()
    handle_axis = Vector(item.get("handle_axis_world", (1, 0, 0)))
    approach = Vector(item["approach_axis_world"])
    approach = (approach - handle_axis.normalized() *
                approach.dot(handle_axis.normalized())).normalized()
    target = Vector(item["grip_world"]) - approach * (
        float(item.get("handle_radius_m", 0.016)) + 0.018)
    wrist_goal = Vector(item["grip_world"]) + Vector(item["wrist_offset"])
    weights = WEIGHTS[variant]

    def measure():
        bpy.context.view_layer.update()
        palm_error = (palm_anchor(rig, side, names) - target).length
        wrist_error = (rig.matrix_world @ wrist.head - wrist_goal).length
        angles = _palm_metrics(bones, names, side,
                               desired_forward, desired_normal)
        if angles["plane_deg"] is None:
            raise ValueError("Unable to derive palm plane from knuckles")
        return {
            "palm_error_m": round(float(palm_error), 6),
            "wrist_error_m": round(float(wrist_error), 6),
            "plane_deg": angles["plane_deg"],
            "forward_deg": angles["forward_deg"],
            "objective": round(score_proxy(
                palm_error, angles["plane_deg"], angles["forward_deg"],
                wrist_error, weights), 6),
        }

    baseline = measure()
    best = base.copy()
    best_values = baseline
    trials = [{"axis": "none", "rad": 0.0, **baseline}]
    # One bounded search from a common base. Avoid accumulated rotations
    # that can severely twist the palm.
    for axis_name, axis in (("x", (1, 0, 0)),
                            ("y", (0, 1, 0)),
                            ("z", (0, 0, 1))):
        for amount in (-0.40, -0.20, 0.20, 0.40):
            wrist.matrix = base.copy()
            bpy.context.view_layer.update()
            rot = Quaternion(Vector(axis), amount).to_matrix().to_4x4()
            wrist.matrix = (Matrix.Translation(pivot) @ rot
                            @ Matrix.Translation(-pivot) @ wrist.matrix)
            candidate = measure()
            trials.append({"axis": axis_name, "rad": amount, **candidate})
            if (candidate["wrist_error_m"] <= wrist_budget_m and
                    candidate["objective"] + 0.00001 <
                    best_values["objective"]):
                best = wrist.matrix.copy()
                best_values = candidate

    wrist.matrix = best
    final = measure()
    position_refinement = {"attempted": False, "accepted": False}
    if variant == "joint_position":
        # One small arm-space adjustment after finding hand orientation.
        # This tests a genuinely different hypothesis from wrist-only
        # orientation trials, while preserving the best whole-arm pose.
        from palm_anchor import fit_palm_anchor
        from rig import arm_chain
        chain = arm_chain(side, bones.keys())
        saved_names = list(dict.fromkeys(chain + [wrist.name]))
        saved = {name: bones[name].matrix.copy() for name in saved_names}
        candidate_fit = fit_palm_anchor(
            rig, side, target, passes=3,
            wrist_goal_world=wrist_goal, wrist_max_deviation=wrist_budget_m)
        after = measure()
        position_refinement = {"attempted": True,
                               "candidate_fit": candidate_fit,
                               "candidate_score": after["objective"]}
        if (after["wrist_error_m"] <= wrist_budget_m and
                after["objective"] + 0.00001 < final["objective"]):
            final = after
            position_refinement["accepted"] = True
        else:
            for name in sorted(saved_names,
                               key=lambda name: len(bones[name].parent_recursive)):
                bones[name].matrix = saved[name]
                bpy.context.view_layer.update()
            final = measure()
    return {
        "name": "coupled_grip_proxy_v1",
        "variant": variant,
        "baseline": baseline,
        "final": final,
        "trials": trials,
        "wrist_budget_m": wrist_budget_m,
        "arm_position_refinement": position_refinement,
        "objective_non_regression": (
            final["objective"] <= baseline["objective"] + 0.0001),
        "measured_palm_is_skeletal_proxy": True,
        "anatomical_joint_limits_verified": False,
        "surface_contact_verified": False,
        "collision_free_verified": False,
    }
