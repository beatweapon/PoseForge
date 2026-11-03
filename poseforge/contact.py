"""Mesh-based exploratory diagnostics for card grasp poses.

Uses posed vertices assigned to distal finger bones; not continuous collision
detection or a guarantee of true skin-to-surface contact.
"""
from mathutils import Vector


def inspect_card_skin(rig, card, side, names, body_objects):
    """Measure proximity of deforming skin vertices to two card face targets."""
    from grasp import card_face_targets

    center = card.matrix_world.translation.copy()
    size = card.dimensions.copy()
    targets = card_face_targets(center, size)
    depsgraph = __import__("bpy").context.evaluated_depsgraph_get()
    report = {"method": "weighted_evaluated_mesh_vertices",
              "is_exact_collision_test": False, "fingers": {}}

    for finger in ("thumb", "index"):
        bones = [names[f"{side}_{finger}_{joint}"] for joint in (2, 3)]
        goal = targets[finger]
        best = None
        sample_count = 0
        inside_count = 0
        for obj in body_objects:
            groups = {obj.vertex_groups[b].index for b in bones
                      if b in obj.vertex_groups}
            if not groups:
                continue
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                if len(mesh.vertices) != len(obj.data.vertices):
                    continue
                matrix = evaluated.matrix_world
                for i, base_vert in enumerate(obj.data.vertices):
                    if not any(group.group in groups and group.weight >= 0.05
                               for group in base_vert.groups):
                        continue
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
            "nearest_skin_vertex": best,
            "sampled_vertices_inside_card": inside_count,
            "has_penetration_evidence": inside_count > 0,
            "note": "Vertex samples cannot prove absence of mesh intersection.",
        }
    return report
