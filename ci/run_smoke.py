"""Headless CI smoke checks for the existing user-facing PoseForge CLI.

Generate low-resolution renders; preserve per-scene diagnostics even on failure.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "ci"
SCENES = (
    ("human_neutral.json", "render-human", "neutral"),
    ("human_hand_reach.json", "render-hand-reach", "hand_reach"),
    ("human_finger_reach.json", "render-reach", "finger_reach"),
    ("human_card_pinch.json", "render-pinch", "pinch_preview"),
    ("human_card_grasp.json", "render-grasp-card", "card_grasp"),
)
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    summary = ["# PoseForge Blender smoke test", "",
               "The render pass checks command success and output images, not anatomical validity.",
               "", "| Scenario | Result | IK error (m) |", "|---|---|---|"]
    failures = []
    for sample, cmd, scene_name in SCENES:
        config = json.loads((ROOT / "examples" / sample).read_text(encoding="utf-8"))
        config["model"]["source"] = str((ROOT / "assets" / "human.blend").resolve())
        config["output"] = str(OUT / scene_name)
        config["cameras"] = ["front", "three_quarter", "hand_closeup"]
        config["render"].update(width=512, height=512)
        config_file = OUT / (scene_name + ".json")
        config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        command = [sys.executable, "-m", "poseforge.cli", cmd,
                   str(config_file), "--blender", args.blender]
        result = subprocess.run(command, cwd=ROOT, check=False)
        scene_dir = OUT / scene_name
        problems = []
        if result.returncode != 0:
            problems.append("exit=" + str(result.returncode))
        for view in config["cameras"]:
            image = scene_dir / (view + ".png")
            if not image.is_file() or image.open("rb").read(8) != PNG_HEADER:
                problems.append("missing or invalid PNG: " + view)
        report_file = scene_dir / "report.json"
        report = None
        if not report_file.exists():
            problems.append("missing report.json")
        else:
            try:
                report = json.loads(report_file.read_text(encoding="utf-8"))
                if report.get("pose_action") != config["pose"]["action"]:
                    problems.append("report action mismatch")
            except (ValueError, OSError) as exc:
                problems.append("invalid report: " + str(exc))
        errors = [t["error_m"] for t in report.get("targets", [])] if report else []
        if scene_name == "card_grasp" and report:
            if len(report.get("targets", [])) != 2 or not report.get("arm_reach"):
                problems.append("grasp diagnostics missing")
        error_text = ", ".join(map(str, errors)) if errors else "—"
        if problems:
            failures.append(scene_name + ": " + "; ".join(problems))
        summary.append("| " + scene_name + " | " +
                       ("FAIL: " + "; ".join(problems) if problems else "PASS") +
                       " | " + error_text + " |")
    summary += ["", "CCD convergence does not guarantee valid joint limits or contact.",
                "Artifacts: PNG views and report.json for each scenario.", ""]
    (OUT / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary), flush=True)
    if failures:
        raise SystemExit("Smoke-test failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
