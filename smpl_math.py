"""
smpl_math.py
Pure math for the SMPL body model: no FBX and no file I/O.

Functions
---------
rodrigues_to_euler      Convert Rodrigues rotation vectors to Euler angles.
calc_local_position     Parent-relative joint positions from mesh vertices.
pose_to_joint_rotations Per-joint Euler angles for one or many SMPL poses.
"""

import numpy as np
from scipy.spatial.transform import Rotation

NUM_JOINTS = 24

# Parent joint index for each of the 24 SMPL joints (joint 0 = Pelvis = root)
JOINT_PARENTS = [
    0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21,
]


def rodrigues_to_euler(rotation_vectors):
    """
    Convert Rodrigues vectors (axis * angle, radians) to Euler angles.

    Angles are extrinsic X, then Y, then Z, in degrees, matching the default
    FBX rotation order (eEulerXYZ).

    Parameters
    ----------
    rotation_vectors : (..., 3) array.

    Returns
    -------
    (..., 3) array of Euler angles in degrees.
    """
    rotation_vectors = np.asarray(rotation_vectors, dtype=float)
    flat = rotation_vectors.reshape(-1, 3)
    euler = Rotation.from_rotvec(flat).as_euler("xyz", degrees=True)
    return euler.reshape(rotation_vectors.shape)


def calc_local_position(joint_regressor, vertices):
    """
    Compute the parent-relative position of each SMPL joint.

    Parameters
    ----------
    joint_regressor : (24, N) array mapping vertices to joint positions.
    vertices        : (N, 3) array of mesh vertex positions.

    Returns
    -------
    (24, 3) array. Row 0 (Pelvis) is in world space, the others are offsets
    from their parent joint.
    """
    joints = joint_regressor @ vertices
    local = joints - joints[JOINT_PARENTS]
    local[0] = joints[0]
    return local


def pose_to_joint_rotations(poses):
    """
    Convert SMPL pose vectors to per-joint Euler angles (degrees).

    Parameters
    ----------
    poses : (72,) for a single pose or (F, 72) for F frames.

    Returns
    -------
    (24, 3) or (F, 24, 3) array of Euler angles in degrees.
    """
    poses = np.asarray(poses, dtype=float)
    return rodrigues_to_euler(poses.reshape(poses.shape[:-1] + (NUM_JOINTS, 3)))
