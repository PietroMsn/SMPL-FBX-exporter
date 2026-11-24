"""
animate.py
Bake SMPL joint rotations as FBX animation curves on the skeleton.
"""

from fbx import FbxAnimCurveDef, FbxTime

from smpl_math import NUM_JOINTS

LINEAR = FbxAnimCurveDef.eInterpolationLinear
CUBIC = FbxAnimCurveDef.eInterpolationCubic


def _write_curves(prop, anim_layer, times, values, interpolation):
    """Write one key per frame on the X/Y/Z curves of an FBX property."""
    fbx_time = FbxTime()
    for axis, channel in enumerate("XYZ"):
        curve = prop.GetCurve(anim_layer, channel, True)
        curve.KeyModifyBegin()
        for t, value in zip(times, values):
            fbx_time.SetSecondDouble(t)
            key = curve.KeyAdd(fbx_time)[0]
            curve.KeySetValue(key, float(value[axis]))
            curve.KeySetInterpolation(key, interpolation)
        curve.KeyModifyEnd()


def bake_animation(joints, anim_layer, rotations, root_position, fps):
    """
    Write rotation keyframes for all 24 SMPL joints.

    The Pelvis (joint 0) also gets translation keys and uses linear
    interpolation; the other joints use cubic interpolation.

    Parameters
    ----------
    joints        : list of >= 24 FbxNode objects.
    anim_layer    : FbxAnimLayer to write curves into.
    rotations     : (F, 24, 3) Euler angles in degrees, one row per frame.
    root_position : (3,) Pelvis position written on every frame.
    fps           : Frames per second of the source sequence.
    """
    num_frames = len(rotations)
    times = [i / fps for i in range(num_frames)]

    for j in range(NUM_JOINTS):
        print(f"Baking joint {j + 1}/{NUM_JOINTS}", flush=True)
        node = joints[j]
        interpolation = LINEAR if j == 0 else CUBIC
        _write_curves(node.LclRotation, anim_layer, times, rotations[:, j], interpolation)
        if j == 0:
            _write_curves(node.LclTranslation, anim_layer, times,
                          [root_position] * num_frames, LINEAR)
