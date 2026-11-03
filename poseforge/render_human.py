"""Render an existing MPFB .blend. Preview posing is NOT contact-solved."""
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Blender child modules reside alongside this script, not on package sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rig import semantic_bones, arm_chain, wrist_bone_name
from ik import solve_tip, solve_hand_reach
from grasp import solve_card_grasp, refine_skin_grasp, card_face_targets, _measure
from contact import inspect_card_skin
from presentation import resolve_card_presentation, measure_arm_posture
from pose_prior import solve_card_with_prior
from bow import hold_bow
from staff import hold_staff


def look_at(cam, point):
    cam.rotation_euler = (Vector(point) - cam.location).to_track_quat("-Z", "Y").to_euler()


def preview_pose(rig):
    bones = rig.pose.bones
    mapping = semantic_bones(bones.keys())
    needed = ("right_upper_arm", "right_forearm", "right_wrist",
              "right_thumb_1", "right_index_1")
    missing = [key for key in needed if key not in mapping]
    if missing:
        raise RuntimeError("Missing MPFB pose bones: " + ", ".join(missing))
    # This is a visual feasibility preview, NOT an IK solution or a correct grip.
    angles = {"right_upper_arm": (0, 0, -0.45),
              "right_forearm": (0.30, 0, -0.20), "right_wrist": (0.05, 0.0, 0.0),
              "right_thumb_1": (0, 0.25, 0.15), "right_thumb_2": (0, 0.30, 0),
              "right_index_1": (0.2, 0, 0), "right_index_2": (0.25, 0, 0)}
    for semantic, euler in angles.items():
        name = mapping.get(semantic)
        if name:
            bone = bones[name]
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = euler
    bpy.context.view_layer.update()
    fingertip = rig.matrix_world @ bones[mapping["right_index_1"]].tail
    bpy.ops.mesh.primitive_cube_add(size=1, location=fingertip + Vector((0, -0.045, -0.09)))
    card = bpy.context.object
    card.name = "Card_preview_NOT_contact_solved"
    card.dimensions = (0.22, 0.007, 0.33)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def main():
    if "--" not in sys.argv:
        raise ValueError("Missing configuration")
    cfg = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=cfg["model"]["source"])
    scene = bpy.context.scene
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError(f"Expected one armature, got {len(rigs)}")
    rig = rigs[0]
    # Backwards compatibility for human.blend created before startup cleanup:
    # remove ONLY the recognizable, unmodified Blender startup cube.
    for obj in list(bpy.data.objects):
        if (obj.type == "MESH" and obj.name == "Cube" and obj.parent is None
                and len(obj.data.vertices) == 8 and not obj.modifiers
                and all(abs(d - 2.0) < 0.001 for d in obj.dimensions)):
            bpy.data.objects.remove(obj, do_unlink=True)
    reach_results = []
    grasp_arm = None
    grasp_card = None
    presented_card = None
    bow_prop = None
    if cfg["pose"]["action"] == "pinch_preview":
        preview_pose(rig)
    elif cfg["pose"]["action"] == "reach":
        mapping = semantic_bones(rig.pose.bones.keys())
        for target in cfg["pose"]["targets"]:
            side, finger = target["effector"].split("_", 1)
            chain = [mapping[f"{side}_{finger}_{joint}"] for joint in (3, 2, 1)]
            result = solve_tip(rig, chain, target["position"])
            result["effector"] = target["effector"]
            reach_results.append(result)
    elif cfg["pose"]["action"] == "reach_hand":
        side = cfg["pose"]["hand"]
        chain = arm_chain(side, rig.pose.bones.keys())
        result = solve_hand_reach(rig, side, wrist_bone_name(side), chain,
                                  cfg["pose"]["target_position"])
        reach_results.append(result)
    elif cfg["pose"]["action"] == "grasp_card":
        grasp_card, grasp_arm, reach_results = solve_card_grasp(rig, cfg["pose"])
    elif cfg["pose"]["action"] == "present_card":
        spec = cfg["pose"]
        bpy.context.view_layer.update()
        presented_card = resolve_card_presentation(
            rig, spec["hand"], spec["size"], spec["presentation"])
        grasp_card, grasp_arm, reach_results = solve_card_with_prior(
            rig, {"hand": spec["hand"], "card": presented_card})
    elif cfg["pose"]["action"] == "hold_bow":
        bow_prop, reach_results = hold_bow(rig, cfg["pose"])
    elif cfg["pose"]["action"] == "hold_staff":
        bow_prop, reach_results = hold_staff(rig, cfg["pose"])
    mesh_objs = [o for o in bpy.data.objects
                 if o.type == "MESH" and o.name not in ("Card_preview_NOT_contact_solved", "Card_grasp_preview")
                 and (o.parent == rig or any(m.type == "ARMATURE" and m.object == rig
                                            for m in o.modifiers))]
    if not mesh_objs:
        raise RuntimeError("No body mesh in model")
    skin_contact = None
    grasp_skin_search = None
    if grasp_card is not None:
        card_spec = presented_card or cfg["pose"]["card"]
        side = cfg["pose"]["hand"]
        mapping = semantic_bones(rig.pose.bones.keys())
        targets = card_face_targets(
            card_spec["position"], card_spec["size"])
        if presented_card is None:
            grasp_skin_search = refine_skin_grasp(
                rig, grasp_card, side, mesh_objs, targets)
        reach_results = _measure(rig, rig.pose.bones, mapping, side, targets)
        for row in reach_results:
            row["sample_point"] = "bone_tail"
        skin_contact = inspect_card_skin(
            rig, grasp_card, side, mapping, mesh_objs)
    points = [o.matrix_world @ Vector(corner) for o in mesh_objs for corner in o.bound_box]
    low = Vector((min(p[i] for p in points) for i in range(3)))
    high = Vector((max(p[i] for p in points) for i in range(3)))
    center = (low + high) / 2
    size = max(high.z - low.z, high.x - low.x, high.y - low.y)
    wrist = rig.pose.bones.get("wrist.R")
    # PoseBone.head is evaluated in armature space, unlike the data bone's rest head.
    bpy.context.view_layer.update()
    close_target = rig.matrix_world @ wrist.head if wrist else center
    if reach_results:
        close_target = Vector(reach_results[0]["actual"])
    if grasp_card is not None:
        close_target = grasp_card.matrix_world.translation
    if bow_prop is not None:
        close_target = Vector(bow_prop["grips"]["right"])
    if cfg["pose"]["action"] == "pinch_preview":
        card = bpy.data.objects.get("Card_preview_NOT_contact_solved")
        if card is not None:
            close_target = card.matrix_world.translation
    scene.render.engine = os.environ.get("POSEFORGE_RENDER_ENGINE", "BLENDER_EEVEE")
    scene.render.resolution_x = cfg["render"]["width"]
    scene.render.resolution_y = cfg["render"]["height"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = cfg["render"]["transparent"]
    for obj in list(bpy.data.objects):
        if obj.type == "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)
    if not any(obj.type == "LIGHT" for obj in bpy.data.objects):
        bpy.ops.object.light_add(type="AREA", location=center + Vector((1, -2, 3)))
        bpy.context.object.data.energy = 650
        bpy.context.object.data.size = 4
    output = Path(cfg["output"])
    output.mkdir(parents=True, exist_ok=True)
    views = {"front": (0, -1, 0), "back": (0, 1, 0),
             "left": (-1, 0, 0), "right": (1, 0, 0),
             "three_quarter": (1, -1, 0.35), "hand_closeup": (0.7, -1, 0.4)}
    for name in cfg["cameras"]:
        direction = Vector(views[name]).normalized()
        target = close_target if name == "hand_closeup" else center
        distance = max(size * 2.5, 2)
        bpy.ops.object.camera_add(location=target + direction * distance)
        cam = bpy.context.object
        cam.name = "PoseForge_" + name
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = max(size * 1.18, 0.5) if name != "hand_closeup" else 0.38
        look_at(cam, target)
        scene.camera = cam
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
    action = cfg["pose"]["action"]
    status = ("neutral" if action == "neutral" else
              "ik_converged" if action in ("reach", "reach_hand") and all(r["converged"] for r in reach_results)
              else "ik_unconverged" if action in ("reach", "reach_hand") else "pose_preview_only")
    if action in ("grasp_card", "present_card"):
        status = "grasp_preview_within_tolerance" if all(r["converged"] for r in reach_results) else "grasp_preview_unconverged"
    skin_quality = None
    if skin_contact is not None:
        fingers = skin_contact.get("fingers", {})
        skin_quality = (
            "intersection_evidence" if any(
                item.get("has_penetration_evidence")
                for item in fingers.values()) else "not_verified"
        )
    if grasp_card is not None and skin_quality == "intersection_evidence":
        # Do not report a 'successful grasp' solely from tip IK convergence.
        status = "grasp_preview_intersection_evidence"
    posture = (measure_arm_posture(rig, cfg["pose"]["hand"])
               if grasp_card is not None else None)
    if bow_prop is not None:
        status = "bilateral_prop_reference" if all(r["converged"] for r in reach_results) else "bilateral_prop_wrist_unconverged"
    report = {"status": status, "skin_quality": skin_quality,
              "bow_prop": bow_prop,
              "arm_posture": posture, "presentation": presented_card,
              "targets": reach_results,
              "arm_reach": grasp_arm, "card": presented_card or cfg["pose"].get("card"),
              "skin_contact_diagnostics": skin_contact,
              "skin_search": grasp_skin_search,
              "pose_action": cfg["pose"]["action"], "contact_verified": False,
              "collision_verified": False, "views": cfg["cameras"],
              "model": cfg["model"]["source"]}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
