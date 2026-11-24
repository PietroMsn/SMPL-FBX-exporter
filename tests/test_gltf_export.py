"""
glTF export: parse the written file with a small independent reader, skin the
mesh from the file contents alone and compare with the reference LBS.
"""

import json
import struct

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from exporters import gltf_export
from reference import posed_vertices

DTYPES = {5126: np.float32, 5121: np.uint8, 5123: np.uint16, 5125: np.uint32}
WIDTHS = {"SCALAR": 1, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _read_glb(path):
    data = open(path, "rb").read()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    assert (magic, version, length) == (b"glTF", 2, len(data))
    json_len, json_type = struct.unpack_from("<I4s", data, 12)
    assert json_type == b"JSON" and json_len % 4 == 0
    gltf = json.loads(data[20:20 + json_len])
    bin_len, bin_type = struct.unpack_from("<I4s", data, 20 + json_len)
    assert bin_type == b"BIN\0" and bin_len % 4 == 0
    return gltf, data[28 + json_len:28 + json_len + bin_len]


def _accessor(gltf, blob, index):
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    assert view["byteOffset"] % 4 == 0
    dtype = DTYPES[acc["componentType"]]
    width = WIDTHS[acc["type"]]
    arr = np.frombuffer(blob, dtype=dtype, count=acc["count"] * width,
                        offset=view["byteOffset"])
    return arr.reshape(acc["count"], width) if width > 1 else arr


def _skin_from_file(gltf, blob, frame):
    """Linear blend skinning using only what is stored in the glTF file."""
    nodes = gltf["nodes"]
    skin = gltf["skins"][0]
    anim = gltf["animations"][0]

    rotation = {}
    for ch in anim["channels"]:
        assert ch["target"]["path"] == "rotation"
        quats = _accessor(gltf, blob, anim["samplers"][ch["sampler"]]["output"])
        rotation[ch["target"]["node"]] = quats[frame]

    parent = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    world = {}

    def world_of(i):
        if i not in world:
            local = np.eye(4)
            if i in rotation:
                local[:3, :3] = Rotation.from_quat(rotation[i]).as_matrix()
            local[:3, 3] = nodes[i].get("translation", [0, 0, 0])
            world[i] = local if i not in parent else world_of(parent[i]) @ local
        return world[i]

    ibm = _accessor(gltf, blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4)
    joint_mats = [world_of(n) @ ibm[k].T for k, n in enumerate(skin["joints"])]

    prim = gltf["meshes"][0]["primitives"][0]["attributes"]
    pos = _accessor(gltf, blob, prim["POSITION"]).astype(float)
    out = np.zeros_like(pos)
    homogeneous = np.c_[pos, np.ones(len(pos))]
    s = 0
    while f"JOINTS_{s}" in prim:
        idx = _accessor(gltf, blob, prim[f"JOINTS_{s}"])
        w = _accessor(gltf, blob, prim[f"WEIGHTS_{s}"])
        for c in range(4):
            mats = np.array(joint_mats)[idx[:, c]]
            out += w[:, c, None] * np.einsum("vij,vj->vi", mats, homogeneous)[:, :3]
        s += 1
    return out


def test_glb_structure_and_skinning(tmp_path, rig):
    path = tmp_path / "anim.glb"
    gltf_export.export(rig, str(path))
    gltf, blob = _read_glb(path)

    assert gltf["asset"]["version"] == "2.0"
    assert len(gltf["skins"][0]["joints"]) == 25
    assert len(gltf["animations"][0]["channels"]) == 24
    times = _accessor(gltf, blob, gltf["animations"][0]["samplers"][0]["input"])
    np.testing.assert_allclose(times, np.arange(20) / 30, atol=1e-6)

    prim = gltf["meshes"][0]["primitives"][0]["attributes"]
    weights = _accessor(gltf, blob, prim["WEIGHTS_0"])
    np.testing.assert_allclose(weights.sum(axis=1), 1.0, atol=1e-6)

    for frame in (0, 7, 19):
        np.testing.assert_allclose(_skin_from_file(gltf, blob, frame),
                                   posed_vertices(rig, frame), atol=1e-5)


def test_gltf_with_bin(tmp_path, rig):
    path = tmp_path / "anim.gltf"
    gltf_export.export(rig, str(path))
    gltf = json.loads(path.read_text())
    blob = (tmp_path / "anim.bin").read_bytes()
    assert gltf["buffers"][0] == {"byteLength": len(blob), "uri": "anim.bin"}
    np.testing.assert_allclose(_skin_from_file(gltf, blob, 5),
                               posed_vertices(rig, 5), atol=1e-5)


def test_quaternions_stay_on_one_hemisphere(rig):
    from exporters.skinning import rotation_quaternions
    q = rotation_quaternions(rig.rotations)
    assert np.all(np.sum(q[1:] * q[:-1], axis=2) >= 0)


@pytest.mark.parametrize("max_influences", [4, 8])
def test_vertex_influences_keep_all_weight(rig, max_influences):
    from exporters.skinning import vertex_influences
    idx, w = vertex_influences(rig.weights, max_influences)
    assert idx.shape == w.shape == (rig.weights.shape[1], max_influences)
    np.testing.assert_allclose(w.sum(axis=1), 1.0)
