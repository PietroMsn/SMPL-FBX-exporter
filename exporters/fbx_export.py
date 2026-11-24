"""
fbx_export.py
Write a :class:`rig.Rig` as a skinned, animated FBX file (Autodesk FBX SDK).
"""

import numpy as np
from fbx import (
    FbxManager, FbxIOSettings, FbxScene, FbxExporter,
    FbxNode, FbxSkeleton, FbxSkin, FbxCluster, FbxPose,
    FbxMesh, FbxMatrix, FbxDouble3, FbxVector4,
    FbxAnimStack, FbxAnimLayer, FbxAnimCurveDef, FbxTime,
    IOSROOT, EXP_FBX_EMBEDDED,
)

from rig import JOINT_NAMES, JOINT_ORDER, JOINT_PARENT, ROOT
from smpl_math import NUM_JOINTS, rodrigues_to_euler

LINEAR = FbxAnimCurveDef.eInterpolationLinear
CUBIC = FbxAnimCurveDef.eInterpolationCubic


# ---------------------------------------------------------------------------
# Scene construction
# ---------------------------------------------------------------------------

def _build_mesh(manager, rig):
    mesh = FbxMesh.Create(manager, "human")
    mesh.InitControlPoints(len(rig.vertices))
    for idx, v in enumerate(rig.vertices):
        mesh.SetControlPointAt(FbxVector4(*map(float, v)), idx)
    for face in rig.faces:
        mesh.BeginPolygon()
        for vert_idx in face:
            mesh.AddPolygon(int(vert_idx))
        mesh.EndPolygon()
    mesh.RemoveBadPolygons()
    return mesh


def _build_skeleton(manager, scene, rig):
    """Create the joint nodes (in rest pose) and the mesh node."""
    character = FbxNode.Create(manager, "character")
    mesh_node = FbxNode.Create(manager, "myMesh")
    scene.GetRootNode().AddChild(character)

    joints = [None] * (NUM_JOINTS + 1)
    for j in JOINT_ORDER:
        node = FbxNode.Create(manager, JOINT_NAMES[j])
        skel = FbxSkeleton.Create(manager, JOINT_NAMES[j] + "_skeleton")
        skel.SetSkeletonType(FbxSkeleton.eLimbNode)
        node.SetNodeAttribute(skel)
        node.LclTranslation.Set(FbxDouble3(*map(float, rig.rest_offsets[j])))
        node.LclRotation.Set(FbxDouble3(0.0, 0.0, 0.0))
        parent = JOINT_PARENT[j]
        (character if parent is None else joints[parent]).AddChild(node)
        joints[j] = node

    character.AddChild(mesh_node)
    return joints, mesh_node


def _make_cluster(scene, name, joint, mesh_matrix, weights=None):
    cluster = FbxCluster.Create(scene, name)
    if weights is not None:
        for vert_idx in np.flatnonzero(weights):
            cluster.AddControlPointIndex(int(vert_idx), float(weights[vert_idx]))
    cluster.SetLink(joint)
    cluster.SetLinkMode(FbxCluster.eNormalize)
    cluster.SetTransformMatrix(mesh_matrix)
    cluster.SetTransformLinkMatrix(joint.EvaluateGlobalTransform())
    return cluster


def _skin(manager, scene, rig, mesh, mesh_node, joints):
    skin = FbxSkin.Create(manager, "skin")
    mesh.AddDeformer(skin)
    mesh_node.SetNodeAttribute(mesh)
    mesh_matrix = mesh_node.EvaluateGlobalTransform()

    skin.AddCluster(_make_cluster(scene, "cluster_Root", joints[ROOT], mesh_matrix))
    for j in range(NUM_JOINTS):
        skin.AddCluster(_make_cluster(
            scene, "cluster_" + JOINT_NAMES[j], joints[j], mesh_matrix, rig.weights[j]))

    bind_pose = FbxPose.Create(manager, "bindPose")
    bind_pose.SetIsBindPose(True)
    for node in joints:
        bind_pose.Add(node, FbxMatrix(node.EvaluateGlobalTransform()))
    scene.AddPose(bind_pose)


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def _write_curves(prop, anim_layer, times, values, interpolation):
    """Write one key per frame on the X/Y/Z curves of an FBX property."""
    fbx_time = FbxTime()
    for axis, channel in enumerate("XYZ"):
        curve = prop.GetCurve(anim_layer, channel, True)
        curve.KeyModifyBegin()
        for t, value in zip(times, values):
            fbx_time.SetSecondDouble(float(t))
            key = curve.KeyAdd(fbx_time)[0]
            curve.KeySetValue(key, float(value[axis]))
            curve.KeySetInterpolation(key, interpolation)
        curve.KeyModifyEnd()


def _bake_animation(scene, rig, joints):
    """
    Rotation keys for all 24 joints (Euler XYZ, degrees). The Pelvis also gets
    translation keys and linear interpolation, the others cubic.
    """
    anim_stack = FbxAnimStack.Create(scene, "Take001")
    anim_layer = FbxAnimLayer.Create(scene, "Base Layer")
    anim_stack.AddMember(anim_layer)

    euler = rodrigues_to_euler(rig.rotations)  # (F, 24, 3)
    times = rig.times

    for j in range(NUM_JOINTS):
        print(f"Baking joint {j + 1}/{NUM_JOINTS}", flush=True)
        interpolation = LINEAR if j == 0 else CUBIC
        _write_curves(joints[j].LclRotation, anim_layer, times, euler[:, j], interpolation)
        if j == 0:
            _write_curves(joints[j].LclTranslation, anim_layer, times,
                          [rig.rest_offsets[0]] * rig.num_frames, LINEAR)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export(rig, output_path):
    """Write *rig* to *output_path* as a binary FBX file."""
    manager = FbxManager.Create()
    try:
        io_settings = FbxIOSettings.Create(manager, IOSROOT)
        io_settings.SetBoolProp(EXP_FBX_EMBEDDED, False)
        manager.SetIOSettings(io_settings)

        scene = FbxScene.Create(manager, "")
        mesh = _build_mesh(manager, rig)
        joints, mesh_node = _build_skeleton(manager, scene, rig)
        _skin(manager, scene, rig, mesh, mesh_node, joints)
        _bake_animation(scene, rig, joints)

        file_format = manager.GetIOPluginRegistry().GetNativeWriterFormat()
        exporter = FbxExporter.Create(manager, "")
        try:
            if not exporter.Initialize(output_path, file_format, manager.GetIOSettings()):
                raise RuntimeError(exporter.GetStatus().GetErrorString())
            if not exporter.Export(scene):
                raise RuntimeError(exporter.GetStatus().GetErrorString())
        finally:
            exporter.Destroy()
    finally:
        manager.Destroy()
