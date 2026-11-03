"""Actor-relative display-card placement.

The semantic instruction is independent of a particular humanoid's size:
shoulder positions are taken from the evaluated rig. Coordinates follow the
current PoseForge convention (front camera looks along +Y).
"""
from mathutils import Vector


def resolve_card_presentation(rig, side, size, presentation):
    """Make a card placement around the upper torso, in world coordinates."""
    if presentation != "chest_display":
        raise ValueError("Unsupported card presentation")
    suffix = "R" if side == "right" else "L"
    bone_name = "upperarm01." + suffix
    bone = rig.pose.bones.get(bone_name)
    if bone is None:
        raise ValueError("Missing shoulder bone: " + bone_name)
    shoulder = rig.matrix_world @ bone.head
    # Place the card slightly in front of the chest, just below shoulder level.
    # Side is kept explicit; no absolute world-coordinate guesses in JSON.
    right_sign = -1.0 if side == "right" else 1.0
    position = shoulder + Vector((right_sign * 0.05, -0.24, -0.13))
    return {
        "position": [round(float(v), 5) for v in position],
        "size": list(size),
        "placement": "upper_torso_relative",
        "shoulder_world": [float(v) for v in shoulder],
        "presentation": presentation,
    }


def measure_arm_posture(rig, side):
    """Report simple elbow-down and elbow bend evidence (not a limit solver)."""
    suffix = "R" if side == "right" else "L"
    bones = rig.pose.bones
    arm = bones["upperarm01." + suffix]
    forearm = bones["lowerarm01." + suffix]
    wrist = bones["wrist." + suffix]
    shoulder = rig.matrix_world @ arm.head
    elbow = rig.matrix_world @ forearm.head
    hand = rig.matrix_world @ wrist.head
    upper = shoulder - elbow
    lower = hand - elbow
    angle = upper.angle(lower) if upper.length > 1e-6 and lower.length > 1e-6 else 0.0
    return {
        "shoulder_world": [float(v) for v in shoulder],
        "elbow_world": [float(v) for v in elbow],
        "wrist_world": [float(v) for v in hand],
        "elbow_below_shoulder": bool(elbow.z < shoulder.z),
        "elbow_angle_deg": round(float(__import__("math").degrees(angle)), 2),
        "wrist_above_waist_approx": bool(hand.z > shoulder.z - 0.4),
        "is_anatomical_joint_limit_verified": False,
    }
