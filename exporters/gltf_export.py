"""
gltf_export.py
Write a :class:`rig.Rig` as glTF 2.0: binary ``.glb`` or ``.gltf`` + ``.bin``.

Pure numpy, no extra dependency. Joint rotations are stored as quaternions
with LINEAR interpolation (spherical interpolation in glTF).
"""

import json
import os
import struct

import numpy as np

from rig import JOINT_NAMES, JOINT_ORDER, JOINT_PARENT
from smpl_math import NUM_JOINTS
from exporters.skinning import (
    SKIN_INDEX, rotation_quaternions, vertex_influences, vertex_normals,
)

FLOAT, UNSIGNED_BYTE, UNSIGNED_SHORT, UNSIGNED_INT = 5126, 5121, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
TYPE_BY_WIDTH = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4", 16: "MAT4"}
COMPONENT_BY_DTYPE = {
    np.dtype(np.float32): FLOAT,
    np.dtype(np.uint8): UNSIGNED_BYTE,
    np.dtype(np.uint16): UNSIGNED_SHORT,
    np.dtype(np.uint32): UNSIGNED_INT,
}


class _Builder:
    """Accumulates binary data, buffer views and accessors."""

    def __init__(self):
        self.blob = bytearray()
        self.buffer_views = []
        self.accessors = []

    def add(self, array, target=None, min_max=False):
        array = np.ascontiguousarray(array)
        width = 1 if array.ndim == 1 else array.shape[1]

        while len(self.blob) % 4:
            self.blob.append(0)
        view = {"buffer": 0, "byteOffset": len(self.blob), "byteLength": array.nbytes}
        if target is not None:
            view["target"] = target
        self.blob.extend(array.tobytes())
        self.buffer_views.append(view)

        accessor = {
            "bufferView": len(self.buffer_views) - 1,
            "componentType": COMPONENT_BY_DTYPE[array.dtype],
            "count": len(array),
            "type": TYPE_BY_WIDTH[width],
        }
        if min_max:
            flat = array.reshape(len(array), width)
            accessor["min"] = flat.min(axis=0).tolist()
            accessor["max"] = flat.max(axis=0).tolist()
        self.accessors.append(accessor)
        return len(self.accessors) - 1


def build_gltf(rig):
    """Return ``(gltf_json_dict, binary_blob)`` for *rig*."""
    b = _Builder()

    # --- Mesh ---------------------------------------------------------------
    positions = rig.vertices.astype(np.float32)
    normals = vertex_normals(rig.vertices, rig.faces).astype(np.float32)
    index_dtype = np.uint16 if len(positions) < 65535 else np.uint32
    indices = rig.faces.astype(index_dtype).reshape(-1)

    attributes = {
        "POSITION": b.add(positions, ARRAY_BUFFER, min_max=True),
        "NORMAL": b.add(normals, ARRAY_BUFFER),
    }
    joint_idx, joint_w = vertex_influences(rig.weights)
    for s in range(joint_idx.shape[1] // 4):
        cols = slice(4 * s, 4 * s + 4)
        attributes[f"JOINTS_{s}"] = b.add(joint_idx[:, cols].astype(np.uint8), ARRAY_BUFFER)
        attributes[f"WEIGHTS_{s}"] = b.add(joint_w[:, cols].astype(np.float32), ARRAY_BUFFER)

    mesh = {
        "name": "human",
        "primitives": [{
            "attributes": attributes,
            "indices": b.add(indices, ELEMENT_ARRAY_BUFFER),
            "mode": 4,  # triangles
        }],
    }

    # --- Joint nodes ----------------------------------------------------------
    # node index of joint j == SKIN_INDEX[j]; the mesh node comes last
    nodes = []
    for j in JOINT_ORDER:
        node = {"name": JOINT_NAMES[j]}
        offset = rig.rest_offsets[j]
        if np.any(offset):
            node["translation"] = [float(x) for x in offset]
        children = [SKIN_INDEX[c] for c in JOINT_ORDER if JOINT_PARENT[c] == j]
        if children:
            node["children"] = children
        nodes.append(node)
    mesh_node = len(nodes)
    nodes.append({"name": "human", "mesh": 0, "skin": 0})

    # Inverse bind matrices: rest joints are pure translations (column-major)
    world = rig.rest_world_positions()
    ibm = np.tile(np.eye(4, dtype=np.float32), (len(JOINT_ORDER), 1, 1))
    for i, j in enumerate(JOINT_ORDER):
        ibm[i, 3, :3] = -world[j]  # row 3 of the transposed (column-major) matrix
    skin = {
        "name": "skeleton",
        "joints": list(range(len(JOINT_ORDER))),
        "skeleton": SKIN_INDEX[JOINT_ORDER[0]],
        "inverseBindMatrices": b.add(ibm.reshape(-1, 16)),
    }

    # --- Animation ------------------------------------------------------------
    times = b.add(rig.times.astype(np.float32), min_max=True)
    quats = rotation_quaternions(rig.rotations).astype(np.float32)
    samplers, channels = [], []
    for j in range(NUM_JOINTS):
        samplers.append({"input": times, "output": b.add(quats[:, j]),
                         "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1,
                         "target": {"node": SKIN_INDEX[j], "path": "rotation"}})

    gltf = {
        "asset": {"version": "2.0", "generator": "SMPL-FBX-exporter"},
        "scene": 0,
        "scenes": [{"name": "character", "nodes": [SKIN_INDEX[JOINT_ORDER[0]], mesh_node]}],
        "nodes": nodes,
        "meshes": [mesh],
        "skins": [skin],
        "animations": [{"name": "Take001", "samplers": samplers, "channels": channels}],
        "accessors": b.accessors,
        "bufferViews": b.buffer_views,
        "buffers": [{"byteLength": len(b.blob)}],
    }
    return gltf, bytes(b.blob)


def _pad(data, fill):
    return data + fill * (-len(data) % 4)


def export(rig, output_path):
    """Write *rig* as ``.glb`` (single binary file) or ``.gltf`` + ``.bin``."""
    gltf, blob = build_gltf(rig)

    if output_path.lower().endswith(".gltf"):
        bin_name = os.path.splitext(os.path.basename(output_path))[0] + ".bin"
        gltf["buffers"][0]["uri"] = bin_name
        with open(os.path.join(os.path.dirname(output_path), bin_name), "wb") as f:
            f.write(blob)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(gltf, f, indent=1)
        return

    json_chunk = _pad(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    bin_chunk = _pad(blob, b"\0")
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    with open(output_path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(json_chunk), b"JSON"))
        f.write(json_chunk)
        f.write(struct.pack("<I4s", len(bin_chunk), b"BIN\0"))
        f.write(bin_chunk)
