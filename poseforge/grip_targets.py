"""Shared prop grip targets for two-hand pose references.

Targets specify a position and approach direction in WORLD coordinates.
Wrist-to-knuckle is only a coarse hand-axis proxy, not a grip/contact test.
"""
import math
import bpy
from mathutils import Matrix, Vector
from ik import solve_hand_reach
from rig import arm_chain, wrist_bone_name, semantic_bones
from grip_pose import apply_cylinder_grip


def solve_grip_frames(rig, targets, *, max_orientation_rad=0.20):
    """Apply each hand's wrist-position IK and a bounded wrist-axis adjustment.

    targets: [{"hand": side, "grip_world": xyz, "wrist_offset": xyz,
               "approach_axis_world": xyz}].
    The direction is interpreted as wrist->knuckles, in WORLD coordinates.
    """
    bones = rig.pose.bones
    mapping = semantic_bones(bones.keys())
    results = []
    for item in targets:
        side = item["hand"]
        grip = Vector(item["grip_world"])
        offset = Vector(item["wrist_offset"])
        axis = Vector(item["approach_axis_world"])
        if axis.length < 1e-6:
            raise ValueError("Zero grip approach direction")
        axis.normalize()
        goal = grip + offset
        wrist_name = wrist_bone_name(side)
        wrist = bones[wrist_name]
        arm_result = solve_hand_reach(rig, side, wrist_name,
                                      arm_chain(side, bones.keys()), goal)
        bpy.context.view_layer.update()
        knuckle_name = mapping[f"{side}_index_1"]
        def current_axis():
            vec = bones[knuckle_name].head - wrist.head
            return vec.normalized() if vec.length > 1e-8 else None

        before_axis = current_axis()
        target_local = rig.matrix_world.inverted().to_3x3() @ axis
        target_local.normalize()
        initial_angle = (math.degrees(before_axis.angle(target_local))
                         if before_axis is not None else None)
        if before_axis is not None and initial_angle is not None:
            correction = before_axis.rotation_difference(target_local)
            if correction.angle > max_orientation_rad:
                correction = __import__("mathutils").Quaternion(
                    correction.axis, max_orientation_rad)
            pivot = wrist.head.copy()
            wrist.matrix = (Matrix.Translation(pivot)
                            @ correction.to_matrix().to_4x4()
                            @ Matrix.Translation(-pivot) @ wrist.matrix)
            bpy.context.view_layer.update()

        results.append({
            "hand": side, "grip_world": [float(v) for v in grip],
            "wrist_goal_world": [float(v) for v in goal],
            "approach_axis_world": [float(v) for v in axis],
            "orientation_angle_before_deg": (
                round(initial_angle, 3) if initial_angle is not None else None),
            "arm_ik": arm_result,
        })

    # Hand templates are applied AFTER arm positioning, against the shared
    # rigid handle frame. They do not move the prop or rewrite arm targets.
    finger_priors = {}
    for item in targets:
        finger_priors[item["hand"]] = apply_cylinder_grip(
            rig, item["hand"], item["grip_world"],
            item.get("handle_axis_world", (1, 0, 0)),
            radius=item.get("handle_radius_m", 0.016))

    # Sample after BOTH arms are solved; no stale first-hand measurements.
    for row in results:
        side = row["hand"]
        wrist = bones[wrist_bone_name(side)]
        actual = rig.matrix_world @ wrist.head
        goal = Vector(row["wrist_goal_world"])
        axis = bones[mapping[f"{side}_index_1"]].head - wrist.head
        desired_local = rig.matrix_world.inverted().to_3x3() @ Vector(
            row["approach_axis_world"])
        angle = (math.degrees(axis.angle(desired_local))
                 if axis.length > 1e-8 else None)
        row.update({
            "target": row["wrist_goal_world"],
            "actual": [float(v) for v in actual],
            "error_m": round((actual - goal).length, 6),
            "converged": (actual - goal).length <= 0.01,
            "orientation_angle_after_deg": (
                round(angle, 3) if angle is not None else None),
            "orientation_step_limit_rad": max_orientation_rad,
            "hand_surface_contact_verified": False,
            "orientation_verified": False,
            "finger_grip_prior": finger_priors[side],
        })
    return results
