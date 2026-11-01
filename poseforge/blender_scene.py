"""Executed inside Blender; procedural prototype, NOT an articulated humanoid rig."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# All locations are world-space. The card lies in the XZ plane (its front faces -Y).
CARD_CENTER = Vector((0.62, -0.05, 1.40))
CARD_WIDTH = 0.30
CARD_HEIGHT = 0.43
CARD_THICKNESS = 0.008
CORNER = CARD_CENTER + Vector((CARD_WIDTH / 2, 0, CARD_HEIGHT / 2))


def material(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1.0)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1.0)
    return m


def joint(name, point, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=radius, location=point)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def segment(name, a, b, radius, mat):
    midpoint = (Vector(a) + Vector(b)) / 2
    delta = Vector(b) - Vector(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius, depth=delta.length, location=midpoint)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    joint(name + "_end", b, radius, mat)


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    skin = material("Proxy grey", (0.66, 0.67, 0.69))
    blue = material("Card FRONT blue", (0.05, 0.25, 0.85))
    orange = material("Card BACK orange", (0.98, 0.38, 0.09))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.03))
    torso = bpy.context.object
    torso.name = "Torso proxy"
    torso.dimensions = (0.48, 0.22, 0.80)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    torso.data.materials.append(skin)
    joint("Head", (0, 0, 1.66), 0.16, skin)
    segment("Left upper arm", (-0.24, 0, 1.32), (-0.39, -0.04, 0.98), 0.075, skin)
    segment("Left forearm", (-0.39, -0.04, 0.98), (-0.30, -0.12, 0.75), 0.055, skin)
    segment("Right upper arm", (0.24, 0, 1.32), (0.44, -0.05, 1.18), 0.075, skin)
    segment("Right forearm", (0.44, -0.05, 1.18), (0.58, -0.13, 1.48), 0.052, skin)
    joint("Right palm", (0.60, -0.11, 1.52), 0.067, skin)
    # The simple fingertip proxies touch the front and back card faces at the same corner.
    # This is *not* IK, and does not establish a collision-free human grip.
    contact = CORNER + Vector((-0.018, 0, -0.018))
    thumb_tip = contact + Vector((0, -CARD_THICKNESS / 2 - 0.012, 0))
    index_tip = contact + Vector((0, CARD_THICKNESS / 2 + 0.012, 0))
    segment("Thumb proxy", (0.57, -0.15, 1.53), thumb_tip, 0.012, skin)
    segment("Index proxy", (0.63, -0.06, 1.56), index_tip, 0.012, skin)
    # Card local dimensions (X,Y,Z); blue on -Y, orange on +Y.
    bpy.ops.mesh.primitive_cube_add(size=1, location=CARD_CENTER)
    card = bpy.context.object
    card.name = "Card"
    card.dimensions = (CARD_WIDTH, CARD_THICKNESS, CARD_HEIGHT)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    card.data.materials.append(blue)
    card.data.materials.append(orange)
    for face in card.data.polygons:
        face.material_index = 0 if face.normal.y < -0.5 else 1
    return thumb_tip, index_tip, contact


def camera_at(name, location, target, scale):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.name = "Camera_" + name
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    return cam


def main():
    if "--" not in sys.argv:
        raise SystemExit("Missing JSON config after --")
    config = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    thumb, index, target = build()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = config["render"]["width"]
    scene.render.resolution_y = config["render"]["height"]
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = config["render"]["transparent"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    world = bpy.data.worlds.new("World") if scene.world is None else scene.world
    scene.world = world
    world.color = (0.6, 0.6, 0.6)
    bpy.ops.object.light_add(type="AREA", location=(1.0, -2.0, 3.0))
    bpy.context.object.data.energy = 550
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 4.0
    viewpoints = {
        "front": ((0, -4, 1.2), (0, 0, 1.1), 2.35),
        "back": ((0, 4, 1.2), (0, 0, 1.1), 2.35),
        "left": ((-4, 0, 1.2), (0, 0, 1.1), 2.35),
        "right": ((4, 0, 1.2), (0, 0, 1.1), 2.35),
        "three_quarter": ((3, -3, 2.1), (0, 0, 1.1), 2.35),
        "hand_closeup": ((1.0, -1.5, 1.9), tuple(target), 0.65),
    }
    output = Path(config["output"])
    output.mkdir(parents=True, exist_ok=True)
    for view in config["cameras"]:
        location, look_at, scale = viewpoints[view]
        scene.camera = camera_at(view, location, look_at, scale)
        scene.render.filepath = str(output / f"{view}.png")
        bpy.ops.render.render(write_still=True)
    # Distance is from each fingertip center to its intended surface contact.
    # It is not mesh penetration testing.
    distances = {
        "thumb_surface_gap_m": abs(thumb.y - (target.y - CARD_THICKNESS / 2)) - 0.012,
        "index_surface_gap_m": abs(index.y - (target.y + CARD_THICKNESS / 2)) - 0.012,
    }
    report = {
        "status": "prototype_only",
        "views": config["cameras"],
        "contact": {k: round(v, 6) for k, v in distances.items()},
        "limitations": ["proxy geometry, not skinned rig", "no IK", "no mesh collision/penetration checks"],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PoseForge rendered:", ", ".join(config["cameras"]))


if __name__ == "__main__":
    main()
