"""Experimental wrist refinement driven by evaluated skin-to-handle gaps.

A finite, rollback-safe local search. This is not continuous collision
detection, anatomically constrained IK, or certification of real grasp.
"""
import bpy
from mathutils import Matrix, Quaternion, Vector

from handle_skin import inspect_handle_skin
from rig import wrist_bone_name


def _score(hand, require_opposition=False):
    total = 0.0
    near = 0
    inside = 0
    for finger in ("thumb", "index"):
        item = hand["fingers"][finger]
        gap = item["nearest_abs_gap_m"]
        count = item["sample_count"]
        if not count or gap is None:
            total += 250.0
        else:
            total += min(75.0, gap * 1000.0)
            near += int(item["sampled_within_5mm"] > 0)
        total += 12.0 * item["sampled_inside_over_2mm"]
        inside += item["sampled_inside_over_2mm"]
    radial_dot = hand.get("thumb_index_radial_dot")
    opposed = bool(hand.get("opposing_sides_proxy", False))
    if require_opposition:
        if radial_dot is None:
            total += 60.0
        elif not opposed:
            total += 30.0 * (1.0 + float(radial_dot))
    return {"score": round(total, 5), "near_fingers": near,
            "thumb_index_radial_dot": radial_dot,
            "opposing_sides_proxy": opposed,
            "deep_inside_vertices": inside}


def refine_skin_wrist(rig, target, body_meshes, *, require_opposition=False):
    side = target["hand"]
    wrist = rig.pose.bones[wrist_bone_name(side)]
    base = wrist.matrix.copy()
    pivot = wrist.head.copy()

    def measure():
        report = inspect_handle_skin(rig, [target], body_meshes)
        return _score(report["hands"][side], require_opposition=require_opposition)

    initial = measure()
    best = initial
    best_matrix = base.copy()
    trials = [{"axis": "none", "radians": 0.0, **initial}]
    for axis_name, axis in (("x", (1, 0, 0)), ("y", (0, 1, 0))):
        for radians in (-0.12, 0.12):
            wrist.matrix = base.copy()
            bpy.context.view_layer.update()
            rot = Quaternion(Vector(axis), radians).to_matrix().to_4x4()
            wrist.matrix = (Matrix.Translation(pivot) @ rot
                            @ Matrix.Translation(-pivot) @ wrist.matrix)
            candidate = measure()
            trials.append({"axis": axis_name, "radians": radians, **candidate})
            # Do not improve a distance proxy by creating additional deep
            # intersections or losing a previously near-contact finger.
            if (candidate["deep_inside_vertices"] <= best["deep_inside_vertices"]
                    and candidate["near_fingers"] >= best["near_fingers"]
                    and candidate["score"] < best["score"] - 0.1):
                best = candidate
                best_matrix = wrist.matrix.copy()
    wrist.matrix = best_matrix
    bpy.context.view_layer.update()
    final = measure()
    return {
        "name": "skin_wrist_opposition_search_v2" if require_opposition else "skin_wrist_local_search_v1",
        "opposition_required": require_opposition,
        "baseline": initial, "final": final, "trials": trials,
        "improved_or_unchanged": final["score"] <= initial["score"] + 0.001,
        "deep_penetration_not_increased":
            final["deep_inside_vertices"] <= initial["deep_inside_vertices"],
        "mesh_proximity_only": True,
        "contact_verified": False,
        "collision_free_verified": False,
    }
