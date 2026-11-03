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
    if not isinstance(pose, dict) or pose.get("action") not in ("neutral", "pinch_preview", "reach", "reach_hand", "grasp_card"):
        raise ValueError("Supported actions: neutral, pinch_preview, reach, reach_hand, grasp_card")
    if pose["action"] == "pinch_preview":
        required = {"hand": "right", "object": "card"}
        if any(pose.get(k) != v for k, v in required.items()):
            raise ValueError("pinch_preview requires right hand and card")
    if pose["action"] == "reach":
        targets = pose.get("targets")
        if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
            raise ValueError("reach.targets requires 1..10 targets")
        seen = set()
        for target in targets:
            if not isinstance(target, dict):
                raise ValueError("Each target must be an object")
            name = target.get("effector")
            valid = {f"{side}_{finger}" for side in ("left", "right")
                     for finger in ("thumb", "index", "middle", "ring", "pinky")}
            if name not in valid or name in seen:
                raise ValueError("Unknown or duplicate effector")
            seen.add(name)
            pos = target.get("position")
            if (not isinstance(pos, list) or len(pos) != 3 or
                    any(type(v) not in (float, int) or not -10 <= v <= 10 for v in pos)):
                raise ValueError("target.position must be three finite coordinates in meters")
    if pose["action"] == "reach_hand":
        if pose.get("hand") not in ("left", "right"):
            raise ValueError("reach_hand.hand must be left or right")
        position = pose.get("target_position")
        if (not isinstance(position, list) or len(position) != 3 or
                any(type(v) not in (int, float) or not -10 <= v <= 10 for v in position)):
            raise ValueError("reach_hand.target_position requires three finite numbers in meters")
    if pose["action"] == "grasp_card":
        if pose.get("hand") not in ("left", "right"):
            raise ValueError("grasp_card.hand must be left or right")
        card = pose.get("card")
        if not isinstance(card, dict):
            raise ValueError("grasp_card.card must be an object")
        for key in ("position", "size"):
            xyz = card.get(key)
            if (not isinstance(xyz, list) or len(xyz) != 3 or
                    any(type(v) not in (int, float) or not -10 <= v <= 10
                        for v in xyz)):
                raise ValueError(f"grasp_card.card.{key} must be three finite numbers")
        if any(not 0.001 <= v <= 1.0 for v in card["size"]):
            raise ValueError("grasp_card.card.size must be 0.001..1 m")
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
