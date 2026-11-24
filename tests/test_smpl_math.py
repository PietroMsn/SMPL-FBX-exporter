import numpy as np
from scipy.spatial.transform import Rotation

from smpl_math import (
    JOINT_PARENTS, NUM_JOINTS,
    calc_local_position, pose_to_joint_rotations, rodrigues_to_euler,
)


def _rodrigues_matrix(v):
    """Reference Rodrigues formula, independent of scipy."""
    angle = np.linalg.norm(v)
    if angle == 0:
        return np.eye(3)
    k = v / angle
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K


def test_euler_reproduces_rotation_matrix():
    rng = np.random.default_rng(0)
    for v in rng.normal(size=(200, 3)):
        euler = rodrigues_to_euler(v)
        R = Rotation.from_euler("xyz", euler, degrees=True).as_matrix()
        np.testing.assert_allclose(R, _rodrigues_matrix(v), atol=1e-10)


def test_zero_rotation_gives_zero_angles():
    np.testing.assert_allclose(rodrigues_to_euler(np.zeros(3)), 0.0, atol=1e-12)


def test_single_axis_rotation():
    np.testing.assert_allclose(rodrigues_to_euler([0, 0, np.pi / 2]), [0, 0, 90], atol=1e-9)


def test_pose_to_joint_rotations_shapes():
    assert pose_to_joint_rotations(np.zeros(72)).shape == (NUM_JOINTS, 3)
    assert pose_to_joint_rotations(np.zeros((5, 72))).shape == (5, NUM_JOINTS, 3)


def test_local_positions_are_parent_relative():
    rng = np.random.default_rng(1)
    vertices = rng.normal(size=(50, 3))
    regressor = rng.random((NUM_JOINTS, 50))
    world = regressor @ vertices
    local = calc_local_position(regressor, vertices)

    np.testing.assert_allclose(local[0], world[0])
    for i in range(1, NUM_JOINTS):
        np.testing.assert_allclose(local[i], world[i] - world[JOINT_PARENTS[i]])
