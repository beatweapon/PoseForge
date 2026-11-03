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
    # Keep the safe existing wrist seed for the semantic placement preview.
    # A 65 mm lateral wrist seed reduced sampled intersections but produced
    # severe hand twisting; do not use it without joint-angle constraints.
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


def refine_skin_grasp(rig, card, side, body_objects, bone_targets, *, trials=4):
    """Bounded mesh-aware wrist pose search; never worsens the measured objective.

    All candidates are measured against the *evaluated skin*, not just bone
    tips. The evaluator samples vertices; it does not prove collision freedom.
    """
    from contact import inspect_card_skin

    bones = rig.pose.bones
    names = semantic_bones(bones.keys())
    wrist = wrist_bone_name(side)
    chains = {
        finger: [names[f"{side}_{finger}_{i}"] for i in (3, 2, 1)]
        for finger in ("thumb", "index")
    }
    involved = [wrist] + [name for chain in chains.values() for name in chain]
    involved = list(dict.fromkeys(involved))
    ordered = sorted(involved, key=lambda name: len(bones[name].parent_recursive))

    def snapshot():
        return {name: bones[name].matrix.copy() for name in involved}

    def restore(saved):
        for name in ordered:
            bones[name].matrix = saved[name]
            bpy.context.view_layer.update()

    def errors():
        bpy.context.view_layer.update()
        return {
            finger: float((rig.matrix_world @ bones[names[f"{side}_{finger}_3"]].tail
                           - bone_targets[finger]).length)
            for finger in ("thumb", "index")
        }

    def evaluate():
        metrics = inspect_card_skin(rig, card, side, names, body_objects)
        error = errors()
        samples = [metrics["fingers"].get(f, {}) for f in ("thumb", "index")]
        if any(not row.get("sample_count") for row in samples):
            return float("inf"), metrics, error
        penetration = sum(row.get("sampled_vertices_inside_card", 0)
                          for row in samples)
        # Penalize penetration more than small surface-distance variation.
        gap = sum(
            min(row["nearest_outside_face_gap_m"], 0.03)
            if row.get("nearest_outside_face_gap_m") is not None else 0.03
            for row in samples)
        # Preserve goal proximity; large bone-tip changes are unacceptable.
        tip_cost = sum(max(0.0, e - 0.005) * 10 for e in error.values())
        return penetration * 0.02 + gap + tip_cost, metrics, error

    best_score, initial_metrics, initial_errors = evaluate()
    best_pose = snapshot()
    initial_inside = sum(
        row.get("sampled_vertices_inside_card", 0)
        for row in initial_metrics["fingers"].values())
    trace = [{"trial": "initial", "score": best_score,
              "inside": initial_inside, "tip_errors": initial_errors}]
    experiments = [
        ((1, 0, 0), 0.15), ((1, 0, 0), -0.15),
        ((0, 0, 1), 0.15), ((0, 0, 1), -0.15),
    ][:trials]

    for axis, angle in experiments:
        restore(best_pose)
        pivot = bones[wrist].head.copy()
        delta = Quaternion(Vector(axis), angle).to_matrix().to_4x4()
        bones[wrist].matrix = (Matrix.Translation(pivot) @ delta
                               @ Matrix.Translation(-pivot) @ bones[wrist].matrix)
        bpy.context.view_layer.update()
        for finger in ("thumb", "index"):
            solve_tip(rig, chains[finger], bone_targets[finger])
        score, metrics, tip_errors = evaluate()
        inside = sum(row.get("sampled_vertices_inside_card", 0)
                     for row in metrics["fingers"].values())
        trace.append({"trial": f"wrist_{axis}_{angle:+.2f}",
                      "score": score, "inside": inside,
                      "tip_errors": tip_errors})
        if score < best_score - 1e-7:
            best_score = score
            best_pose = snapshot()

    restore(best_pose)
    final_score, final_metrics, final_errors = evaluate()
    return {
        "method": "bounded_wrist_orientation_skin_vertex_search",
        "status": "improved" if final_score < trace[0]["score"] - 1e-7
                  else "no_improvement",
        "baseline_score": trace[0]["score"],
        "final_score": final_score,
        "baseline_inside": initial_inside,
        "final_inside": sum(
            row.get("sampled_vertices_inside_card", 0)
            for row in final_metrics["fingers"].values()),
        "final_tip_errors": final_errors,
        "trials": trace,
        "not_verified": ["continuous_collision", "joint_limits",
                         "skin_contact", "grasp_force"],
    }
