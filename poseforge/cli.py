"""Run PoseForge tools through Blender's local background process."""
import argparse
import json
import subprocess
from pathlib import Path

from .schema import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(prog="poseforge")
    parser.add_argument("command", choices=("validate", "render", "inspect-model"))
    parser.add_argument("config", help="Pose JSON, or model file for inspect-model")
    parser.add_argument("--blender", default="blender", help="Blender executable or path")
    parser.add_argument("--output", help="Report JSON path for inspect-model")
    args = parser.parse_args(argv)

    if args.command == "inspect-model":
        model = Path(args.config).resolve()
        if not model.is_file() or model.suffix.lower() not in (".blend", ".fbx", ".glb", ".gltf"):
            parser.error("inspect-model requires an existing .blend/.fbx/.glb/.gltf file")
        report = Path(args.output).resolve() if args.output else model.with_name(model.stem + "_rig_report.json")
        report.parent.mkdir(parents=True, exist_ok=True)
        script = Path(__file__).with_name("model_inspect.py")
        command = [args.blender, "--background", "--factory-startup", "--python", str(script),
                   "--", str(model), str(report)]
    else:
        try:
            config = load_config(args.config)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if args.command == "validate":
            print("Valid:", args.config)
            return 0
        output = Path(config["output"])
        output.mkdir(parents=True, exist_ok=True)
        normalized = output / "_poseforge_config.json"
        normalized.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        script = Path(__file__).with_name("blender_scene.py")
        command = [args.blender, "--background", "--factory-startup", "--python", str(script), "--", str(normalized)]
    try:
        return subprocess.call(command)
    except FileNotFoundError:
        parser.error("Blender executable not found. Supply --blender PATH.")


if __name__ == "__main__":
    raise SystemExit(main())
