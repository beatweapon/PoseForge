"""Reusable, conservative finger curl around a cylindrical prop.

The MPFB local-axis signs are evaluated as two trial poses, using sampled
skeletal distal-tip proximity to a grip axis. This is a pose prior rather than
true skin contact, tendon simulation or collision detection.
"""
import bpy
from mathutils import Vector
from rig import semantic_bones

FINGER_BENDS = {
    "index": (0.38, 0.52, 0.30),
    "middle": (0.45, 0.57, 0.32),
    "ring": (0.48, 0.60, 0.34),
    "pinky": (0.50, 0.55, 0.31),
}
THUMB_BENDS = ((0.10, 0.13, -0.20), (0.18, 0.09, -0.12),
               (0.12, 0.0, -0.05))


def _axis_distance(point, origin, direction):
    displacement = point - origin
    return (displacement - direction * displacement.dot(direction)).length


def apply_cylinder_grip(rig, side, grip_world, axis_world=(1, 0, 0),
                        radius=0.016, curl_scale=1.0):
    """Try both curl signs at a controlled scale, retain the better skeletal prior."""
    if not 0.5 <= curl_scale <= 1.6:
        raise ValueError("curl_scale outside experimental safe bounds")
    names = semantic_bones(rig.pose.bones.keys())
    fingers = ("thumb", "index", "middle", "ring", "pinky")
    bone_names = [names[f"{side}_{finger}_{i}"]
                  for finger in fingers for i in (1, 2, 3)]
    bones = rig.pose.bones
    original = {}
    for name in bone_names:
        pb = bones[name]
        original[name] = (pb.rotation_mode, pb.rotation_euler.copy(),
                          pb.rotation_quaternion.copy(), pb.matrix_basis.copy())

    origin = Vector(grip_world)
    axis = Vector(axis_world).normalized()

    def tip_data():
        bpy.context.view_layer.update()
        return {finger: (rig.matrix_world @ bones[names[f"{side}_{finger}_3"]].tail)
                for finger in fingers}

    baseline = tip_data()
    def scores(points):
        return {f: round(float(_axis_distance(p, origin, axis)), 6)
                for f, p in points.items()}

    baseline_distances = scores(baseline)
    options = []
    for sign in (1, -1):
        for finger, angles in FINGER_BENDS.items():
            for joint, bend in enumerate(angles, 1):
                pb = bones[names[f"{side}_{finger}_{joint}"]]
                pb.rotation_mode = "XYZ"
                pb.rotation_euler = (sign * bend * curl_scale, 0, 0)
        for joint, angles in enumerate(THUMB_BENDS, 1):
            pb = bones[names[f"{side}_thumb_{joint}"]]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = tuple(sign * a * curl_scale for a in angles)
        trial_points = tip_data()
        distances = scores(trial_points)
        # A finger should be close to the grip, but the axis is not the
        # outer skin surface. Do NOT optimize to distance zero.
        grip_score = sum(abs(distances[f] - radius - 0.012)
                         for f in ("index", "middle", "ring", "pinky"))
        # A thumb reaching too far from the opposite fingers is disfavored.
        grip_score += min(0.2, (trial_points["thumb"] -
                                trial_points["index"]).length) * 0.25
        options.append({"sign": sign, "score": float(grip_score),
                        "distances_m": distances})
    chosen = min(options, key=lambda entry: entry["score"])
    for finger, angles in FINGER_BENDS.items():
        for joint, bend in enumerate(angles, 1):
            pb = bones[names[f"{side}_{finger}_{joint}"]]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (chosen["sign"] * bend * curl_scale, 0, 0)
    for joint, angles in enumerate(THUMB_BENDS, 1):
        pb = bones[names[f"{side}_thumb_{joint}"]]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = tuple(chosen["sign"] * a * curl_scale for a in angles)
    final = tip_data()
    return {
        "name": "cylinder_finger_prior_v1",
        "selected_flexion_sign": chosen["sign"],
        "curl_scale": curl_scale,
        "baseline_axis_distances_m": baseline_distances,
        "final_axis_distances_m": scores(final),
        "trials": options,
        "radius_m": float(radius),
        "body_mesh_contact_verified": False,
        "joint_limits_verified": False,
        "collision_verified": False,
    }
