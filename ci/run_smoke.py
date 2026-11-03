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
    ("human_card_present.json", "render-present-card", "card_present"),
    ("human_bow_hold.json", "render-hold-bow", "bow_hold"),
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
    geometry_notes = []
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
        if scene_name == "card_grasp" and report:
            if not errors or max(errors) > 0.005:
                problems.append("bone-tip grasp error exceeds 5 mm regression limit")
            diagnostics = report.get("skin_contact_diagnostics") or {}
            fingers = diagnostics.get("fingers", {})
            for finger in ("thumb", "index"):
                item = fingers.get(finger, {})
                if not item.get("sample_count") or not item.get("nearest_skin_vertex"):
                    problems.append(f"missing posed skin samples for {finger}")
        if scene_name == "card_grasp" and report:
            skin_search = report.get("skin_search") or {}
            if not skin_search.get("trials"):
                problems.append("missing skin-aware search trials")
            elif skin_search["final_score"] > skin_search["baseline_score"] + 1e-6:
                problems.append("skin-aware search regressed its objective")
            geometry_notes.append(
                f"- skin search: {skin_search.get('status')} "
                f"score {skin_search.get('baseline_score')} -> "
                f"{skin_search.get('final_score')}; sampled intersections "
                f"{skin_search.get('baseline_inside')} -> {skin_search.get('final_inside')}")
            fingers = (report.get("skin_contact_diagnostics") or {}).get("fingers", {})
            for finger in ("thumb", "index"):
                data = fingers.get(finger) or {}
                count = data.get("sampled_vertices_inside_card")
                nearest = (data.get("nearest_skin_vertex") or {}).get("distance_m")
                geometry_notes.append(
                    f"- {finger}: mesh vertices inside card = {count}, "
                    f"nearest sampled skin vertex to face target = {nearest} m")
        if scene_name == "card_present" and report:
            pose = report.get("presentation") or {}
            posture = report.get("arm_posture") or {}
            if pose.get("presentation") != "chest_display" or not posture:
                problems.append("semantic placement or arm posture report missing")
            prior = (report.get("arm_reach") or {}).get("pose_prior", {})
            if prior.get("name") != "pinch_v1":
                problems.append("missing pinch pose prior report")
            if not errors or max(errors) > 0.03:
                problems.append("semantic pinch exceeds 30mm bone-tip regression threshold")
            if not posture.get("elbow_below_shoulder"):
                problems.append("elbow should remain below shoulder")
            geometry_notes.append(
                "- pose prior: " + str(prior.get("chosen"))
                + ", tip errors=" + str(prior.get("final_errors_m")))
            fingers = (report.get("skin_contact_diagnostics") or {}).get("fingers", {})
            if any(not (fingers.get(f) or {}).get("sample_count") for f in ("thumb", "index")):
                problems.append("missing finger skin samples")
            geometry_notes.append(
                "- semantic presentation: elbow_below_shoulder="
                + str(posture.get("elbow_below_shoulder"))
                + ", elbow_angle_deg=" + str(posture.get("elbow_angle_deg"))
                + ", bone-tip errors=" + str(errors))
        if scene_name == "bow_hold" and report:
            prop = report.get("bow_prop") or {}
            wrists = report.get("targets", [])
            if len(wrists) != 2 or {t.get("hand") for t in wrists} != {"right", "left"}:
                problems.append("two hand targets required")
            if not prop.get("bow_string_shared_scene") or len(prop.get("bow_endpoints", [])) != 2:
                problems.append("missing rigid bow/string prop geometry")
            if prop.get("length_m") != config["pose"]["length_m"]:
                problems.append("bow length mismatch")
            if any(t.get("error_m", 99) > 0.10 for t in wrists):
                problems.append("wrist more than 100mm from bow grip seed")
            geometry_notes.append(
                "- bow hold: wrist-to-target errors=" + str(errors)
                + "; rigid bow length=" + str(prop.get("length_m")))
        error_text = ", ".join(map(str, errors)) if errors else "—"
        if problems:
            failures.append(scene_name + ": " + "; ".join(problems))
        summary.append("| " + scene_name + " | " +
                       ("FAIL: " + "; ".join(problems) if problems else "PASS") +
                       " | " + error_text + " |")
    summary += ["", "### Card skin geometry (diagnostic only)", *geometry_notes, "", "CCD convergence does not guarantee valid joint limits or contact.",
                "Artifacts: PNG views and report.json for each scenario.", ""]
    (OUT / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary), flush=True)
    if failures:
        raise SystemExit("Smoke-test failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
