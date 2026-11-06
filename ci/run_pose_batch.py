"""Run multiple isolated bow-grip variants and produce review artifacts.

No variant is automatically considered anatomically valid or promoted.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ("current", "joint_balanced", "joint_position", "joint_orientation")
VIEWS = ("front", "back", "three_quarter", "hand_closeup")


def summarize(report):
    hands = report.get("targets") or []
    if len(hands) != 2:
        raise ValueError("Expected exactly two hands")
    def mean(values):
        return round(sum(values) / len(values), 6)
    def hand_metric(row, key, subkey):
        item = row.get(key) or {}
        value = item.get(subkey)
        return float(value) if value is not None else None
    return {
        "max_wrist_error_m": max(float(h["error_m"]) for h in hands),
        "mean_palm_error_m": mean([hand_metric(h, "palm_anchor_fit", "final_error_m") for h in hands]),
        "mean_palm_plane_deg": mean([float(h["palm_frame_final"]["plane_deg"]) for h in hands]),
        "mean_index_axis_gap_m": (
            mean([float(h["finger_grip_prior"]["final_axis_distances_m"]["index"])
                  for h in hands]) if all(h.get("finger_grip_prior") for h in hands) else None),
        "joint_fits": [h.get("joint_grip_fit") for h in hands],
        "mean_final_palm_plane_deg": mean([float(h["palm_frame_final"]["plane_deg"]) for h in hands]),
        "skin_contact_verified": False,
        "collision_free_verified": False,
    }


def draw_montage(folder, rows):
    cell_w, cell_h = 320, 342
    sheet = Image.new("RGB", (cell_w * len(VIEWS), cell_h * len(VARIANTS)), "#16181d")
    draw = ImageDraw.Draw(sheet)
    for y, variant in enumerate(VARIANTS):
        for x, view in enumerate(VIEWS):
            source = folder / variant / (view + ".png")
            with Image.open(source) as raw:
                image = raw.convert("RGBA")
                background = Image.new("RGBA", image.size, (28, 30, 35, 255))
                background.alpha_composite(image)
                thumb = background.convert("RGB")
                thumb.thumbnail((306, 306))
            sheet.paste(thumb, (x * cell_w + (cell_w-thumb.width)//2,
                                y * cell_h + 24))
            draw.text((x * cell_w + 8, y * cell_h + 6),
                      variant + " / " + view, fill="#f4f4f5")
    sheet.save(folder / "comparison.png")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--blender", required=True)
    p.add_argument("--output", default=str(ROOT / "output" / "ci" / "bow_batch"))
    args = p.parse_args()
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    baseline = json.loads((ROOT / "examples" / "human_bow_hold.json").read_text())
    for variant in VARIANTS:
        config = json.loads(json.dumps(baseline))
        config["model"]["source"] = str((ROOT / "assets" / "human.blend").resolve())
        config["output"] = str(folder / variant)
        config["cameras"] = list(VIEWS)
        config["render"].update(width=320, height=320)
        config_file = folder / (variant + ".json")
        config_file.write_text(json.dumps(config, indent=2))
        env = {**os.environ, "POSEFORGE_GRIP_VARIANT": variant}
        result = subprocess.run(
            [sys.executable, "-m", "poseforge.cli", "render-hold-bow",
             str(config_file), "--blender", args.blender],
            cwd=ROOT, env=env, check=False)
        if result.returncode:
            raise RuntimeError(f"{variant}: Blender exit {result.returncode}")
        report = json.loads((folder / variant / "report.json").read_text())
        if any(not (folder / variant / (view + ".png")).is_file() for view in VIEWS):
            raise RuntimeError(f"{variant}: expected views missing")
        if {h.get("experiment_variant") for h in report.get("targets", [])} != {variant}:
            raise RuntimeError(f"{variant}: variant configuration was ignored")
        rows.append({"variant": variant, **summarize(report)})
    draw_montage(folder, rows)
    if not (folder / "comparison.png").is_file():
        raise RuntimeError("Montage generation failed")
    payload = {
        "experiment": "bow coupled-grip proxy comparison v2",
        "reference": "current",
        "variants": rows,
        "selected": None,
        "selection_reason": "No automatic promotion: score is a skeletal proxy, not a validated grasp.",
        "requires_visual_review": True,
        "views": list(VIEWS),
    }
    (folder / "comparison.json").write_text(json.dumps(payload, indent=2) + "\n")
    headings = ["# Bow grip batch comparison", "",
                "All candidates were independently rendered from the same model and scene.",
                "No automatic winner: human/vision inspection is required.", "",
                "| Variant | Wrist max (mm) | Palm mean (mm) | Plane mean (deg) | Index axis mean (mm) |",
                "|---|---:|---:|---:|---:|"]
    for r in rows:
        if r["variant"].startswith("joint_"):
            fits = r["joint_fits"]
            if len(fits) != 2 or any(not fit["objective_non_regression"]
                                      or len(fit["trials"]) != 13 for fit in fits):
                raise RuntimeError("Incomplete or regressing coupled search")
            if r["variant"] == "joint_position" and not all(
                    fit["arm_position_refinement"]["attempted"] for fit in fits):
                raise RuntimeError("Joint position refinement was not attempted")
        gap = "n/a" if r["mean_index_axis_gap_m"] is None else f'{r["mean_index_axis_gap_m"]*1000:.1f}'
        headings.append(f'| {r["variant"]} | {r["max_wrist_error_m"]*1000:.1f} | '
                        f'{r["mean_palm_error_m"]*1000:.1f} | '
                        f'{r["mean_palm_plane_deg"]:.1f} | {gap} |')
    headings += ["", "See comparison.png and each variant's report.json.",
                 "All contact and collision claims remain unverified.", ""]
    (folder / "summary.md").write_text("\n".join(headings))
    print("\n".join(headings))


if __name__ == "__main__":
    main()
