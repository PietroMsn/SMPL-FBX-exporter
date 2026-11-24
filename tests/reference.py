"""
Reference linear blend skinning, written directly from the SMPL definition,
used to check what the exporters write.
"""

import numpy as np
from scipy.spatial.transform import Rotation

from rig import JOINT_ORDER, JOINT_PARENT, ROOT


def posed_vertices(rig, frame):
    """Vertices of *rig* deformed by the pose of *frame*, as (V, 3)."""
    world_rest = rig.rest_world_positions()
    global_tf = {}
    for j in JOINT_ORDER:
        local = np.eye(4)
        if j != ROOT:
            local[:3, :3] = Rotation.from_rotvec(rig.rotations[frame, j]).as_matrix()
        local[:3, 3] = rig.rest_offsets[j]
        parent = JOINT_PARENT[j]
        global_tf[j] = local if parent is None else global_tf[parent] @ local

    homogeneous = np.c_[rig.vertices, np.ones(len(rig.vertices))]
    out = np.zeros((len(rig.vertices), 3))
    for j in range(len(rig.weights)):
        skin = global_tf[j].copy()
        skin[:3, 3] -= skin[:3, :3] @ world_rest[j]  # global @ inverse(bind)
        out += rig.weights[j][:, None] * (homogeneous @ skin.T)[:, :3]
    return out
