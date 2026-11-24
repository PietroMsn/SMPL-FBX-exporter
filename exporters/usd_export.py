"""
usd_export.py
Write a :class:`rig.Rig` as OpenUSD with UsdSkel (``.usd``, ``.usda``,
``.usdc`` or ``.usdz``). Requires ``pip install usd-core``.

Layout::

    /Character              SkelRoot
        /Skeleton           Skeleton  (bind + rest transforms)
            /Animation      SkelAnimation  (per-frame joint rotations)
        /Human              Mesh  (bound to /Character/Skeleton)
"""

import os
import shutil
import tempfile

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, UsdUtils, Vt

from rig import JOINT_NAMES, JOINT_ORDER, JOINT_PARENT, ROOT
from exporters.skinning import rotation_quaternions, vertex_influences, vertex_normals


def _joint_paths():
    """UsdSkel joint tokens, e.g. "Root/Pelvis/L_Hip", in JOINT_ORDER."""
    paths = {}
    for j in JOINT_ORDER:
        parent = JOINT_PARENT[j]
        paths[j] = JOINT_NAMES[j] if parent is None else paths[parent] + "/" + JOINT_NAMES[j]
    return [paths[j] for j in JOINT_ORDER]


def _translation_matrix(t):
    return Gf.Matrix4d(1.0).SetTranslate(Gf.Vec3d(*map(float, t)))


def _write_stage(rig, path):
    stage = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetTimeCodesPerSecond(rig.fps)
    stage.SetFramesPerSecond(rig.fps)
    stage.SetStartTimeCode(0)
    stage.SetEndTimeCode(rig.num_frames - 1)

    root = UsdSkel.Root.Define(stage, "/Character")
    stage.SetDefaultPrim(root.GetPrim())

    # --- Skeleton -------------------------------------------------------------
    joints = Vt.TokenArray(_joint_paths())
    world = rig.rest_world_positions()
    skel = UsdSkel.Skeleton.Define(stage, "/Character/Skeleton")
    skel.CreateJointsAttr(joints)
    skel.CreateJointNamesAttr(Vt.TokenArray([JOINT_NAMES[j] for j in JOINT_ORDER]))
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(
        [_translation_matrix(world[j]) for j in JOINT_ORDER]))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(
        [_translation_matrix(rig.rest_offsets[j]) for j in JOINT_ORDER]))

    # --- Animation ------------------------------------------------------------
    anim = UsdSkel.Animation.Define(stage, "/Character/Skeleton/Animation")
    anim.CreateJointsAttr(joints)
    anim.CreateTranslationsAttr(Vt.Vec3fArray(
        [Gf.Vec3f(*map(float, rig.rest_offsets[j])) for j in JOINT_ORDER]))
    anim.CreateScalesAttr(Vt.Vec3hArray([Gf.Vec3h(1, 1, 1)] * len(JOINT_ORDER)))

    quats = rotation_quaternions(rig.rotations)  # (F, 24, 4) x, y, z, w
    identity = Gf.Quatf(1.0)
    rotations_attr = anim.CreateRotationsAttr()
    for frame in range(rig.num_frames):
        per_joint = [identity if j == ROOT else
                     Gf.Quatf(float(quats[frame, j, 3]), Gf.Vec3f(*map(float, quats[frame, j, :3])))
                     for j in JOINT_ORDER]
        rotations_attr.Set(Vt.QuatfArray(per_joint), Usd.TimeCode(frame))

    UsdSkel.BindingAPI.Apply(skel.GetPrim()).CreateAnimationSourceRel().SetTargets(
        [anim.GetPath()])

    # --- Mesh -----------------------------------------------------------------
    mesh = UsdGeom.Mesh.Define(stage, "/Character/Human")
    mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(rig.vertices.astype(np.float32)))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(rig.faces)))
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(
        rig.faces.reshape(-1).astype(np.int32)))
    mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(
        vertex_normals(rig.vertices, rig.faces).astype(np.float32)))
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateExtentAttr(UsdGeom.PointBased.ComputeExtent(mesh.GetPointsAttr().Get()))

    joint_idx, joint_w = vertex_influences(rig.weights)
    influences = joint_idx.shape[1]
    binding = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
    binding.CreateSkeletonRel().SetTargets([skel.GetPath()])
    binding.CreateJointIndicesPrimvar(False, influences).Set(
        Vt.IntArray.FromNumpy(joint_idx.reshape(-1).astype(np.int32)))
    binding.CreateJointWeightsPrimvar(False, influences).Set(
        Vt.FloatArray.FromNumpy(joint_w.reshape(-1).astype(np.float32)))
    binding.CreateGeomBindTransformAttr(Gf.Matrix4d(1.0))

    stage.GetRootLayer().Save()


def export(rig, output_path):
    """Write *rig* as USD; the extension selects text, binary or usdz."""
    if not output_path.lower().endswith(".usdz"):
        _write_stage(rig, output_path)
        return

    # usdz is a zip package: write a .usdc first, then package it
    tmp_dir = tempfile.mkdtemp()
    try:
        name = os.path.splitext(os.path.basename(output_path))[0] + ".usdc"
        layer = os.path.join(tmp_dir, name)
        _write_stage(rig, layer)
        if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(layer), output_path):
            raise RuntimeError("Failed to create the usdz package")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
