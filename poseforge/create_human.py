"""Generate an MPFB full-body mesh with a built-in rig in Blender.

Uses installed MPFB service APIs, not GUI automation. Fails rather than emitting an unrigged model.
"""
import importlib
import json
import sys
from pathlib import Path

import bpy


def service():
    # Installed Blender extensions normally use this module namespace.
    for module in ("bl_ext.blender_org.mpfb.services.humanservice", "mpfb.services.humanservice"):
        try:
            return importlib.import_module(module).HumanService
        except (ImportError, AttributeError):
            continue
    raise RuntimeError("MPFB is not importable. Run setup-mpfb and check Blender extension activation.")


def main():
    if "--" not in sys.argv:
        raise ValueError("Missing output .blend path")
    dest = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    svc = service()
    human = svc.create_human()
    if human is None or human.type != "MESH":
        raise RuntimeError("MPFB did not create a human mesh")
    # MPFB ships a built-in 'default' rig; validate the actual armature below.
    rig = svc.add_builtin_rig(human, "default")
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError("MPFB did not produce an armature (default rig unavailable?)")
    bones = [b.name for b in rig.data.bones]
    # MPFB's default rig uses numeric finger chains: finger1 = thumb, finger2 = index.
    # Confirm all three phalange bones on BOTH hands, rather than matching English labels.
    required = [f"finger{finger}-{joint}.{side}"
                for side in ("L", "R") for finger in range(1, 6)
                for joint in range(1, 4)]
    missing = sorted(set(required) - set(bones))
    if missing:
        raise RuntimeError(
            "MPFB default rig has incomplete finger chains: "
            + ", ".join(missing)
            + "\\nAvailable bone names: " + ", ".join(bones)
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest))
    info = {"file": str(dest), "human": human.name, "rig": rig.name, "bone_count": len(bones),
            "bones": bones, "finger_naming": "MPFB default: finger1=thumb, finger2=index, finger3=middle, finger4=ring, finger5=pinky; joints 1..3; .L/.R", "note": "Generated, not posed. Pinch IK is not implemented."}
    dest.with_suffix(".json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PoseForge created human:", dest)


if __name__ == "__main__":
    main()
