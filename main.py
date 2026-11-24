"""
main.py
Convert an SMPL pose sequence (e.g. from SURREAL) into a rigged, skinned and
animated 3D file: FBX, glTF 2.0 or USD.

Run ``python main.py --help`` for usage.
"""

import argparse
import os
import sys

import exporters
from rig import build_rig
from smpl_model import find_model

MODELS_DIR = "models"
DEFAULT_FPS = 30.0  # SURREAL videos are rendered at 30 fps


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Export an SMPL pose sequence as an animated FBX, glTF or USD file.")
    p.add_argument("pose_mat", help=".mat file with a 'pose' array (72 x frames), "
                                    "e.g. a SURREAL *_info.mat file")
    p.add_argument("mesh_mat", nargs="?",
                   help="optional .mat file with a custom T-pose body in SMPL topology "
                        "('VERT', optional 'TRIV'). Default: the SMPL template mesh")
    p.add_argument("-o", "--output",
                   help="output path; its extension picks the format if --format is not "
                        "given (.fbx, .glb, .gltf, .usd, .usda, .usdc, .usdz). "
                        "Default: output/<pose file name>.<format extension>")
    p.add_argument("-f", "--format", choices=sorted(exporters.FORMATS),
                   help="output format (default: from the --output extension, else fbx)")
    p.add_argument("--model",
                   help="official SMPL model file (.pkl or .npz). Default: the first "
                        f"SMPL model found in {MODELS_DIR}/")
    p.add_argument("-s", "--scale", type=float, default=1.0,
                   help="scale factor applied to the mesh (default: 1, i.e. metres)")
    p.add_argument("--fps", type=float, default=DEFAULT_FPS,
                   help=f"frame rate of the animation (default: {DEFAULT_FPS:g})")
    p.add_argument("--up-axis", choices=["y", "z"], default="y",
                   help="axis pointing up in the pose data. Raw SURREAL *_info.mat files "
                        "are Z-up: use 'z' so the character stands upright (default: y)")
    p.add_argument("--start", type=int, default=0, help="first frame (inclusive)")
    p.add_argument("--end", type=int, help="last frame (exclusive, default: all)")
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
        args.output = os.path.join("output", stem + exporters.FORMATS[args.format][1])
    return args


def main(argv=None):
    args = parse_args(argv)

    model = args.model or find_model(MODELS_DIR)
    if model is None:
        raise SystemExit(
            f"No SMPL model found in {MODELS_DIR}/. Download it from "
            "https://smpl.is.tue.mpg.de (free registration), put the .pkl file in "
            f"{MODELS_DIR}/ or pass it with --model.")

    rig = build_rig(args.pose_mat, model, args.mesh_mat,
                    scale=args.scale, fps=args.fps, start=args.start, end=args.end,
                    up_axis=args.up_axis)
    exporters.export(rig, args.output, args.format)
    print(f"Exported {rig.num_frames} frames to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
