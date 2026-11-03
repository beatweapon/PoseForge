"""A rigid staff with two independently defined hand grip frames."""
import bpy
from mathutils import Vector
from bow import _tube
from grip_targets import solve_grip_frames


def hold_staff(rig, specification):
    bones = rig.pose.bones
    shoulders = [rig.matrix_world @ bones["upperarm01." + suffix].head
                 for suffix in ("R", "L")]
    midpoint = sum(shoulders, Vector()) / 2
    center = midpoint + Vector((0, -0.3, -0.45))
    length = float(specification["length_m"])
    start = center + Vector((-length / 2, 0, 0))
    end = center + Vector((length / 2, 0, 0))
    staff = _tube("Staff_Rigid", [start, end], 0.016,
                  (0.38, 0.21, 0.10, 1.0))
    positions = {
        "right": center + Vector((-length * 0.2, 0, 0)),
        "left": center + Vector((length * 0.2, 0, 0)),
    }
    frames = [
        {"hand": side, "grip_world": list(pos),
         "wrist_offset": [0, 0.012, 0.078],
         "approach_axis_world": [0, 0, -1]}
        for side, pos in positions.items()
    ]
    results = solve_grip_frames(rig, frames)
    return {
        "kind": "staff", "parts": [staff.name], "length_m": length,
        "center": [float(v) for v in center],
        "grips": {k: [float(v) for v in p] for k, p in positions.items()},
        "endpoints": [[float(v) for v in start], [float(v) for v in end]],
        "shared_scene": True, "grip_frames": frames,
    }, results
