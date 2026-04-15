"""
animate.py
Bake SMPL pose data as FBX animation curves on a skeleton.

Dependency chain:  smpl_math  <-  geometry  <-  animate
                   (no import of skeleton or main)

Functions
---------
compute_frame_pose  Compute joint rotations and positions for one frame.
bake_animation      Write FBX keyframe curves for all joints.
"""

import sys

import numpy as np
from fbx import FbxAnimCurveDef, FbxTime

from smpl_math import calc_local_position, pose_to_joint_rotations, NUM_JOINTS
from geometry import load_geometry_from_args


# ---------------------------------------------------------------------------
# Per-frame pose
# ---------------------------------------------------------------------------

def compute_frame_pose(frame, pose_mat, smpl_model):
    """
    Set the SMPL model to the given frame and extract joint data.

    Parameters
    ----------
    frame      : Frame index into ``pose_mat["pose"]``.
    pose_mat   : Dict loaded from a SURREAL .mat file (key ``"pose"``).
    smpl_model : SMPL model object whose ``pose`` attribute will be mutated.

    Returns
    -------
    joint_rotation : (24, 3) float array - Euler angles in degrees.
    local_position : list of 24 [x, y, z] parent-relative joint positions.
    translation    : [0, 0, 0] placeholder (global translation unused).
    """
    smpl_model.pose[:] = pose_mat["pose"][:, frame]

    vertices, _ = load_geometry_from_args()
    local_position = calc_local_position(smpl_model, vertices)
    joint_rotation = pose_to_joint_rotations(smpl_model)

    return joint_rotation, local_position, [0, 0, 0]


# ---------------------------------------------------------------------------
# FBX curve helpers (private)
# ---------------------------------------------------------------------------

def _add_key(curve, time):
    return curve.KeyAdd(time)[0]


def _set_key(curve, key_index, value,
             interpolation=FbxAnimCurveDef.eInterpolationLinear):
    curve.KeySetValue(key_index, value)
    curve.KeySetInterpolation(key_index, interpolation)


# ---------------------------------------------------------------------------
# Animation baking
# ---------------------------------------------------------------------------

def bake_animation(
    mesh_node,
    joints,
    anim_layer,
    scene,
    rotation,
    pose_mat,
    init_frame,
    final_frame,
    use_translation,
    smpl_model
):
    """
    Write FBX keyframe curves for all 24 SMPL joints.

    For the root joint (index 0) both rotation and translation curves are
    always written.  For all other joints only rotation *or* translation
    curves are written, depending on the *rotation* flag.

    Parameters
    ----------
    mesh_node       : Root FBX mesh node (unused, kept for API symmetry).
    joints          : List of >=24 FbxNode objects.
    anim_layer      : FbxAnimLayer to write curves into.
    scene           : FbxScene instance.
    rotation        : If True, bake ``LclRotation``; else bake ``LclTranslation``.
    pose_mat        : SURREAL pose dict.
    init_frame      : First frame index (inclusive).
    final_frame     : Last frame index (exclusive).
    use_translation : Apply global translation offset to the root joint.
    smpl_model      : SMPL model object.
    """
    CUBIC  = FbxAnimCurveDef.eInterpolationCubic
    LINEAR = FbxAnimCurveDef.eInterpolationLinear

    fbx_time = FbxTime()

    for joint_idx in range(NUM_JOINTS):
        sys.stdout.write("Baking joint " + str(joint_idx) + "/" + str(NUM_JOINTS) + "\n")
        sys.stdout.flush()

        node = joints[joint_idx]

        # Primary curves (rotation or positional, depending on mode)
        if rotation:
            cx = node.LclRotation.GetCurve(anim_layer, "X", True)
            cy = node.LclRotation.GetCurve(anim_layer, "Y", True)
            cz = node.LclRotation.GetCurve(anim_layer, "Z", True)
        else:
            cx = node.LclTranslation.GetCurve(anim_layer, "X", True)
            cy = node.LclTranslation.GetCurve(anim_layer, "Y", True)
            cz = node.LclTranslation.GetCurve(anim_layer, "Z", True)

        # Translation curves (written only for the root joint)
        ctx = node.LclTranslation.GetCurve(anim_layer, "X", True)
        cty = node.LclTranslation.GetCurve(anim_layer, "Y", True)
        ctz = node.LclTranslation.GetCurve(anim_layer, "Z", True)

        all_curves = (cx, cy, cz, ctx, cty, ctz)
        for curve in all_curves:
            curve.KeyModifyBegin()

        time_offset = 0.0

        for frame in range(init_frame, final_frame):
            joint_rot, local_pos, trans = compute_frame_pose(frame, pose_mat, smpl_model)

            fbx_time.SetSecondDouble(time_offset)

            kx = _add_key(cx, fbx_time)
            ky = _add_key(cy, fbx_time)
            kz = _add_key(cz, fbx_time)

            if joint_idx == 0:
                # Root joint: drive both rotation and world translation
                ktx = _add_key(ctx, fbx_time)
                kty = _add_key(cty, fbx_time)
                ktz = _add_key(ctz, fbx_time)

                _set_key(cx, kx, joint_rot[0][0], LINEAR)
                _set_key(cy, ky, joint_rot[0][1], LINEAR)
                _set_key(cz, kz, joint_rot[0][2], LINEAR)

                tx = local_pos[0][0] - trans[2] if use_translation else local_pos[0][0]
                ty = local_pos[0][1] + trans[0] if use_translation else local_pos[0][1]
                tz = local_pos[0][2] - trans[1] if use_translation else local_pos[0][2]

                _set_key(ctx, ktx, tx, LINEAR)
                _set_key(cty, kty, ty, LINEAR)
                _set_key(ctz, ktz, tz, LINEAR)

            else:
                if rotation:
                    _set_key(cx, kx, joint_rot[joint_idx][0], CUBIC)
                    _set_key(cy, ky, joint_rot[joint_idx][1], CUBIC)
                    _set_key(cz, kz, joint_rot[joint_idx][2], CUBIC)
                else:
                    _set_key(cx, kx,  local_pos[joint_idx][0], CUBIC)
                    _set_key(cy, ky, -local_pos[joint_idx][1], CUBIC)  # Y-axis flip
                    _set_key(cz, kz,  local_pos[joint_idx][2], CUBIC)

            # TODO: derive time step from actual video FPS for proper sync
            time_offset += 1.0 if frame in (0, 100) else 0.05

        for curve in all_curves:
            curve.KeyModifyEnd()
