"""Simple positional CCD for a semantic fingertip goal in Blender.

No joint limits, collision solving, or grip/contact forces.
"""
from mathutils import Matrix, Quaternion, Vector
import bpy


def solve_tip(rig, chain, target_world, max_iterations=80, tolerance=0.003):
    """Rotate distal-to-proximal bones; target is in Blender world meters."""
    bones = rig.pose.bones
    if any(name not in bones for name in chain):
        raise ValueError("Missing finger bones for IK")
    target = rig.matrix_world.inverted() @ Vector(target_world)
    tip_name = chain[0]
    def tip():
        return bones[tip_name].tail.copy()
    for iteration in range(max_iterations):
        if (tip() - target).length <= tolerance:
            break
        for name in chain:
            pivot = bones[name].head.copy()
            current, desired = tip() - pivot, target - pivot
            if current.length < 1e-8 or desired.length < 1e-8:
                continue
            delta = current.rotation_difference(desired)
            if delta.angle > 0.35:
                delta = Quaternion(delta.axis, 0.35)
            bone = bones[name]
            bone.matrix = (Matrix.Translation(pivot) @ delta.to_matrix().to_4x4()
                           @ Matrix.Translation(-pivot) @ bone.matrix)
            bpy.context.view_layer.update()
    actual = rig.matrix_world @ tip()
    error = (actual - Vector(target_world)).length
    return {"target": [float(v) for v in target_world],
            "actual": [float(v) for v in actual],
            "error_m": round(error, 6), "converged": error <= tolerance,
            "iterations": iteration + 1}
