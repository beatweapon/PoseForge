"""Blender-side read-only model inventory. No external downloads or pose changes."""
import json
import sys
from pathlib import Path

import bpy


def classify_bones(bone_names):
    """Suggest bone names by semantics, without assuming a particular rig naming scheme."""
    labels = {"head": [], "spine": [], "upper_arm": [], "forearm": [],
              "hand": [], "thumb": [], "index": [], "middle": [], "ring": [],
              "pinky": [], "thigh": [], "shin": [], "foot": []}
    aliases = {"head": ("head",), "spine": ("spine", "chest", "hips", "pelvis", "torso"),
               "upper_arm": ("upperarm", "upper_arm", "arm_upper"),
               "forearm": ("forearm", "lowerarm", "lower_arm"),
               "hand": ("hand", "wrist"), "thumb": ("thumb",), "index": ("index",),
               "middle": ("middle",), "ring": ("ring",), "pinky": ("pinky", "little"),
               "thigh": ("thigh", "upleg", "upper_leg"),
               "shin": ("shin", "calf", "lowerleg", "lower_leg"),
               "foot": ("foot", "ankle")}
    for name in bone_names:
        normalized = name.casefold().replace(" ", "").replace("-", "_")
        for label, tokens in aliases.items():
            if any(t in normalized for t in tokens):
                labels[label].append(name)
    return labels


def main():
    if "--" not in sys.argv or len(sys.argv) - sys.argv.index("--") != 3:
        raise SystemExit("Usage: blender --background --python model_inspect.py -- MODEL REPORT")
    model_path, report_path = map(Path, sys.argv[sys.argv.index("--") + 1:])
    suffix = model_path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(model_path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(model_path))
    elif suffix in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(model_path))
    else:
        raise ValueError(f"Unsupported model format: {suffix}")
    armatures = []
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        bones = list(obj.data.bones)
        names = [bone.name for bone in bones]
        groups = classify_bones(names)
        armatures.append({
            "object": obj.name,
            "bone_count": len(names),
            "bones": [{"name": b.name, "parent": b.parent.name if b.parent else None,
                       "head_local": [round(float(n), 5) for n in b.head_local],
                       "tail_local": [round(float(n), 5) for n in b.tail_local]} for b in bones],
            "suggested_bones": groups,
            "has_thumb_and_index_candidates": bool(groups["thumb"] and groups["index"]),
        })
    result = {
        "source": str(model_path),
        "object_count": len(bpy.data.objects),
        "mesh_count": sum(obj.type == "MESH" for obj in bpy.data.objects),
        "armatures": armatures,
        "note": "Bone-name matches are heuristics, not verified rig capabilities or correct handedness.",
    }
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PoseForge rig inventory: {report_path}")
    if not armatures:
        print("WARNING: No armature found. This model is not ready for articulated poses.")


if __name__ == "__main__":
    main()
