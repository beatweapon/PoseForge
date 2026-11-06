"""Sample evaluated MPFB skin vertices against cylindrical handles.

Diagnostic ONLY: sparse vertex samples cannot establish exact mesh contact,
collision-freedom or a stable physical grasp.
"""
import bpy
from mathutils import Vector
from rig import mpfb_skin_groups

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
        for finger in FINGERS:
            gaps = []
            for obj in body_meshes:
                groups = {obj.vertex_groups[name].index
                          for name in mpfb_skin_groups(side, finger)
                          if name in obj.vertex_groups}
                if not groups:
                    continue
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
                        world_point = evaluated.matrix_world @ mesh.vertices[i].co
                        gap, axial = cylinder_gap(world_point, center, axis, radius)
                        if abs(axial) <= 0.10 and gap <= 0.055:
                            gaps.append(gap)
                finally:
                    evaluated.to_mesh_clear()
            hand["fingers"][finger] = {
                "sample_count": len(gaps),
                "nearest_abs_gap_m": min(map(abs, gaps), default=None),
                "sampled_inside_over_2mm": sum(g < -0.002 for g in gaps),
                "sampled_within_5mm": sum(abs(g) <= 0.005 for g in gaps),
                "contact_verified": False,
            }
        hand["sample_count"] = sum(v["sample_count"] for v in hand["fingers"].values())
        hand["has_penetration_evidence"] = any(
            v["sampled_inside_over_2mm"] for v in hand["fingers"].values())
        result["hands"][side] = hand
    return result
