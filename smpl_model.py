"""
smpl_model.py
Load the official SMPL model files without chumpy.

Everything the exporter needs about SMPL (template mesh, triangles, skin
weights, joint regressor) is read from the model file you download from
https://smpl.is.tue.mpg.de, so no SMPL data has to ship with this project.

Supported files
---------------
* ``.pkl``: the official SMPL models (pickled under Python 2; any chumpy
  objects inside are unpacked without importing chumpy).
* ``.npz``: the same data saved as arrays (keys ``v_template``, ``f``,
  ``weights``, ``J_regressor``), as distributed for SMPL-X tools.
"""

import glob
import os
import pickle
from dataclasses import dataclass

import numpy as np
import scipy.sparse

# File names of the official SMPL downloads, in order of preference
MODEL_FILE_PATTERNS = [
    "basicmodel_m_lbs_10_207_0_v1.*.pkl",
    "basicModel_m_lbs_10_207_0_v1.*.pkl",
    "basicmodel_neutral_lbs_10_207_0_v1.*.pkl",
    "basicModel_neutral_lbs_10_207_0_v1.*.pkl",
    "basicmodel_f_lbs_10_207_0_v1.*.pkl",
    "basicModel_f_lbs_10_207_0_v1.*.pkl",
    "SMPL_MALE.pkl", "SMPL_NEUTRAL.pkl", "SMPL_FEMALE.pkl",
    "SMPL_MALE.npz", "SMPL_NEUTRAL.npz", "SMPL_FEMALE.npz",
]


@dataclass
class SmplModel:
    v_template: np.ndarray   # (V, 3) T-pose vertices, metres, Y-up
    faces: np.ndarray        # (F, 3) triangles, 0-based
    weights: np.ndarray      # (24, V) linear blend skinning weights
    J_regressor: np.ndarray  # (24, V) joint regressor


class _Stub:
    """Placeholder for chumpy objects found in the pickle."""

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


def _to_array(value, dtype=float):
    """Convert numpy / scipy sparse / chumpy values to a dense numpy array."""
    if isinstance(value, _Stub):
        if "x" not in value.__dict__:
            raise ValueError("Unsupported chumpy object in the SMPL model file")
        value = value.__dict__["x"]
    if scipy.sparse.issparse(value):
        value = value.toarray()
    return np.asarray(value, dtype=dtype)


def find_model(folder="models"):
    """Return the first official SMPL model file found in *folder*, or None."""
    for pattern in MODEL_FILE_PATTERNS:
        matches = sorted(glob.glob(os.path.join(folder, pattern)))
        if matches:
            return matches[0]
    return None


def load_smpl_model(path):
    """Load an SMPL ``.pkl`` or ``.npz`` model file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"SMPL model not found: {path}. Download it from https://smpl.is.tue.mpg.de "
            "and put it in models/, or pass its path with --model.")

    if path.lower().endswith(".npz"):
        data = dict(np.load(path, allow_pickle=False))
    else:
        with open(path, "rb") as f:
            data = _SmplUnpickler(f, encoding="latin1").load()

    missing = {"v_template", "f", "weights", "J_regressor"} - set(data)
    if missing:
        raise ValueError(f"{path} is not an SMPL model (missing {sorted(missing)})")

    return SmplModel(
        v_template=_to_array(data["v_template"]),
        faces=_to_array(data["f"], dtype=np.int64),
        weights=_to_array(data["weights"]).T,
        J_regressor=_to_array(data["J_regressor"]),
    )
