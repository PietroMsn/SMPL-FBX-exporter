"""
skinning.py
Helpers shared by the glTF and USD exporters (no file-format code).
"""

import numpy as np
from scipy.spatial.transform import Rotation

from rig import JOINT_ORDER
from smpl_math import NUM_JOINTS

# Position of each joint in JOINT_ORDER (= index used by skins and skeletons)
SKIN_INDEX = {joint: i for i, joint in enumerate(JOINT_ORDER)}


def vertex_influences(weights, max_influences=None):
    """
    Convert dense (24, V) weights into per-vertex (joint, weight) lists.

    Returns
    -------
    joint_indices : (V, K) int array, indices into JOINT_ORDER.
    joint_weights : (V, K) float array, each row summing to 1.
    K is the largest number of non-zero weights on a vertex, rounded up to a
    multiple of 4 (glTF stores influences in groups of 4), unless
    *max_influences* is given.
    """
    w = np.asarray(weights, dtype=float).T  # (V, 24)
    if max_influences is None:
        needed = max(1, int((w > 0).sum(axis=1).max()))
        max_influences = -(-needed // 4) * 4

    k = min(max_influences, NUM_JOINTS)
    order = np.argsort(-w, axis=1)[:, :k]                    # strongest first
    top = np.take_along_axis(w, order, axis=1)
    totals = top.sum(axis=1, keepdims=True)
    totals[totals == 0] = 1.0
    top = top / totals

    smpl_to_skin = np.array([SKIN_INDEX[j] for j in range(NUM_JOINTS)])
    indices = np.where(top > 0, smpl_to_skin[order], 0)

    if max_influences > k:
        pad = max_influences - k
        indices = np.pad(indices, ((0, 0), (0, pad)))
        top = np.pad(top, ((0, 0), (0, pad)))
    return indices, top


def rotation_quaternions(rotations):
    """
    (F, 24, 3) Rodrigues vectors -> (F, 24, 4) unit quaternions (x, y, z, w).

    Consecutive quaternions of a joint are kept on the same hemisphere so that
    interpolating between keys never takes the long way round.
    """
    frames, joints, _ = rotations.shape
    quats = Rotation.from_rotvec(rotations.reshape(-1, 3)).as_quat().reshape(frames, joints, 4)
    for f in range(1, frames):
        flip = np.sum(quats[f] * quats[f - 1], axis=1) < 0
        quats[f, flip] *= -1
    return quats


def vertex_normals(vertices, faces):
    """Area-weighted per-vertex normals."""
    tri = vertices[faces]
    face_normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    normals = np.zeros_like(vertices)
    for corner in range(3):
        np.add.at(normals, faces[:, corner], face_normals)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths[lengths == 0] = 1.0
    return normals / lengths
