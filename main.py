'''
main.py
Entry point: loads SMPL pose data, builds the FBX scene, and exports it.

Usage
-----
    python main.py <pose_mat> <output_name> <mesh_mat> <scale>

Arguments
---------
pose_mat    : Path to the SURREAL .mat file containing pose data.
output_name : Base name for the output .fbx file (no extension).
mesh_mat    : Path to the .mat file containing mesh geometry (VERT, TRIV).
scale       : Integer scale factor applied to vertex coordinates.


'''

import sys

import fbx
import FbxCommon
from fbx import (
    FbxManager, FbxIOSettings, FbxScene,
    FbxAnimStack, FbxAnimLayer,
    FbxExporter, FbxMesh, FbxVector4,
    IOSROOT, EXP_FBX_EMBEDDED,
)
import scipy.io as sio
import numpy as np

from serialization import load_model
from geometry import load_geometry_from_args
from skeleton import create_skinned_mesh
from animate import bake_animation


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SMPL_MODEL_PATH = "./models/basicmodel_m_lbs_10_207_0_v1.0.0.pkl"
OUTPUT_DIR      = "./resFbx/Buff/"
INIT_FRAME      = 0


# ---------------------------------------------------------------------------
# Scene construction
# ---------------------------------------------------------------------------

def _build_mesh(sdk_manager, name):
    """Create an FbxMesh populated with vertices and triangles from the mesh .mat."""
    mesh = FbxMesh.Create(sdk_manager, name)

    vertices, faces = load_geometry_from_args()

    # Control points
    mesh.InitControlPoints(len(vertices))
    for idx, v in enumerate(vertices):
        mesh.SetControlPointAt(FbxVector4(v[0], v[1], v[2]), idx)

    # Triangles
    for face in faces:
        mesh.BeginPolygon()
        mesh.AddPolygon(int(face[0]))
        mesh.AddPolygon(int(face[1]))
        mesh.AddPolygon(int(face[2]))
        mesh.EndPolygon()

    mesh.RemoveBadPolygons()
    return mesh


def create_scene(sdk_manager, scene, pose_mat_path):
    """
    Populate *scene* with the animated SMPL human model.

    Parameters
    ----------
    sdk_manager   : FbxManager instance.
    scene         : FbxScene instance to populate.
    pose_mat_path : Path to the SURREAL pose .mat file.

    Returns
    -------
    True on success.
    """
    smpl_model = load_model(SMPL_MODEL_PATH)
    pose_mat   = sio.loadmat(pose_mat_path)
    final_frame = len(pose_mat["pose"][0])

    # Build mesh geometry
    raw_mesh = _build_mesh(sdk_manager, "human")

    # Attach skeleton + skinning
    mesh_node, joints, skinned_mesh = create_skinned_mesh(
        sdk_manager, scene, smpl_model, raw_mesh
    )
    mesh_node.SetNodeAttribute(skinned_mesh)

    # Create animation stack + base layer
    anim_stack = FbxAnimStack.Create(scene, "Take001")
    anim_layer = FbxAnimLayer.Create(scene, "Base Layer")
    anim_stack.AddMember(anim_layer)

    # Bake keyframes
    bake_animation(
        mesh_node, joints, anim_layer, scene,
        rotation=True,
        pose_mat=pose_mat,
        init_frame=INIT_FRAME,
        final_frame=final_frame,
        use_translation=False,
        smpl_model=smpl_model,
    )

    return True


# ---------------------------------------------------------------------------
# FBX export
# ---------------------------------------------------------------------------

def _init_sdk():
    """Initialise the FBX SDK manager and I/O settings."""
    sdk_manager = FbxManager.Create()
    io_settings = FbxIOSettings.Create(sdk_manager, IOSROOT)
    sdk_manager.SetIOSettings(io_settings)
    sdk_manager.GetIOSettings().SetBoolProp(EXP_FBX_EMBEDDED, False)
    return sdk_manager, io_settings


def _export_scene(sdk_manager, scene, output_name):
    """Save *scene* to ``OUTPUT_DIR/<output_name>.fbx``."""
    file_format = sdk_manager.GetIOPluginRegistry().GetNativeWriterFormat()
    output_path = OUTPUT_DIR + output_name + ".fbx"

    exporter = FbxExporter.Create(sdk_manager, "")
    exporter.Initialize(output_path, file_format, sdk_manager.GetIOSettings())
    exporter.Export(scene)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 5:
        print("Usage: python main.py <pose_mat> <output_name> <mesh_mat> <scale>")
        sys.exit(1)

    pose_mat_path = sys.argv[1]
    output_name   = sys.argv[2]

    sdk_manager, _ = _init_sdk()
    scene = FbxScene.Create(sdk_manager, "")

    create_scene(sdk_manager, scene, pose_mat_path)

    # Intermediate save (debug helper)
    FbxCommon.SaveScene(sdk_manager, scene, "prova")

    _export_scene(sdk_manager, scene, output_name)

    exporter = FbxExporter.Create(sdk_manager, "")

    # exports the scene in fbx format at the path:
    save_path = "./resFbx/"
    filename = sys.argv[2] + "_newAnimation.fbx"

    lFileFormat = sdk_manager.GetIOPluginRegistry().GetNativeWriterFormat()

    # Specify the path and name of the file to be imported
    _ = exporter.Initialize(save_path + filename, lFileFormat, sdk_manager.GetIOSettings())

    _ = exporter.Export(scene)

    sdk_manager.Destroy()
    sys.exit(0)


if __name__ == "__main__":
    main()
