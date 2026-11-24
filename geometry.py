"""
geometry.py
Load mesh geometry (vertices and triangles) from a .mat file.
"""

import numpy as np
import scipy.io as sio


def load_geometry(mat_path, scale=1.0):
    """
    Load mesh geometry from a .mat file with ``VERT`` and ``TRIV`` arrays.

    Parameters
    ----------
    mat_path : Path to the .mat file.
    scale    : Uniform scale factor applied to vertex coordinates.

    Returns
    -------
    vertices : (N, 3) float array of vertex positions (scaled).
    faces    : (F, 3) int array of triangle indices (0-based).
    """
    data = sio.loadmat(mat_path)

    vertices = np.asarray(data["VERT"], dtype=float) * scale
    faces = np.asarray(data["TRIV"], dtype=np.int64) - 1  # MATLAB 1-based -> 0-based

    return vertices, faces
