"""
rig.py
Format-independent description of the animated SMPL character.

Every exporter (FBX, glTF, USD) receives the same :class:`Rig` and only has
to translate it into its own file format.

Conventions
-----------
* Joint 0-23 are the SMPL joints, joint 24 is a virtual ``Root`` at the
  origin and parent of the Pelvis. ``JOINT_ORDER`` lists them parents-first.
* In the rest pose (bind pose) every joint has identity rotation, so its
  rest transform is a pure translation (``rest_offsets``).
* ``rotations`` are local joint rotations as Rodrigues vectors (radians),
  exactly as stored in the SMPL ``pose`` vector.
"""

from dataclasses import dataclass

import numpy as np
import scipy.io as sio

from geometry import load_geometry
from smpl_math import NUM_JOINTS, calc_local_position
from smpl_model import load_joint_regressor

ROOT = NUM_JOINTS  # index of the virtual Root joint

JOINT_NAMES = [
    "Pelvis",    "L_Hip",     "R_Hip",      "Spine1",
    "L_Knee",    "R_Knee",    "Spine2",     "L_Ankle",
    "R_Ankle",   "Spine3",    "L_Foot",     "R_Foot",
    "Neck",      "L_Collar",  "R_Collar",   "Head",
    "L_Shoulder","R_Shoulder","L_Elbow",    "R_Elbow",
    "L_Wrist",   "R_Wrist",   "L_Hand",     "R_Hand",
    "Root",
]

# Parent of each joint (SMPL topology; the Pelvis hangs from Root, Root has none)
JOINT_PARENT = [
    ROOT, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21,
    None,
]

# Root first, then the SMPL joints (SMPL already lists parents before children)
JOINT_ORDER = [ROOT] + list(range(NUM_JOINTS))


@dataclass
class Rig:
    vertices: np.ndarray       # (V, 3) rest-pose vertex positions
    faces: np.ndarray          # (T, 3) triangle vertex indices, 0-based
    weights: np.ndarray        # (24, V) skin weights of the SMPL joints
    rest_offsets: np.ndarray   # (25, 3) rest translation of each joint w.r.t. its parent
    rotations: np.ndarray      # (F, 24, 3) local rotations per frame (Rodrigues)
    fps: float

    @property
    def num_frames(self):
        return len(self.rotations)

    @property
    def times(self):
        return np.arange(self.num_frames) / self.fps

    def rest_world_positions(self):
        """(25, 3) world position of every joint in the rest pose."""
        world = np.zeros((NUM_JOINTS + 1, 3))
        for j in JOINT_ORDER:
            parent = JOINT_PARENT[j]
            world[j] = self.rest_offsets[j] + (world[parent] if parent is not None else 0.0)
        return world


def build_rig(pose_mat, mesh_mat, model, weights, scale=1.0, fps=30.0,
              start=0, end=None):
    """Load all inputs from disk and return a :class:`Rig`."""
    vertices, faces = load_geometry(mesh_mat, scale)
    weights = np.load(weights)
    if weights.shape != (NUM_JOINTS, len(vertices)):
        raise ValueError(f"Skin weights have shape {weights.shape}, expected "
                         f"({NUM_JOINTS}, {len(vertices)})")

    poses = sio.loadmat(pose_mat)["pose"].T[start:end]  # (F, 72)
    if len(poses) == 0:
        raise ValueError("No frames selected: check --start/--end")

    regressor = load_joint_regressor(model)
    rest_offsets = np.zeros((NUM_JOINTS + 1, 3))
    rest_offsets[:NUM_JOINTS] = calc_local_position(regressor, vertices)

    return Rig(
        vertices=vertices,
        faces=faces,
        weights=weights,
        rest_offsets=rest_offsets,
        rotations=np.asarray(poses, dtype=float).reshape(len(poses), NUM_JOINTS, 3),
        fps=float(fps),
    )
