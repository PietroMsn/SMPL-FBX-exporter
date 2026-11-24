"""End-to-end FBX export on the sample data, using the fake fbx module."""

import numpy as np
import pytest
import scipy.io as sio

import fbx
import main
from conftest import POSE
from rig import JOINT_NAMES
from smpl_model import load_smpl_model
from smpl_math import pose_to_joint_rotations

pytestmark = pytest.mark.skipif(not getattr(fbx, "IS_FAKE", False),
                                reason="runs only with the fake fbx module")


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def test_export(tmp_path, model_file):
    out = tmp_path / "out" / "anim.fbx"
    assert main.main([POSE, "-o", str(out), "--model", model_file,
                      "--fps", "25", "--end", "10"]) == 0
    assert out.exists()  # output directory was created

    _, scene = fbx.FbxExporter.last
    character = scene.GetRootNode().children[0]
    root_joint, mesh_node = character.children

    # Every joint appears exactly once, with its own name
    assert sorted(n.name for n in _walk(root_joint)) == sorted(JOINT_NAMES)
    skeleton_names = [n.attribute.name for n in _walk(root_joint)]
    assert len(set(skeleton_names)) == len(skeleton_names)

    mesh = mesh_node.attribute
    assert len(mesh.points) == 6890 and len(mesh.polygons) == 13776
    clusters = mesh.deformers[0].clusters
    assert len({c.name for c in clusters}) == len(clusters) == 25
    assert sum(len(c.weights) for c in clusters) == np.count_nonzero(load_smpl_model(model_file).weights)

    # 10 frames at 25 fps, values taken from the pose file
    pelvis = root_joint.children[0]
    keys = pelvis.LclRotation.curves["X"].keys
    assert [k[0] for k in keys] == pytest.approx([i / 25 for i in range(10)])
    expected = pose_to_joint_rotations(sio.loadmat(POSE)["pose"].T[:10])
    assert [k[1] for k in keys] == pytest.approx(expected[:, 0, 0].tolist())
    assert keys[0][2] == "linear"

    knee = next(n for n in _walk(root_joint) if n.name == "L_Knee")
    assert knee.LclRotation.curves["Z"].keys[3][1] == pytest.approx(expected[3, 4, 2])
    assert knee.LclRotation.curves["Z"].keys[3][2] == "cubic"
    assert not knee.LclTranslation.curves


def test_bad_frame_range(tmp_path, model_file):
    with pytest.raises(ValueError):
        main.main([POSE, "-o", str(tmp_path / "x.fbx"), "--model", model_file,
                   "--start", "100000"])


def test_missing_model_message(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "MODELS_DIR", str(tmp_path))
    with pytest.raises(SystemExit, match="No SMPL model found"):
        main.main([POSE, "-o", str(tmp_path / "x.glb")])
