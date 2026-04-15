"""
geometry.py
Mesh geometry utilities: loading vertex / face data from .mat files.

Dependency chain:  smpl_math  <-  geometry  (no FBX, no animation)

Functions
---------
load_geometry   Load vertices and faces from a SURREAL .mat file.
"""

import sys

import numpy as np
import scipy.io as sio


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_geometry(mat_path, scale):
    """
    Load mesh geometry from a SURREAL-format .mat file.

    Parameters
    ----------
    mat_path : Path to the .mat file containing ``VERT`` and ``TRIV`` arrays.
    scale    : Uniform scale factor applied to vertex coordinates.

    Returns
    -------
    vertices : (N, 3) float array of vertex positions (scaled).
    faces    : (F, 3) float array of triangle indices (converted to 0-based).
    """
    data = sio.loadmat(mat_path)

    vertices = np.array(data["VERT"], dtype=float) * scale
    faces    = np.array(data["TRIV"], dtype=float) - 1  # MATLAB 1-based -> 0-based

    return vertices, faces


def load_geometry_from_args():
    """
    Convenience wrapper: read mesh path and scale from ``sys.argv[3]`` and
    ``sys.argv[4]`` respectively.

    Returns
    -------
    vertices : (N, 3) float array.
    faces    : (F, 3) float array (0-based).

    Raises
    ------
    IndexError  if fewer than 5 command-line arguments are provided.
    ValueError  if ``sys.argv[4]`` cannot be converted to an integer.
    """
    mat_path = sys.argv[3]
    scale    = int(sys.argv[4])
    return load_geometry(mat_path, scale)
