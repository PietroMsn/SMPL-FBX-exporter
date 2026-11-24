"""Loading SMPL model files (.pkl with chumpy objects, .npz) and the rig."""

import pickle
import sys
import types

import numpy as np
import pytest
import scipy.sparse

from conftest import MESH, POSE, synthetic_smpl_arrays
from rig import build_rig
from smpl_model import find_model, load_smpl_model


def _write_chumpy_pickle(path, arrays):
    """
    Write a pickle laid out like the official SMPL files: Python 2 protocol,
    a sparse J_regressor and chumpy objects for some arrays. A throw-away
    ``chumpy`` module is registered only while pickling.
    """
    chumpy = types.ModuleType("chumpy")
    chumpy_ch = types.ModuleType("chumpy.ch")

    class Ch:
        def __init__(self, x):
            self.x = x
            self._dirty_vars = set()

    Ch.__module__ = "chumpy.ch"
    Ch.__qualname__ = "Ch"
    chumpy_ch.Ch = Ch
    sys.modules.update({"chumpy": chumpy, "chumpy.ch": chumpy_ch})
    try:
        data = {
            "v_template": Ch(arrays["v_template"]),
            "weights": Ch(arrays["weights"]),
            "f": arrays["f"],
            "J_regressor": scipy.sparse.csc_matrix(arrays["J_regressor"]),
            "shapedirs": Ch(np.zeros((len(arrays["v_template"]), 3, 10))),
        }
        with open(path, "wb") as f:
            pickle.dump(data, f, protocol=2)
    finally:
        del sys.modules["chumpy"], sys.modules["chumpy.ch"]


@pytest.mark.parametrize("ext", ["pkl", "npz"])
def test_load_model(tmp_path, ext):
    arrays = synthetic_smpl_arrays()
    path = tmp_path / f"model.{ext}"
    if ext == "pkl":
        _write_chumpy_pickle(path, arrays)
    else:
        np.savez(path, **arrays)

    assert "chumpy" not in sys.modules
    model = load_smpl_model(str(path))
    np.testing.assert_array_equal(model.v_template, arrays["v_template"])
    np.testing.assert_array_equal(model.faces, arrays["f"])
    np.testing.assert_array_equal(model.weights, arrays["weights"].T)
    np.testing.assert_array_equal(model.J_regressor, arrays["J_regressor"])


def test_missing_model_file():
    with pytest.raises(FileNotFoundError, match="smpl.is.tue.mpg.de"):
        load_smpl_model("does/not/exist.pkl")


def test_find_model_prefers_official_names(tmp_path):
    assert find_model(str(tmp_path)) is None
    (tmp_path / "SMPL_NEUTRAL.pkl").touch()
    (tmp_path / "basicmodel_m_lbs_10_207_0_v1.1.0.pkl").touch()
    assert find_model(str(tmp_path)).endswith("basicmodel_m_lbs_10_207_0_v1.1.0.pkl")


def test_rig_uses_template_mesh_and_model_weights(model_file):
    model = load_smpl_model(model_file)
    rig = build_rig(POSE, model_file, end=5, scale=2.0)
    np.testing.assert_allclose(rig.vertices, model.v_template * 2.0)
    np.testing.assert_array_equal(rig.faces, model.faces)
    np.testing.assert_array_equal(rig.weights, model.weights)


def test_rig_with_custom_mesh(model_file, tmp_path):
    import scipy.io as sio
    verts = sio.loadmat(MESH)["VERT"] + 1.0
    custom = tmp_path / "custom.mat"
    sio.savemat(custom, {"VERT": verts})  # no TRIV: SMPL triangles are used
    rig = build_rig(POSE, model_file, str(custom), end=5)
    np.testing.assert_allclose(rig.vertices, verts)
    np.testing.assert_array_equal(rig.faces, load_smpl_model(model_file).faces)


def test_rig_rejects_mesh_with_wrong_topology(model_file, tmp_path):
    import scipy.io as sio
    bad = tmp_path / "bad.mat"
    sio.savemat(bad, {"VERT": np.zeros((100, 3))})
    with pytest.raises(ValueError, match="SMPL topology"):
        build_rig(POSE, model_file, str(bad))
