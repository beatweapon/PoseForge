"""Card grasp preview: arm placement followed by two positional fingertip solves.

This tests bone-tip proximity, NOT skin contact or collision-free grasping.
"""
import bpy
from mathutils import Matrix, Quaternion, Vector
from rig import arm_chain, wrist_bone_name, semantic_bones
from ik import solve_hand_reach, solve_tip

def card_face_targets(position, size, corner="top_right", clearance=0.010):
    """Top-right corner on both faces, inset 12 mm to stay on each face."""
    if corner != "top_right":
        raise ValueError("Unsupported corner")
    center = Vector(position)
    sx, sy, sz = size
    x = center.x + sx / 2 - min(0.012, sx / 4)
    z = center.z + sz / 2 - min(0.012, sz / 4)
    return {
        "thumb": Vector((x, center.y + sy / 2 + clearance, z)),
        "index": Vector((x, center.y - sy / 2 - clearance, z)),
    }

def add_card(position, size):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    card = bpy.context.object
    card.name = "Card_grasp_preview"
    card.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mat = bpy.data.materials.new("Card_blue")
    mat.diffuse_color = (0.12, 0.35, 0.85, 1.0)
    card.data.materials.append(mat)
    return card

def _measure(rig, bones, names, side, targets):
    """Measure both tips AFTER all pose operations, in world coordinates."""
    bpy.context.view_layer.update()
    out = []
    for finger in ("thumb", "index"):
        actual = rig.matrix_world @ bones[names[f"{side}_{finger}_3"]].tail
        target = targets[finger]
        error = (actual - target).length
        out.append({"effector": f"{side}_{finger}",
                    "face": "front" if finger == "thumb" else "back",
                    "target": [float(v) for v in target],
                    "actual": [float(v) for v in actual],
                    "delta_world": [float(v) for v in target - actual],
                    "error_m": round(error, 6),
                    "converged": error <= 0.003})
    return out


def solve_card_grasp(rig, spec):
    side = spec["hand"]
    targets = card_face_targets(spec["card"]["position"], spec["card"]["size"])
    card = add_card(spec["card"]["position"], spec["card"]["size"])
    names = semantic_bones(rig.pose.bones.keys())
    bones = rig.pose.bones
    wrist = wrist_bone_name(side)
    finger_tips = [names[f"{side}_{f}_3"] for f in ("thumb", "index")]
    bpy.context.view_layer.update()
    middle = sum((bones[n].tail.copy() for n in finger_tips), Vector()) / 2
    wrist_position = bones[wrist].head.copy()
    target_middle = (targets["thumb"] + targets["index"]) / 2
    desired_wrist = rig.matrix_world @ (
        wrist_position + (rig.matrix_world.inverted() @ target_middle - middle))
    arm_names = arm_chain(side, bones.keys())
    finger_chains = {
        finger: [names[f"{side}_{finger}_{j}"] for j in (3, 2, 1)]
        for finger in ("thumb", "index")
    }

    def fit_fingers():
        for finger in ("thumb", "index"):
            solve_tip(rig, finger_chains[finger], targets[finger])
        return _measure(rig, bones, names, side, targets)

    arm = solve_hand_reach(rig, side, wrist, arm_names, desired_wrist)
    results = fit_fingers()
    initial_max_error = max(r["error_m"] for r in results)
    best_score = sum(r["error_m"] ** 2 for r in results)
    optimized_bones = list(dict.fromkeys(arm_names + [wrist] + sum(finger_chains.values(), [])))
    best_pose = {name: bones[name].matrix.copy() for name in optimized_bones}
    history = [{"pass": 0, "max_error_m": initial_max_error,
                "sum_square_error": best_score}]

    # A two-stage solve can leave the thumb out of reach. Adjust the wrist
    # towards the residual of both finger goals, then re-fit each finger.
    # Preserve the best pose so extra passes can never regress the measured
    # bone-tip objective. This is not collision-aware or anatomically constrained.
    for attempt in range(1, 5):
        residual = sum((targets[finger] -
                        rig.matrix_world @ bones[names[f"{side}_{finger}_3"]].tail
                        for finger in ("thumb", "index")), Vector()) / 2
        if residual.length < 0.001:
            break
        # Limit arm translation correction to 25 mm per pass.
        if residual.length > 0.025:
            residual.normalize()
            residual *= 0.025
        current_wrist = rig.matrix_world @ bones[wrist].head
        arm = solve_hand_reach(rig, side, wrist, arm_names,
                               current_wrist + residual)
        candidate = fit_fingers()
        score = sum(r["error_m"] ** 2 for r in candidate)
        history.append({"pass": attempt,
                        "max_error_m": max(r["error_m"] for r in candidate),
                        "sum_square_error": score})
        if score + 1e-10 < best_score:
            best_score = score
            best_pose = {name: bones[name].matrix.copy() for name in optimized_bones}
        else:
            # No systematic progress: don't keep accumulating distorted poses.
            break

    # The wrist orientation controls the separation and reach of thumb/index.
    # Explore a small bounded set of wrist rotations instead of only trying
    # translations. Record errors; these are still bone-tip proxy targets.
    def restore_pose(snapshot):
        for name in sorted(optimized_bones,
                           key=lambda n: len(bones[n].parent_recursive)):
            bones[name].matrix = snapshot[name]
            bpy.context.view_layer.update()

    orientation_trials = []
    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        for angle in (-0.35, 0.35):
            restore_pose(best_pose)
            pivot = bones[wrist].head.copy()
            rotation = Quaternion(Vector(axis), angle).to_matrix().to_4x4()
            bones[wrist].matrix = (Matrix.Translation(pivot) @ rotation
                                   @ Matrix.Translation(-pivot) @ bones[wrist].matrix)
            bpy.context.view_layer.update()
            candidate = fit_fingers()
            score = sum(row["error_m"] ** 2 for row in candidate)
            orientation_trials.append({"axis": list(axis), "angle_rad": angle,
                                       "max_error_m": max(row["error_m"] for row in candidate),
                                       "sum_square_error": score})
            if score + 1e-10 < best_score:
                best_score = score
                best_pose = {name: bones[name].matrix.copy()
                             for name in optimized_bones}

    # Restore poses in hierarchy order (parents before children) so child
    # matrices are not shifted by later parent restoration.
    for name in sorted(optimized_bones, key=lambda n: len(bones[n].parent_recursive)):
        bones[name].matrix = best_pose[name]
        bpy.context.view_layer.update()
    final_results = _measure(rig, bones, names, side, targets)
    for row in final_results:
        row["sample_point"] = "bone_tail"
    arm["optimization"] = {
        "passes": history,
        "initial_max_error_m": initial_max_error,
        "final_max_error_m": max(row["error_m"] for row in final_results),
        "strategy": "wrist residual refinement plus orientation sweep",
        "orientation_trials": orientation_trials,
    }
    return card, arm, final_results
