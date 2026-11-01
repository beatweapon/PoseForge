"""Run from a normal Python installation; Blender is a subprocess."""
import argparse
import json
import subprocess
from pathlib import Path
from .schema import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(prog="poseforge")
    parser.add_argument("command", choices=("validate", "render"))
    parser.add_argument("config")
    parser.add_argument("--blender", default="blender", help="Blender executable or path")
    args = parser.parse_args(argv)
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
