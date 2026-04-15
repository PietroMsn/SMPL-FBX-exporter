"""
smpl_math.py
Pure mathematical utilities for the SMPL body model.

No FBX, no file I/O, no project-level imports - this module sits at the
bottom of the dependency stack and can be imported by any other module
without risk of circular references.

Functions
---------
rodrigues_to_euler      Convert a Rodrigues rotation vector to Euler angles.
calc_local_position     Compute parent-relative joint positions from vertices.
pose_to_joint_rotations Extract per-joint Euler angles from a raw SMPL pose vector.
"""

import math

import numpy as np
from numpy import linalg
import transforms3d


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_JOINTS = 24

# Parent joint index for each of the 24 SMPL joints (joint 0 = Pelvis = root)
JOINT_PARENTS = [
    0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21,
]


# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------

def rodrigues_to_euler(rotation_vector):
    """
    Convert a 3-D Rodrigues rotation vector (axis x angle) to Euler angles.

    Uses the Rodrigues formula to build the 3x3 rotation matrix, then
    extracts ZYX Euler angles via ``transforms3d``.

    Parameters
    ----------
    rotation_vector : (3,) array  -  axis scaled by rotation angle (radians).

    Returns
    -------
    euler : (3,) array of Euler angles in **degrees**.
            Returns the zero vector unchanged when the input has zero norm.
    """
    angle = linalg.norm(rotation_vector)
    if angle == 0.0:
        return rotation_vector.copy()

    axis = rotation_vector / angle

    skew = np.array([
        [ 0.0,    -axis[2],  axis[1]],
        [ axis[2], 0.0,     -axis[0]],
        [-axis[1], axis[0],  0.0    ],
    ])

    rotation_matrix = (
        np.eye(3)
        + skew * math.sin(angle)
        + np.matmul(skew, skew * (1.0 - math.cos(angle)))
    )

    return np.array(transforms3d.euler.mat2euler(rotation_matrix)) * 180.0 / math.pi


# ---------------------------------------------------------------------------
# Joint position helpers
# ---------------------------------------------------------------------------

def calc_local_position(smpl_model, vertices):
    """
    Compute the parent-relative position of each SMPL joint.

    The joint world positions are obtained by applying the SMPL joint
    regressor to the mesh vertices.  Each joint position is then expressed
    relative to its parent joint (joint 0 / Pelvis is kept in world space).

    Parameters
    ----------
    smpl_model : SMPL model object that exposes a sparse ``J_regressor``
                 of shape (24, N_vertices).
    vertices   : (N, 3) float array of mesh vertex positions.

    Returns
    -------
    local_positions : list of 24 [x, y, z] float lists.
    """
    regressor = np.asarray(smpl_model.J_regressor.todense())  # (24, N)

    # World-space joint positions - shape (24, 3)
    J = np.column_stack([
        np.squeeze(np.matmul(regressor, vertices[:, ax]))
        for ax in range(3)
    ])

    local_positions = [J[0].tolist()]  # Pelvis: keep in world space

    for i in range(1, NUM_JOINTS):
        local_positions.append((J[i] - J[JOINT_PARENTS[i]]).tolist())

    return local_positions


# ---------------------------------------------------------------------------
# Pose extraction
# ---------------------------------------------------------------------------

def pose_to_joint_rotations(smpl_model):
    """
    Convert the current SMPL pose vector to per-joint Euler angles (degrees).

    Reads ``smpl_model.pose`` (a flat 72-element vector = 24 joints x 3),
    reshapes it into (24, 3) Rodrigues vectors, and converts each to Euler
    angles with :func:`rodrigues_to_euler`.

    Parameters
    ----------
    smpl_model : SMPL model object with a ``pose`` attribute of length 72.

    Returns
    -------
    joint_rotation : (24, 3) float array of Euler angles in degrees.
    """
    raw = np.array(smpl_model.pose[:]).reshape(NUM_JOINTS, 3)
    return np.array([rodrigues_to_euler(raw[i]) for i in range(NUM_JOINTS)])
