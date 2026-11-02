"""Validate real human rendering configuration without Blender."""
import json
from pathlib import Path

VIEWS = ("front", "back", "left", "right", "three_quarter", "hand_closeup")

def load_config(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be an object")
    model = data.get("model")
    if not isinstance(model, dict) or model.get("type") != "mpfb":
        raise ValueError("model.type must be mpfb")
    source = model.get("source")
    if not isinstance(source, str) or not source.strip() or Path(source).suffix.lower() != ".blend":
        raise ValueError("model.source must be a .blend path")
    # Paths are resolved relative to repository root via the config parent when called from examples/.
    source_path = (path.parent / source).resolve()
    if not source_path.is_file():
        raise ValueError(f"Model file not found: {source_path}")
    data["model"]["source"] = str(source_path)
    pose = data.get("pose", {"action": "neutral"})
    if not isinstance(pose, dict) or pose.get("action") not in ("neutral", "pinch_preview"):
        raise ValueError("Supported actions: neutral, pinch_preview")
    if pose["action"] == "pinch_preview":
        required = {"hand": "right", "object": "card"}
        if any(pose.get(k) != v for k, v in required.items()):
            raise ValueError("pinch_preview requires right hand and card")
    data["pose"] = pose
    cameras = data.get("cameras")
    if (not isinstance(cameras, list) or not cameras or
            any(not isinstance(c, str) or c not in VIEWS for c in cameras) or
            len(cameras) != len(set(cameras))):
        raise ValueError("cameras must be a nonempty list of unique supported views")
    render = data.get("render")
    if not isinstance(render, dict):
        raise ValueError("render must be an object")
    for key in ("width", "height"):
        if type(render.get(key)) is not int or not 64 <= render[key] <= 4096:
            raise ValueError(f"render.{key} must be integer 64..4096")
    if type(render.get("transparent")) is not bool:
        raise ValueError("render.transparent must be bool")
    output = data.get("output")
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output must be directory string")
    data["output"] = str((path.parent / output).resolve())
    return data
