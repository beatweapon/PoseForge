"""A single rigid bow prop and a bilateral, actor-relative holding pose.

The bow mesh/string remain in world space; only the two armature arm chains
move. Wrist IK is a coarse proxy, not a physically verified grip.
"""
import bpy
from mathutils import Vector
from grip_targets import solve_grip_frames


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
        # The bow bends in the XZ plane, so the front/back renders show its
        # silhouette rather than a straight horizontal rod.
        points.append(c + Vector((half * u, 0.03 * u * u, 0.14 * u * u)))
    limbs = _tube("Bow_Limbs", points, 0.012, (0.38, 0.17, 0.065, 1))
    string = _tube("Bow_String",
                   (points[0], c + Vector((0, -0.03, 0.14)), points[-1]),
                   0.0017, (0.85, 0.75, 0.55, 1))
    grip_offsets = {"right": -0.23 * length, "left": 0.23 * length}
    # Physical grip points lie on the curved rigid limb.
    grip_points = {
        side: c + Vector((x, 0.03 * (x / half) ** 2, 0.14 * (x / half) ** 2))
        for side, x in grip_offsets.items()
    }
    return {
        "parts": [limbs.name, string.name],
        "center": [float(v) for v in c],
        "length_m": float(length),
        "grips": {k: [float(v) for v in p] for k, p in grip_points.items()},
        "bow_endpoints": [[float(v) for v in p] for p in (points[0], points[-1])],
        "bow_string_shared_scene": True,
        "front_silhouette_end_rise_m": 0.14,
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
    grip_frames = [
        {"hand": side, "grip_world": prop["grips"][side],
         "wrist_offset": [0, 0.012, 0.078],
         "approach_axis_world": [0, 0, -1]}
        for side in ("right", "left")
    ]
    results = solve_grip_frames(rig, grip_frames)
    prop["kind"] = "bow"
    prop["grip_frames"] = grip_frames
    return prop, results
