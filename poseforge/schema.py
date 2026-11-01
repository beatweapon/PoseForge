"""Input validation; no Blender dependency."""
import json
from pathlib import Path

VIEWS = ("front", "back", "left", "right", "three_quarter", "hand_closeup")


def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    if data.get("model") != "humanoid":
        raise ValueError("Only model=humanoid is supported")
    pose = data.get("pose")
    if not isinstance(pose, dict) or pose.get("action") != "pinch":
        raise ValueError("Only pose.action=pinch is implemented")
    expected = {"hand": "right", "object": "card", "objectPoint": "top_right_corner", "fingers": ["thumb", "index"]}
    for key, value in expected.items():
        if pose.get(key) != value:
            raise ValueError(f"Unsupported pose.{key}: {pose.get(key)!r}")
    cameras = data.get("cameras")
    if not isinstance(cameras, list) or not cameras or len(cameras) != len(set(cameras)):
        raise ValueError("cameras must be a nonempty list without duplicates")
    if any(c not in VIEWS for c in cameras):
        raise ValueError(f"Unknown camera; valid choices: {', '.join(VIEWS)}")
    render = data.get("render")
    if not isinstance(render, dict):
        raise ValueError("render must be an object")
    for key in ("width", "height"):
        if type(render.get(key)) is not int or not 64 <= render[key] <= 4096:
            raise ValueError(f"render.{key} must be integer 64..4096")
    if type(render.get("transparent")) is not bool:
        raise ValueError("render.transparent must be boolean")
    output = data.get("output")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output must be a directory string")
    data["output"] = str((path.parent / output).resolve())
    return data
