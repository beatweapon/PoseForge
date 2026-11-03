"""A single rigid bow prop and a bilateral, actor-relative holding pose.

The bow mesh/string remain in world space; only the two armature arm chains
move. Wrist IK is a coarse proxy, not a physically verified grip.
"""
import bpy
from mathutils import Vector
from ik import solve_hand_reach
from rig import arm_chain, wrist_bone_name


def _tube(name, points, radius, color):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, coordinate in zip(spline.points, points):
        p.co = (*coordinate, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.new(name + "_material")
    mat.diffuse_color = color
    curve.materials.append(mat)
    return obj


def create_bow(center, length):
    """Create a horizontal bow and bowstring once, in the same 3D scene."""
    c = Vector(center)
    half = length / 2
    points = []
    for i in range(33):
        u = -1.0 + 2.0 * i / 32
        # Symmetric recurve-ish profile in XY; fixed in all camera views.
        points.append(c + Vector((half * u, 0.11 * u * u - 0.035, 0)))
    limbs = _tube("Bow_Limbs", points, 0.012, (0.38, 0.17, 0.065, 1))
    string = _tube("Bow_String",
                   (points[0], c + Vector((0, -0.085, 0)), points[-1]),
                   0.0017, (0.85, 0.75, 0.55, 1))
    grip_offsets = {"right": -0.23 * length, "left": 0.23 * length}
    # Physical grip points lie on the curved rigid limb.
    grip_points = {
        side: c + Vector((x, 0.11 * (x / half) ** 2 - 0.035, 0))
        for side, x in grip_offsets.items()
    }
    return {
        "parts": [limbs.name, string.name],
        "center": [float(v) for v in c],
        "length_m": float(length),
        "grips": {k: [float(v) for v in p] for k, p in grip_points.items()},
        "bow_endpoints": [[float(v) for v in p] for p in (points[0], points[-1])],
        "bow_string_shared_scene": True,
    }


def hold_bow(rig, specification):
    """Position a bow around the waist and solve both wrist targets."""
    bones = rig.pose.bones
    shoulder_r = rig.matrix_world @ bones["upperarm01.R"].head
    shoulder_l = rig.matrix_world @ bones["upperarm01.L"].head
    shoulder_mid = (shoulder_l + shoulder_r) / 2
    length = float(specification["length_m"])
    c = shoulder_mid + Vector((0, -0.28, -0.41))
    prop = create_bow(c, length)
    results = []
    for side in ("right", "left"):
        grip = Vector(prop["grips"][side])
        # The wrist joint is intentionally just below and behind the bow;
        # it is not identical to palm or skin contact.
        goal = grip + Vector((0, 0.035, -0.035))
        wrist = wrist_bone_name(side)
        res = solve_hand_reach(
            rig, side, wrist, arm_chain(side, bones.keys()), goal)
        bpy.context.view_layer.update()
        results.append({"hand": side, "grip_world": prop["grips"][side],
                        "wrist_goal_world": [float(v) for v in goal],
                        **res})
    # Re-measure BOTH after solving BOTH; avoid stale first-hand reports.
    for item in results:
        side = item["hand"]
        actual = rig.matrix_world @ bones[wrist_bone_name(side)].head
        goal = Vector(item["wrist_goal_world"])
        item["actual"] = [float(v) for v in actual]
        item["error_m"] = round(float((actual - goal).length), 6)
        item["converged"] = item["error_m"] <= 0.01
    return prop, results
