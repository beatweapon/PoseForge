"""Experimental anatomical pose prior for a two-finger pinch.

A prior is not an anatomical guarantee; it limits IK excursions instead of
allowing arbitrary CCD rotations to produce implausible fingers.
"""
import bpy
from mathutils import Vector
from rig import arm_chain, semantic_bones, wrist_bone_name
from grasp import add_card, card_face_targets, _measure
from ik import solve_hand_reach, solve_chain_to_point

# Signed bend angles chosen as a conservative first-pass pose template.
# These are *local* rotations in MPFB's coordinate frames; CI images determine
# whether the anatomical direction is correct.
PRIOR = {
    "thumb": ((-0.18, 0.10, 0.18), (-0.15, 0.0, 0.0), (-0.08, 0.0, 0.0)),
    "index": ((0.30, 0.0, 0.0), (0.28, 0.0, 0.0), (0.15, 0.0, 0.0)),
    "middle": ((0.42, 0.0, 0.0), (0.42, 0.0, 0.0), (0.24, 0.0, 0.0)),
    "ring": ((0.50, 0.0, 0.0), (0.50, 0.0, 0.0), (0.28, 0.0, 0.0)),
    "pinky": ((0.55, 0.0, 0.0), (0.53, 0.0, 0.0), (0.30, 0.0, 0.0)),
}


def apply_pinch_prior(rig, side):
    names = semantic_bones(rig.pose.bones.keys())
    applied = {}
    for finger, segments in PRIOR.items():
        for joint, angles in enumerate(segments, 1):
            key = f"{side}_{finger}_{joint}"
            bone_name = names.get(key)
            if bone_name is None:
                raise ValueError("Missing MPFB pinch bone: " + key)
            bone = rig.pose.bones[bone_name]
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = angles
            applied[bone_name] = list(angles)
    bpy.context.view_layer.update()
    return applied


def solve_card_with_prior(rig, spec):
    """Prior-first preview, with modest wrist and finger correction budgets."""
    side = spec["hand"]
    card_spec = spec["card"]
    card = add_card(card_spec["position"], card_spec["size"])
    targets = card_face_targets(card_spec["position"], card_spec["size"])
    names = semantic_bones(rig.pose.bones.keys())
    bones = rig.pose.bones
    applied = apply_pinch_prior(rig, side)
    wrist_name = wrist_bone_name(side)

    # Preserve the prior's relative shape, translating the hand with arm IK
    # rather than using unrestricted finger CCD to form the grip.
    thumb = rig.matrix_world @ bones[names[f"{side}_thumb_3"]].tail
    index = rig.matrix_world @ bones[names[f"{side}_index_3"]].tail
    midpoint = (thumb + index) / 2
    goal_midpoint = (targets["thumb"] + targets["index"]) / 2
    wrist_world = rig.matrix_world @ bones[wrist_name].head
    arm = solve_hand_reach(
        rig, side, wrist_name, arm_chain(side, bones.keys()),
        wrist_world + goal_midpoint - midpoint
    )

    # Apply limited correction: no more than 0.08 radians per joint step.
    # Keep only the better of the two options to avoid visibly destroying
    # a decent prior merely to achieve a sub-millimetre bone-tip error.
    prior_errors = _measure(rig, bones, names, side, targets)
    before = {name: bones[name].matrix.copy()
              for finger in ("thumb", "index")
              for j in (1, 2, 3)
              for name in [names[f"{side}_{finger}_{j}"]]}
    for finger in ("thumb", "index"):
        chain = [names[f"{side}_{finger}_{j}"] for j in (3, 2, 1)]
        solve_chain_to_point(
            rig, chain[0], chain, targets[finger],
            max_iterations=3, tolerance=0.008, max_step_angle=0.04
        )
    corrected = _measure(rig, bones, names, side, targets)
    # Penalize over-correction, not just positional error.
    def cost(rows):
        return sum(min(0.12, row["error_m"]) ** 2 for row in rows)
    if cost(corrected) >= cost(prior_errors):
        for name in sorted(before, key=lambda n: len(bones[n].parent_recursive)):
            bones[name].matrix = before[name]
            bpy.context.view_layer.update()
        corrected = _measure(rig, bones, names, side, targets)
        choice = "prior"
    else:
        choice = "bounded_correction"

    for row in corrected:
        row["sample_point"] = "bone_tail"
    arm["pose_prior"] = {
        "name": "pinch_v1",
        "strategy": "local_bend_template_then_bounded_ik",
        "chosen": choice,
        "max_step_angle_rad": 0.04,
        "max_iterations": 3,
        "initial_errors_m": [r["error_m"] for r in prior_errors],
        "final_errors_m": [r["error_m"] for r in corrected],
        "angles_rad": applied,
        "anatomical_joint_limits_verified": False,
    }
    return card, arm, corrected
