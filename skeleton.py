"""
skeleton.py
FBX skeleton hierarchy, skin deformer and bind pose.

Functions
---------
build_node_hierarchy    Create and wire the 25 FbxNode objects.
create_skinned_mesh     Attach skin clusters and bind pose to an FbxMesh.
"""

import numpy as np
from fbx import (
    FbxNode, FbxSkeleton, FbxSkin, FbxCluster,
    FbxPose, FbxMatrix, FbxDouble3,
)

from smpl_math import NUM_JOINTS

ROOT = NUM_JOINTS  # index of the virtual Root node

JOINT_NAMES = [
    "Pelvis",    "L_Hip",     "R_Hip",      "Spine1",
    "L_Knee",    "R_Knee",    "Spine2",     "L_Ankle",
    "R_Ankle",   "Spine3",    "L_Foot",     "R_Foot",
    "Neck",      "L_Collar",  "R_Collar",   "Head",
    "L_Shoulder","R_Shoulder","L_Elbow",    "R_Elbow",
    "L_Wrist",   "R_Wrist",   "L_Hand",     "R_Hand",
    "Root",      # index 24 - virtual root above the pelvis
]

# Parent index for each SMPL joint in the FBX hierarchy
# (SMPL topology; the Pelvis hangs from the virtual Root)
HIERARCHY_PARENT = [
    ROOT, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8,
    9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21,
]


def build_node_hierarchy(scene, manager):
    """
    Create the 25 skeleton nodes and the mesh node, wired into the scene.

    Returns
    -------
    joints    : list of 25 FbxNode objects (0-23 = SMPL joints, 24 = Root).
    mesh_node : FbxNode that will own the mesh.
    """
    character_node = FbxNode.Create(manager, "character")
    mesh_node = FbxNode.Create(manager, "myMesh")

    joints = []
    for name in JOINT_NAMES:
        node = FbxNode.Create(manager, name)
        skel = FbxSkeleton.Create(manager, name + "_skeleton")
        skel.SetSkeletonType(FbxSkeleton.eLimbNode)
        node.SetNodeAttribute(skel)
        joints.append(node)

    scene.GetRootNode().AddChild(character_node)
    character_node.AddChild(joints[ROOT])
    character_node.AddChild(mesh_node)

    for i in range(NUM_JOINTS):
        joints[HIERARCHY_PARENT[i]].AddChild(joints[i])

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


def create_skinned_mesh(sdk_manager, scene, mesh, local_positions, weights):
    """
    Build the skeleton, skin *mesh* to it and register the bind pose.

    Parameters
    ----------
    sdk_manager     : FbxManager instance.
    scene           : FbxScene instance.
    mesh            : FbxMesh to skin.
    local_positions : (24, 3) T-pose joint offsets (see smpl_math).
    weights         : (24, N_vertices) skin weights.

    Returns
    -------
    mesh_node : FbxNode that owns the skinned mesh.
    joints    : list of 25 FbxNode objects.
    """
    if weights.shape != (NUM_JOINTS, mesh.GetControlPointsCount()):
        raise ValueError(
            f"Skin weights have shape {weights.shape}, expected "
            f"({NUM_JOINTS}, {mesh.GetControlPointsCount()})"
        )

    skin = FbxSkin.Create(sdk_manager, "skin")
    mesh.AddDeformer(skin)

    joints, mesh_node = build_node_hierarchy(scene, sdk_manager)
    mesh_node.SetNodeAttribute(mesh)

    for j in range(NUM_JOINTS):
        joints[j].LclTranslation.Set(FbxDouble3(*map(float, local_positions[j])))
        joints[j].LclRotation.Set(FbxDouble3(0.0, 0.0, 0.0))

    mesh_matrix = mesh_node.EvaluateGlobalTransform()

    skin.AddCluster(_make_cluster(scene, "cluster_Root", joints[ROOT], mesh_matrix))
    for j in range(NUM_JOINTS):
        skin.AddCluster(_make_cluster(
            scene, "cluster_" + JOINT_NAMES[j], joints[j], mesh_matrix, weights[j]
        ))

    bind_pose = FbxPose.Create(sdk_manager, "bindPose")
    bind_pose.SetIsBindPose(True)
    for node in joints:
        bind_pose.Add(node, FbxMatrix(node.EvaluateGlobalTransform()))
    scene.AddPose(bind_pose)

    return mesh_node, joints
