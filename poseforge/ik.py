"""Positional cyclic-coordinate-descent IK for Blender pose bones.

Does not solve orientation, anatomical limits, collisions, or grasp forces.
"""
from mathutils import Matrix, Quaternion, Vector
import bpy

def solve_chain_to_point(rig, tip_name, chain, target_world, *,
                         point="tail", max_iterations=120, tolerance=0.005,
                         max_step_angle=0.25):
    bones = rig.pose.bones
    if point not in ("head", "tail"):
        raise ValueError("Unsupported tip point")
    missing = [name for name in [tip_name, *chain] if name not in bones]
    if missing:
        raise ValueError("Missing bones: " + ", ".join(missing))
    if not chain:
        raise ValueError("IK chain cannot be empty")
    target = rig.matrix_world.inverted() @ Vector(target_world)
    def sample():
        bone = bones[tip_name]
        return (bone.head if point == "head" else bone.tail).copy()
    iterations = 0
    for iteration in range(max_iterations):
        iterations = iteration + 1
        if (sample() - target).length <= tolerance:
            break
        for name in chain:
            pivot = bones[name].head.copy()
            source_vector = sample() - pivot
            target_vector = target - pivot
            if min(source_vector.length, target_vector.length) < 1e-8:
                continue
            delta = source_vector.rotation_difference(target_vector)
            if delta.angle > max_step_angle:
                delta = Quaternion(delta.axis, max_step_angle)
            bone = bones[name]
            bone.matrix = (Matrix.Translation(pivot) @ delta.to_matrix().to_4x4()
                           @ Matrix.Translation(-pivot) @ bone.matrix)
            bpy.context.view_layer.update()
    actual = rig.matrix_world @ sample()
    delta_world = Vector(target_world) - actual
    error = delta_world.length
    return {"target": [float(v) for v in target_world],
            "actual": [float(v) for v in actual],
            "delta_world": [float(v) for v in delta_world],
            "error_m": round(error, 6), "converged": bool(error <= tolerance),
            "iterations": iterations, "chain": list(chain),
            "sample_point": point}

def solve_tip(rig, chain, target_world, max_iterations=80, tolerance=0.003):
    return solve_chain_to_point(rig, chain[0], chain, target_world,
                                max_iterations=max_iterations,
                                tolerance=tolerance, max_step_angle=0.35)

def solve_hand_reach(rig, side, wrist_name, chain, target_world):
    result = solve_chain_to_point(rig, wrist_name, chain, target_world,
                                  point="head", max_iterations=120,
                                  tolerance=0.01)
    result["effector"] = side + "_hand"
    return result
