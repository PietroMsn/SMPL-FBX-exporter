"""
geometry.py
Load a custom body mesh (vertices and, optionally, triangles) from a .mat file.
"""

import numpy as np
import scipy.io as sio


def load_geometry(mat_path):
    """
    Load a mesh from a .mat file with a ``VERT`` array and optional ``TRIV``.

    Returns
    -------
    vertices : (N, 3) float array of vertex positions.
    faces    : (F, 3) int array of triangle indices (0-based), or None when
               the file has no ``TRIV`` (the SMPL triangles are used then).
    """
    data = sio.loadmat(mat_path)

    vertices = np.asarray(data["VERT"], dtype=float)
    faces = None
    if "TRIV" in data:
        faces = np.asarray(data["TRIV"], dtype=np.int64) - 1  # MATLAB 1-based -> 0-based

    return vertices, faces
