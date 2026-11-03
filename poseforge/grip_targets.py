"""Shared prop grip targets for two-hand pose references.

Targets specify a position and approach direction in WORLD coordinates.
Wrist-to-knuckle is only a coarse hand-axis proxy, not a grip/contact test.
"""
import math
import bpy
from mathutils import Matrix, Quaternion, Vector
from ik import solve_hand_reach
from rig import arm_chain, wrist_bone_name, semantic_bones
from grip_pose import apply_cylinder_grip


def _hand_frame(bones, names, side):
    """Estimate a palm plane from the wrist, index and pinky knuckle heads."""
    wrist = bones[wrist_bone_name(side)].head.copy()
    index = bones[names[f"{side}_index_1"]].head.copy()
    pinky = bones[names[f"{side}_pinky_1"]].head.copy()
    forward = index - wrist
    lateral = pinky - index
    if forward.length < 1e-7 or lateral.length < 1e-7:
        return None
    forward.normalize()
    normal = forward.cross(lateral)
    if normal.length < 1e-7:
        return None
    normal.normalize()
    return forward, normal


def _palm_metrics(bones, names, side, desired_forward, desired_normal):
    frame = _hand_frame(bones, names, side)
    if frame is None:
        return {"forward_deg": None, "plane_deg": None}
    forward, normal = frame
    return {
        "forward_deg": round(math.degrees(forward.angle(desired_forward)), 3),
        # Unoriented plane diagnostic: side of the hand is NOT calibrated.
        "plane_deg": round(math.degrees(math.acos(min(1.0, max(0.0,
                    abs(normal.dot(desired_normal)))))), 3),
    }


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
        desired_normal_world = Vector(item.get("palm_normal_world",
                                              (0, -1, 0)))
        if desired_normal_world.length < 1e-6:
            raise ValueError("Zero palm plane normal")
        desired_normal = (rig.matrix_world.inverted().to_3x3()
                          @ desired_normal_world).normalized()
        target_local = rig.matrix_world.inverted().to_3x3() @ axis
        target_local.normalize()
        initial_angle = (math.degrees(before_axis.angle(target_local))
                         if before_axis is not None else None)
        palm_before = _palm_metrics(bones, mapping, side,
                                      (rig.matrix_world.inverted().to_3x3() @ axis).normalized(),
                                      desired_normal)
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

        # Small wrist roll search: correct the hand plane without rotating
        # shoulder/elbow or pushing the hand farther from the handle.
        # The palm-side sign is unknown, so do not infer skin-side contact.
        forward_axis = current_axis()
        if forward_axis is not None:
            base = wrist.matrix.copy()
            best = base.copy()
            desired_forward = (rig.matrix_world.inverted().to_3x3() @ axis).normalized()
            def objective():
                angles = _palm_metrics(bones, mapping, side,
                                       desired_forward, desired_normal)
                if angles["plane_deg"] is None:
                    return float("inf")
                return angles["forward_deg"] + 0.55 * angles["plane_deg"]
            score = objective()
            pivot = wrist.head.copy()
            for sign in (-1, 1):
                wrist.matrix = base.copy()
                bpy.context.view_layer.update()
                rotation = Quaternion(forward_axis, sign * 0.16)
                wrist.matrix = (Matrix.Translation(pivot)
                                @ rotation.to_matrix().to_4x4()
                                @ Matrix.Translation(-pivot) @ wrist.matrix)
                bpy.context.view_layer.update()
                candidate = objective()
                if candidate < score - 1e-5:
                    score = candidate
                    best = wrist.matrix.copy()
            wrist.matrix = best
            bpy.context.view_layer.update()
        palm_after = _palm_metrics(bones, mapping, side,
                                     (rig.matrix_world.inverted().to_3x3() @ axis).normalized(),
                                     desired_normal)
        results.append({
            "hand": side, "grip_world": [float(v) for v in grip],
            "wrist_goal_world": [float(v) for v in goal],
            "approach_axis_world": [float(v) for v in axis],
            "orientation_angle_before_deg": (
                round(initial_angle, 3) if initial_angle is not None else None),
            "arm_ik": arm_result,
            "palm_frame_before": palm_before,
            "palm_frame_after": palm_after,
            "palm_plane_is_unoriented": True,
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
