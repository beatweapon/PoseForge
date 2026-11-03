"""Mesh-based exploratory diagnostics for card grasp poses.

Uses posed vertices assigned to distal finger bones; not continuous collision
detection or a guarantee of true skin-to-surface contact.
"""
from mathutils import Vector
from rig import mpfb_skin_groups


def inspect_card_skin(rig, card, side, names, body_objects):
    """Measure proximity of deforming skin vertices to two card face targets."""
    from grasp import card_face_targets

    center = card.matrix_world.translation.copy()
    size = card.dimensions.copy()
    targets = card_face_targets(center, size)
    depsgraph = __import__("bpy").context.evaluated_depsgraph_get()
    report = {"method": "weighted_vertices_with_tip_proximity_fallback",
              "is_exact_collision_test": False, "fingers": {}}

    for finger in ("thumb", "index"):
        bones = ([names[f"{side}_{finger}_{joint}"] for joint in (2, 3)]
                 + mpfb_skin_groups(side, finger))
        goal = targets[finger]
        best = None
        sample_count = 0
        inside_count = 0
        methods = set()
        available_groups = []
        for obj in body_objects:
            groups = {obj.vertex_groups[b].index for b in bones
                      if b in obj.vertex_groups}
            available_groups.extend([g.name for g in obj.vertex_groups if "finger" in g.name.lower()][:12])
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                if len(mesh.vertices) != len(obj.data.vertices):
                    continue
                matrix = evaluated.matrix_world
                matched = [i for i, base_vert in enumerate(obj.data.vertices)
                           if any(group.group in groups and group.weight >= 0.05
                                  for group in base_vert.groups)]
                if matched:
                    methods.add("vertex_weights")
                else:
                    # MPFB rigs may not name skin groups like their armature
                    # bones. Use local posed skin samples around distal tip,
                    # and report this weaker fallback explicitly.
                    tip_world = rig.matrix_world @ rig.pose.bones[names[f"{side}_{finger}_3"]].tail
                    matched = [i for i, v in enumerate(mesh.vertices)
                               if (matrix @ v.co - tip_world).length < 0.03]
                    if matched:
                        methods.add("near_bone_tip_30mm")
                for i in matched:
                    point = matrix @ mesh.vertices[i].co
                    sample_count += 1
                    distance = (point - goal).length
                    if best is None or distance < best["distance_m"]:
                        best = {"distance_m": float(distance),
                                "vertex_position": [float(v) for v in point]}
                    if (abs(point.x - center.x) < size.x / 2 and
                            abs(point.y - center.y) < size.y / 2 and
                            abs(point.z - center.z) < size.z / 2):
                        inside_count += 1
            finally:
                evaluated.to_mesh_clear()
        report["fingers"][finger] = {
            "target": [float(v) for v in goal],
            "sample_count": sample_count,
            "selection_methods": sorted(methods),
            "available_finger_groups_sample": available_groups[:12],
            "nearest_skin_vertex": best,
            "sampled_vertices_inside_card": inside_count,
            "has_penetration_evidence": inside_count > 0,
            "note": "Vertex samples cannot prove absence of mesh intersection.",
        }
    return report
