"""Handle-relative palm anchor placement for prop-grip prototypes.

Use the rig's knuckle positions rather than a manually guessed wrist offset.
This only positions a skeletal palm proxy. Skin contact and bone limits remain
unverified.
"""
import bpy
from mathutils import Vector
from ik import solve_hand_reach
from rig import semantic_bones, arm_chain, wrist_bone_name


def palm_anchor(rig, side, mapping=None):
    names = mapping or semantic_bones(rig.pose.bones.keys())
    bones = rig.pose.bones
    a = rig.matrix_world @ bones[names[f"{side}_index_1"]].head
    b = rig.matrix_world @ bones[names[f"{side}_pinky_1"]].head
    return (a + b) * 0.5


def resolve_palm_target(grip_world, handle_axis_world, approach_axis_world,
                        radius, skin_allowance=0.018):
    """Choose a consistent offset perpendicular to the handle, toward wrist.

    The approach vector points wrist -> fingers, so the palm anchor is placed
    on the opposite side of the handle from the knuckles' approach.
    """
    axis = Vector(handle_axis_world)
    approach = Vector(approach_axis_world)
    if axis.length < 1e-8 or approach.length < 1e-8:
        raise ValueError("Zero grip or approach axis")
    axis.normalize()
    sideways = approach - axis * approach.dot(axis)
    if sideways.length < 1e-6:
        raise ValueError("Approach axis must not be parallel to handle")
    sideways.normalize()
    return Vector(grip_world) - sideways * (radius + skin_allowance)


def fit_palm_anchor(rig, side, target_world, *, passes=5,
                    wrist_goal_world=None, wrist_max_deviation=0.025):
    """Repeatedly solve arm position using the *actual* knuckle midpoint.

    Always retain the pose with the smallest palm-proxy error.
    """
    bones = rig.pose.bones
    chain = arm_chain(side, bones.keys())
    wrist = wrist_bone_name(side)
    names = semantic_bones(bones.keys())
    target = Vector(target_world)
    ordered = sorted(chain, key=lambda name: len(bones[name].parent_recursive))

    def error():
        return (palm_anchor(rig, side, names) - target).length

    best_error = error()
    original_error = best_error
    best = {name: bones[name].matrix.copy() for name in chain}
    trace = [round(best_error, 6)]
    for _ in range(passes):
        if best_error < 0.008:
            break
        residual = target - palm_anchor(rig, side, names)
        if residual.length > 0.012:
            residual.normalize()
            residual *= 0.012
        current_wrist = rig.matrix_world @ bones[wrist].head
        solve_hand_reach(rig, side, wrist, chain, current_wrist + residual)
        bpy.context.view_layer.update()
        candidate = error()
        trace.append(round(candidate, 6))
        if wrist_goal_world is not None:
            tested_wrist = rig.matrix_world @ bones[wrist].head
            if (tested_wrist - Vector(wrist_goal_world)).length > wrist_max_deviation:
                break
        if candidate < best_error - 0.0001:
            best_error = candidate
            best = {name: bones[name].matrix.copy() for name in chain}
        else:
            break
    for name in ordered:
        bones[name].matrix = best[name]
        bpy.context.view_layer.update()
    final = error()
    return {
        "name": "skeletal_palm_anchor_v1",
        "target_world": [float(v) for v in target],
        "actual_world": [float(v) for v in palm_anchor(rig, side, names)],
        "initial_error_m": round(original_error, 6),
        "final_error_m": round(final, 6),
        "attempted_errors_m": trace,
        "improved_or_unchanged": final <= original_error + 1e-5,
        "skin_contact_verified": False,
    }
