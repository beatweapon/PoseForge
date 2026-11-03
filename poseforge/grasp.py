"""Card grasp preview: arm placement followed by two positional fingertip solves.

This tests bone-tip proximity, NOT skin contact or collision-free grasping.
"""
import bpy
from mathutils import Vector
from rig import arm_chain, wrist_bone_name, semantic_bones
from ik import solve_hand_reach, solve_tip

def card_face_targets(position, size, corner="top_right", clearance=0.002):
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

def solve_card_grasp(rig, spec):
    side = spec["hand"]
    targets = card_face_targets(spec["card"]["position"], spec["card"]["size"])
    card = add_card(spec["card"]["position"], spec["card"]["size"])
    names = semantic_bones(rig.pose.bones.keys())
    bones = rig.pose.bones
    wrist = wrist_bone_name(side)
    finger_tips = [names[f"{side}_{f}_3"] for f in ("thumb", "index")]
    bpy.context.view_layer.update()
    # Move the wrist by the current averaged fingertip offset before finger fitting.
    middle = sum((bones[n].tail.copy() for n in finger_tips), Vector()) / 2
    wrist_position = bones[wrist].head.copy()
    target_middle = (targets["thumb"] + targets["index"]) / 2
    desired_wrist = rig.matrix_world @ (wrist_position +
                    (rig.matrix_world.inverted() @ target_middle - middle))
    arm = solve_hand_reach(rig, side, wrist, arm_chain(side, bones.keys()), desired_wrist)
    results = []
    for finger in ("thumb", "index"):
        chain = [names[f"{side}_{finger}_{j}"] for j in (3, 2, 1)]
        result = solve_tip(rig, chain, targets[finger])
        result["effector"] = f"{side}_{finger}"
        result["face"] = "front" if finger == "thumb" else "back"
        results.append(result)
    # First finger may move when subsequent solves are applied; report FINAL positions.
    bpy.context.view_layer.update()
    for result in results:
        finger = result["effector"].split("_", 1)[1]
        actual = rig.matrix_world @ bones[names[f"{side}_{finger}_3"]].tail
        target = targets[finger]
        result["actual"] = [float(v) for v in actual]
        result["error_m"] = round((actual - target).length, 6)
        result["converged"] = result["error_m"] <= 0.003
        result["delta_world"] = [float(v) for v in target - actual]
    return card, arm, results
