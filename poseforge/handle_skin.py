"""Sample evaluated MPFB skin vertices against cylindrical handles.

Diagnostic ONLY: sparse vertex samples cannot establish exact mesh contact,
collision-freedom or a stable physical grasp.
"""
import bpy
from mathutils import Vector
from rig import mpfb_skin_groups, semantic_bones

FINGERS = ("thumb", "index", "middle", "ring", "pinky")


def cylinder_gap(point, center, axis, radius):
    delta = Vector(point) - Vector(center)
    unit = Vector(axis).normalized()
    axial = delta.dot(unit)
    radial = (delta - unit * axial).length
    return float(radial - radius), float(axial)


def inspect_handle_skin(rig, targets, body_meshes):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    bone_names = semantic_bones(rig.pose.bones.keys())
    result = {"method": "evaluated_weighted_finger_vertices",
              "exact_collision_verified": False, "contact_verified": False,
              "hands": {}}
    for target in targets:
        side = target["hand"]
        center = Vector(target["grip_world"])
        axis = Vector(target.get("handle_axis_world", (1, 0, 0)))
        radius = float(target.get("handle_radius_m", 0.016))
        if axis.length < 1e-8 or radius <= 0:
            raise ValueError("Invalid handle")
        axis.normalize()
        hand = {"fingers": {}, "skipped_topology": []}
        hand_nearest = {}
        tips = {f: rig.matrix_world @ rig.pose.bones[bone_names[f"{side}_{f}_3"]].tail
                for f in FINGERS}
        for finger in FINGERS:
            gaps = []
            all_gaps = []
            weighted_count = 0
            matched_groups = set()
            selection_method = "vertex_weights"
            nearest_vertex = None
            for obj in body_meshes:
                groups = {obj.vertex_groups[name].index
                          for name in mpfb_skin_groups(side, finger)
                          if name in obj.vertex_groups}
                if not groups:
                    continue
                matched_groups.update(name for name in mpfb_skin_groups(side, finger)
                                      if name in obj.vertex_groups)
                evaluated = obj.evaluated_get(graph)
                mesh = evaluated.to_mesh()
                try:
                    if len(mesh.vertices) != len(obj.data.vertices):
                        if obj.name not in hand["skipped_topology"]:
                            hand["skipped_topology"].append(obj.name)
                        continue
                    candidates = (i for i, v in enumerate(obj.data.vertices)
                                  if any(g.group in groups and g.weight >= 0.2
                                         for g in v.groups))
                    for i in candidates:
                        weighted_count += 1
                        world_point = evaluated.matrix_world @ mesh.vertices[i].co
                        gap, axial = cylinder_gap(world_point, center, axis, radius)
                        if abs(axial) <= 0.10:
                            all_gaps.append(gap)
                            if nearest_vertex is None or abs(gap) < nearest_vertex[0]:
                                nearest_vertex = (abs(gap), world_point.copy(), gap)
                            if gap <= 0.055:
                                gaps.append(gap)
                finally:
                    evaluated.to_mesh_clear()
            if weighted_count == 0:
                # MPFB can expose group names without assigned weights.
                # Approximate segmentation by proximity to distal bone tips.
                selection_method = "distal_tip_voronoi_35mm"
                own = tips[finger]
                for obj in body_meshes:
                    evaluated = obj.evaluated_get(graph)
                    mesh = evaluated.to_mesh()
                    try:
                        for vert in mesh.vertices:
                            point = evaluated.matrix_world @ vert.co
                            distance = (point - own).length
                            if distance > 0.035:
                                continue
                            if any((point - tip).length < distance
                                   for key, tip in tips.items() if key != finger):
                                continue
                            weighted_count += 1
                            gap, axial = cylinder_gap(point, center, axis, radius)
                            if abs(axial) <= 0.10:
                                all_gaps.append(gap)
                                if nearest_vertex is None or abs(gap) < nearest_vertex[0]:
                                    nearest_vertex = (abs(gap), point.copy(), gap)
                                if gap <= 0.055:
                                    gaps.append(gap)
                    finally:
                        evaluated.to_mesh_clear()
            if nearest_vertex is not None:
                radial = nearest_vertex[1] - center
                radial -= axis * radial.dot(axis)
                if radial.length > 1e-8:
                    radial.normalize()
                    hand_nearest[finger] = radial
            hand["fingers"][finger] = {
                "selection_method": selection_method,
                "sample_count": len(gaps),
                "weighted_vertex_count": weighted_count,
                "axial_window_vertex_count": len(all_gaps),
                "matched_vertex_groups": sorted(matched_groups),
                "closest_signed_gap_in_axial_window_m": (
                    min(all_gaps, key=abs) if all_gaps else None),
                "nearest_abs_gap_m": min(map(abs, gaps), default=None),
                "sampled_inside_over_2mm": sum(g < -0.002 for g in gaps),
                "sampled_within_5mm": sum(abs(g) <= 0.005 for g in gaps),
                "contact_verified": False,
            }
        thumb_normal = hand_nearest.get("thumb")
        index_normal = hand_nearest.get("index")
        # A physical pinch requires opposing contact sides, not merely
        # nearby fingertips. This is only an approximate sampled direction.
        if thumb_normal is not None and index_normal is not None:
            cosine = max(-1.0, min(1.0, thumb_normal.dot(index_normal)))
            hand["thumb_index_radial_dot"] = round(float(cosine), 6)
            hand["opposing_sides_proxy"] = cosine <= -0.35
        else:
            hand["thumb_index_radial_dot"] = None
            hand["opposing_sides_proxy"] = False
        hand["opposition_proxy_only"] = True
        hand["sample_count"] = sum(v["sample_count"] for v in hand["fingers"].values())
        hand["has_penetration_evidence"] = any(
            v["sampled_inside_over_2mm"] for v in hand["fingers"].values())
        result["hands"][side] = hand
    return result
