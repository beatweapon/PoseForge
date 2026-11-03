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
from palm_anchor import resolve_palm_target, fit_palm_anchor


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

        # Search a bounded set of wrist roll candidates against BOTH palm
        # plane and forward axis. Never treat an unoriented plane as proof
        # that the palm's skin side faces the handle.
        forward_axis = current_axis()
        wrist_trials = []
        if forward_axis is not None:
            base = wrist.matrix.copy()
            pivot = wrist.head.copy()
            desired_forward = (rig.matrix_world.inverted().to_3x3() @ axis).normalized()
            def objective():
                values = _palm_metrics(bones, mapping, side,
                                       desired_forward, desired_normal)
                if values["plane_deg"] is None:
                    return float("inf"), values
                return values["forward_deg"] + 0.55 * values["plane_deg"], values

            best_score, values = objective()
            best_matrix = base.copy()
            wrist_trials.append({"roll_rad": 0.0,
                                 "objective_deg": round(best_score, 3),
                                 **values})
            # Wider exploration than the original ±0.16-rad single step.
            # Maximum total wrist roll is 0.48 rad (~27.5 degrees).
            for rotation_angle in (-0.48, -0.32, -0.16,
                                    0.16, 0.32, 0.48):
                wrist.matrix = base.copy()
                bpy.context.view_layer.update()
                rotation = Quaternion(forward_axis, rotation_angle)
                wrist.matrix = (Matrix.Translation(pivot)
                                @ rotation.to_matrix().to_4x4()
                                @ Matrix.Translation(-pivot) @ wrist.matrix)
                bpy.context.view_layer.update()
                score, values = objective()
                wrist_trials.append({"roll_rad": rotation_angle,
                                     "objective_deg": round(score, 3),
                                     **values})
                if score < best_score - 1e-5:
                    best_score = score
                    best_matrix = wrist.matrix.copy()
            wrist.matrix = best_matrix
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
            "wrist_roll_trials": wrist_trials,
            "max_roll_from_arm_ik_rad": 0.48,
        })

    # Re-solve from a handle-relative palm target, rather than tuning a fixed
    # wrist offset. Preserve the earlier wrist pose when its original wrist
    # target would be lost by more than 25mm.
    palm_fits = {}
    for item in targets:
        side = item["hand"]
        wrist = bones[wrist_bone_name(side)]
        chain = arm_chain(side, bones.keys())
        saved = {name: bones[name].matrix.copy() for name in chain}
        goal = resolve_palm_target(
            item["grip_world"], item.get("handle_axis_world", (1, 0, 0)),
            item["approach_axis_world"], item.get("handle_radius_m", 0.016))
        fit = fit_palm_anchor(rig, side, goal)
        actual_wrist = rig.matrix_world @ wrist.head
        original_goal = Vector(item["grip_world"]) + Vector(item["wrist_offset"])
        wrist_deviation = (actual_wrist - original_goal).length
        if wrist_deviation > 0.025:
            for name in sorted(chain,
                               key=lambda n: len(bones[n].parent_recursive)):
                bones[name].matrix = saved[name]
                bpy.context.view_layer.update()
            fit["accepted"] = False
            fit["rejection_reason"] = "wrist_original_goal_deviation_over_25mm"
        else:
            fit["accepted"] = True
        fit["wrist_deviation_m"] = round(float(wrist_deviation), 6)
        palm_fits[side] = fit

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
            "palm_anchor_fit": palm_fits[side],
            "pose_quality": {
                "status": "unverified",
                "criteria": "palm plane <= 25deg; index tip axis gap <= 25mm",
                "palm_plane_within_target": (
                    palm_after["plane_deg"] is not None and
                    palm_after["plane_deg"] <= 25.0),
                "index_bone_axis_gap_within_target": (
                    abs(finger_priors[side]["final_axis_distances_m"]["index"] -
                        finger_priors[side]["radius_m"]) <= 0.025),
                "skin_contact_verified": False,
                "collision_free_verified": False,
            },
        })
    return results
