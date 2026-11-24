"""
main.py
Convert a SURREAL pose sequence into a rigged, skinned and animated FBX file.

Run ``python main.py --help`` for usage.
"""

import argparse
import os
import sys

import numpy as np
import scipy.io as sio
from fbx import (
    FbxManager, FbxIOSettings, FbxScene,
    FbxAnimStack, FbxAnimLayer,
    FbxExporter, FbxMesh, FbxVector4,
    IOSROOT, EXP_FBX_EMBEDDED,
)

from animate import bake_animation
from geometry import load_geometry
from skeleton import create_skinned_mesh
from smpl_math import calc_local_position, pose_to_joint_rotations
from smpl_model import load_joint_regressor

DEFAULT_MODEL = os.path.join("models", "basicmodel_m_lbs_10_207_0_v1.0.0.pkl")
DEFAULT_WEIGHTS = "myWeights.npy"
DEFAULT_FPS = 30.0  # SURREAL videos are rendered at 30 fps


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Export a SURREAL/SMPL pose sequence as an animated FBX.")
    p.add_argument("pose_mat", help="SURREAL *_info.mat file with a 'pose' array (72 x F)")
    p.add_argument("mesh_mat", help=".mat file with the mesh ('VERT' and 'TRIV')")
    p.add_argument("-o", "--output",
                   help="output .fbx path (default: resFbx/<pose file name>.fbx)")
    p.add_argument("-s", "--scale", type=float, default=1.0,
                   help="scale factor applied to the mesh vertices (default: 1)")
    p.add_argument("--fps", type=float, default=DEFAULT_FPS,
                   help=f"frame rate of the animation (default: {DEFAULT_FPS:g})")
    p.add_argument("--start", type=int, default=0, help="first frame (inclusive)")
    p.add_argument("--end", type=int, help="last frame (exclusive, default: all)")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help="SMPL model .pkl, or .npy/.npz with J_regressor "
                        f"(default: {DEFAULT_MODEL})")
    p.add_argument("--weights", default=DEFAULT_WEIGHTS,
                   help=f"skin weights .npy of shape (24, N) (default: {DEFAULT_WEIGHTS})")
    args = p.parse_args(argv)

    if args.output is None:
        stem = os.path.splitext(os.path.basename(args.pose_mat))[0]
        args.output = os.path.join("resFbx", stem + ".fbx")
    return args


def build_mesh(sdk_manager, vertices, faces, name="human"):
    """Create an FbxMesh from vertex and triangle arrays."""
    mesh = FbxMesh.Create(sdk_manager, name)

    mesh.InitControlPoints(len(vertices))
    for idx, v in enumerate(vertices):
        mesh.SetControlPointAt(FbxVector4(*map(float, v)), idx)

    for face in faces:
        mesh.BeginPolygon()
        for vert_idx in face:
            mesh.AddPolygon(int(vert_idx))
        mesh.EndPolygon()

    mesh.RemoveBadPolygons()
    return mesh


def create_scene(sdk_manager, scene, args):
    """Populate *scene* with the skinned, animated SMPL character."""
    regressor = load_joint_regressor(args.model)
    weights = np.load(args.weights)
    vertices, faces = load_geometry(args.mesh_mat, args.scale)
    poses = sio.loadmat(args.pose_mat)["pose"].T[args.start:args.end]  # (F, 72)
    if len(poses) == 0:
        raise ValueError("No frames selected: check --start/--end")

    local_positions = calc_local_position(regressor, vertices)
    rotations = pose_to_joint_rotations(poses)

    mesh = build_mesh(sdk_manager, vertices, faces)
    _, joints = create_skinned_mesh(sdk_manager, scene, mesh, local_positions, weights)

    anim_stack = FbxAnimStack.Create(scene, "Take001")
    anim_layer = FbxAnimLayer.Create(scene, "Base Layer")
    anim_stack.AddMember(anim_layer)

    bake_animation(joints, anim_layer, rotations, local_positions[0], args.fps)
    return len(poses)


def export_scene(sdk_manager, scene, output_path):
    """Write *scene* to *output_path* in binary FBX format."""
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    file_format = sdk_manager.GetIOPluginRegistry().GetNativeWriterFormat()
    exporter = FbxExporter.Create(sdk_manager, "")
    try:
        if not exporter.Initialize(output_path, file_format, sdk_manager.GetIOSettings()):
            raise RuntimeError(exporter.GetStatus().GetErrorString())
        if not exporter.Export(scene):
            raise RuntimeError(exporter.GetStatus().GetErrorString())
    finally:
        exporter.Destroy()


def main(argv=None):
    args = parse_args(argv)

    sdk_manager = FbxManager.Create()
    try:
        io_settings = FbxIOSettings.Create(sdk_manager, IOSROOT)
        io_settings.SetBoolProp(EXP_FBX_EMBEDDED, False)
        sdk_manager.SetIOSettings(io_settings)

        scene = FbxScene.Create(sdk_manager, "")
        num_frames = create_scene(sdk_manager, scene, args)
        export_scene(sdk_manager, scene, args.output)
    finally:
        sdk_manager.Destroy()

    print(f"Exported {num_frames} frames to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
