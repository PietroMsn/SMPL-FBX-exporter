"""
main.py
Convert a SURREAL pose sequence into a rigged, skinned and animated 3D file:
FBX, glTF 2.0 or USD.

Run ``python main.py --help`` for usage.
"""

import argparse
import os
import sys

import exporters
from rig import build_rig

DEFAULT_MODEL = os.path.join("models", "basicmodel_m_lbs_10_207_0_v1.0.0.pkl")
DEFAULT_WEIGHTS = "myWeights.npy"
DEFAULT_FPS = 30.0  # SURREAL videos are rendered at 30 fps


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Export a SURREAL/SMPL pose sequence as an animated FBX, glTF or USD file.")
    p.add_argument("pose_mat", help="SURREAL *_info.mat file with a 'pose' array (72 x F)")
    p.add_argument("mesh_mat", help=".mat file with the mesh ('VERT' and 'TRIV')")
    p.add_argument("-o", "--output",
                   help="output path; its extension picks the format if --format is not "
                        "given (.fbx, .glb, .gltf, .usd, .usda, .usdc, .usdz). "
                        "Default: resFbx/<pose file name>.<format extension>")
    p.add_argument("-f", "--format", choices=sorted(exporters.FORMATS),
                   help="output format (default: from the --output extension, else fbx)")
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

    if args.output:
        guessed = exporters.format_from_path(args.output)
        if args.format is None:
            if guessed is None:
                p.error(f"cannot tell the format from '{args.output}': use --format")
            args.format = guessed
        elif guessed != args.format:
            p.error(f"--format {args.format} does not match the extension of '{args.output}'")
    else:
        args.format = args.format or "fbx"
        stem = os.path.splitext(os.path.basename(args.pose_mat))[0]
        args.output = os.path.join("resFbx", stem + exporters.FORMATS[args.format][1])
    return args


def main(argv=None):
    args = parse_args(argv)
    rig = build_rig(args.pose_mat, args.mesh_mat, args.model, args.weights,
                    scale=args.scale, fps=args.fps, start=args.start, end=args.end)
    exporters.export(rig, args.output, args.format)
    print(f"Exported {rig.num_frames} frames to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
