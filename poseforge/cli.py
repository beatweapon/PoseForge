"""Run PoseForge tools through Blender's local background process."""
import argparse
import json
import subprocess
from pathlib import Path

from .schema import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(prog="poseforge")
    parser.add_argument("command", choices=("validate", "render", "inspect-model", "setup-mpfb", "create-human"))
    parser.add_argument("config", nargs="?", help="Pose JSON, model path, or .blend output for create-human")
    parser.add_argument("--blender", default="blender", help="Blender executable or path")
    parser.add_argument("--output", help="Report JSON path for inspect-model")
    args = parser.parse_args(argv)

    if args.command == "setup-mpfb":
        command = [args.blender, "--command", "extension", "install", "-s", "-e", "mpfb"]
    elif args.command == "create-human":
        if not args.config:
            parser.error("create-human requires an output .blend file path")
        dest = Path(args.config).resolve()
        if dest.suffix.lower() != ".blend":
            parser.error("create-human output must end in .blend")
        dest.parent.mkdir(parents=True, exist_ok=True)
        script = Path(__file__).with_name("create_human.py")
        command = [args.blender, "--background", "--python", str(script), "--", str(dest)]
    elif args.command == "inspect-model":
        if not args.config:
            parser.error("inspect-model requires a model path")
        model = Path(args.config).resolve()
        if not model.is_file() or model.suffix.lower() not in (".blend", ".fbx", ".glb", ".gltf"):
            parser.error("inspect-model requires an existing .blend/.fbx/.glb/.gltf file")
        report = Path(args.output).resolve() if args.output else model.with_name(model.stem + "_rig_report.json")
        report.parent.mkdir(parents=True, exist_ok=True)
        script = Path(__file__).with_name("model_inspect.py")
        command = [args.blender, "--background", "--factory-startup", "--python", str(script),
                   "--", str(model), str(report)]
    else:
        if not args.config:
            parser.error(f"{args.command} requires a config path")
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
