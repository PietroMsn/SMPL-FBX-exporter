"""
smpl_model.py
Load the SMPL joint regressor without chumpy.

The official SMPL ``.pkl`` files were pickled under Python 2 and contain
chumpy objects. The exporter only needs ``J_regressor`` (a scipy sparse
matrix), so chumpy classes are replaced with an inert stub while unpickling.
A ``.npy`` / ``.npz`` file holding the regressor is accepted as well.
"""

import pickle

import numpy as np
import scipy.sparse


class _Stub:
    """Placeholder for any chumpy object found in the pickle."""

    def __init__(self, *args, **kwargs):
        pass

    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)


class _SmplUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module.startswith("chumpy"):
            return _Stub
        # Old pickles reference private modules such as ``scipy.sparse.csc``.
        if module.startswith("scipy.sparse") and hasattr(scipy.sparse, name):
            return getattr(scipy.sparse, name)
        return super().find_class(module, name)


def load_joint_regressor(path):
    """
    Return the SMPL joint regressor as a dense (24, N_vertices) array.

    Parameters
    ----------
    path : ``.pkl`` SMPL model, or ``.npy`` / ``.npz`` (key ``J_regressor``)
           containing the regressor directly.
    """
    if path.endswith(".npy"):
        regressor = np.load(path)
    elif path.endswith(".npz"):
        regressor = np.load(path)["J_regressor"]
    else:
        with open(path, "rb") as f:
            data = _SmplUnpickler(f, encoding="latin1").load()
        regressor = data["J_regressor"]

    if scipy.sparse.issparse(regressor):
        regressor = regressor.toarray()
    return np.asarray(regressor, dtype=float)
