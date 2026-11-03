"""CLI entrypoint; Blender runs locally in background mode."""
import argparse
import json
import subprocess
from pathlib import Path

from .schema import load_config

def main(argv=None):
    parser = argparse.ArgumentParser(prog="poseforge")
    parser.add_argument("command", choices=("validate", "render-human", "render-pinch", "render-reach", "render-hand-reach", "render-grasp-card", "render-present-card",
                                            "inspect-model", "setup-mpfb", "create-human"))
    parser.add_argument("config", nargs="?")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if args.command == "setup-mpfb":
        command = [args.blender, "--online-mode", "--command", "extension", "install", "-s", "-e", "mpfb"]
    elif args.command == "create-human":
        if not args.config or Path(args.config).suffix.lower() != ".blend":
            parser.error("create-human requires a .blend output path")
        dest = Path(args.config).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        command = [args.blender, "--background", "--python",
                   str(Path(__file__).with_name("create_human.py")), "--", str(dest)]
    elif args.command == "inspect-model":
        if not args.config or not Path(args.config).is_file():
            parser.error("inspect-model requires an existing model")
        model = Path(args.config).resolve()
        if model.suffix.lower() not in (".blend", ".fbx", ".glb", ".gltf"):
            parser.error("Unsupported model type")
        report = Path(args.output).resolve() if args.output else model.with_name(model.stem + "_rig_report.json")
        report.parent.mkdir(parents=True, exist_ok=True)
        command = [args.blender, "--background", "--factory-startup", "--python",
                   str(Path(__file__).with_name("model_inspect.py")), "--", str(model), str(report)]
    else:
        if not args.config:
            parser.error("Configuration path required")
        try:
            config = load_config(args.config)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        if args.command == "render-pinch" and config["pose"]["action"] != "pinch_preview":
            parser.error("render-pinch requires pose.action=pinch_preview")
        if args.command == "render-reach" and config["pose"]["action"] != "reach":
            parser.error("render-reach requires pose.action=reach")
        if args.command == "render-hand-reach" and config["pose"]["action"] != "reach_hand":
            parser.error("render-hand-reach requires pose.action=reach_hand")
        if args.command == "render-grasp-card" and config["pose"]["action"] != "grasp_card":
            parser.error("render-grasp-card requires pose.action=grasp_card")
        if args.command == "render-present-card" and config["pose"]["action"] != "present_card":
            parser.error("render-present-card requires pose.action=present_card")
        if args.command == "render-human" and config["pose"]["action"] != "neutral":
            parser.error("render-human requires pose.action=neutral")
        if args.command == "validate":
            print("Valid:", args.config)
            return 0
        output = Path(config["output"])
        output.mkdir(parents=True, exist_ok=True)
        settings = output / "_poseforge_config.json"
        settings.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [args.blender, "--background", "--factory-startup", "--python",
                   str(Path(__file__).with_name("render_human.py")), "--", str(settings)]
    try:
        return subprocess.call(command)
    except FileNotFoundError:
        parser.error("Blender not found; specify --blender PATH")

if __name__ == "__main__":
    raise SystemExit(main())
