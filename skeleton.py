"""
skeleton.py
FBX skeleton hierarchy, skin deformer, and bind-pose construction.

Dependency chain:  smpl_math  <->  geometry  <-  skeleton

This module knows about FBX and SMPL joint structure, but nothing about
animation curves or the top-level scene orchestration.

Functions / classes
-------------------
build_node_hierarchy    Create and wire the 25 FbxNode objects.
create_skinned_mesh     Attach skin clusters and bind pose to an FbxMesh.
"""

import numpy as np
import fbx
from fbx import (
    FbxNode, FbxSkeleton, FbxSkin, FbxCluster,
    FbxPose, FbxMatrix, FbxDouble3,
)

from smpl_math import NUM_JOINTS, calc_local_position
from geometry import load_geometry_from_args


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEIGHTS_FILE = "myWeights.npy"

JOINT_NAMES = [
    "Pelvis",    "L_Hip",     "R_Hip",      "Spine1",
    "L_Knee",    "R_Knee",    "Spine2",     "L_Ankle",
    "R_Ankle",   "Spine3",    "L_Foot",     "R_Foot",
    "Neck",      "L_Collar",  "R_Collar",   "Head",
    "L_Shoulder","R_Shoulder","L_Elbow",    "R_Elbow",
    "L_Wrist",   "R_Wrist",   "L_Hand",     "R_Hand",
    "Root",      # index 24 - virtual root above the pelvis
]

# Parent index for each joint when building the FBX child chain
# (matches SMPL topology; index 24 = Root is parent of Pelvis)
HIERARCHY_PARENT = [
    24, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8,
     9, 9, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21,
]


# ---------------------------------------------------------------------------
# Node hierarchy
# ---------------------------------------------------------------------------

def build_node_hierarchy(scene, manager):
    """
    Create 25 FbxNode skeleton nodes and wire them into the scene.

    The virtual *Root* node (index 24) sits above the SMPL Pelvis (index 0)
    and is a child of the top-level *character* grouping node.

    Parameters
    ----------
    scene   : FbxScene instance.
    manager : FbxManager instance.

    Returns
    -------
    joints    : list of 25 FbxNode objects (indices 0-23 = SMPL, 24 = Root).
    mesh_node : Placeholder FbxNode for the mesh attachment point.
    """
    root_node      = scene.GetRootNode()
    character_node = FbxNode.Create(manager, "character")
    mesh_node      = FbxNode.Create(manager, "myMesh")

    # Create one node per joint
    joints = []
    for i, name in enumerate(JOINT_NAMES):
        node = FbxNode.Create(manager, name)
        skel = FbxSkeleton.Create(manager, "mySkeleton{i}")
        skel.SetSkeletonType(FbxSkeleton.eLimbNode)
        node.SetNodeAttribute(skel)
        joints.append(node)

    # Wire hierarchy
    root_node.AddChild(character_node)
    character_node.AddChild(joints[24])   # character -> Root
    character_node.AddChild(mesh_node)
    joints[24].AddChild(joints[0])        # Root -> Pelvis

    for i in range(NUM_JOINTS):
        joints[HIERARCHY_PARENT[i]].AddChild(joints[i])

    return joints, mesh_node


# ---------------------------------------------------------------------------
# Skinning
# ---------------------------------------------------------------------------

def create_skinned_mesh(sdk_manager, scene, smpl_model, mesh):
    """
    Attach a skin deformer to *mesh*, position joints, and register bind-pose.

    Parameters
    ----------
    sdk_manager : FbxManager instance.
    scene       : FbxScene instance.
    smpl_model  : SMPL model object (used to compute T-pose joint positions).
    mesh        : FbxMesh to skin.

    Returns
    -------
    mesh_node : FbxNode that owns the skinned mesh.
    joints    : list of 25 FbxNode objects.
    mesh      : The same FbxMesh with the skin deformer attached.
    """
    skin_deformer = FbxSkin.Create(sdk_manager, "skin")
    mesh.AddDeformer(skin_deformer)

    joints, mesh_node = build_node_hierarchy(scene, sdk_manager)

    # T-pose joint positions
    vertices, _ = load_geometry_from_args()
    local_positions = calc_local_position(smpl_model, vertices)
    joint_rotation  = np.zeros((NUM_JOINTS, 3))

    # Apply T-pose transforms to nodes
    for j in range(NUM_JOINTS):
        joints[j].LclTranslation.Set(FbxDouble3(*local_positions[j]))
        joints[j].LclRotation.Set(FbxDouble3(*joint_rotation[j]))

    # Load precomputed per-vertex weights
    my_weights  = np.load(WEIGHTS_FILE)
    mesh_matrix = mesh_node.EvaluateGlobalTransform()

    # Root cluster (virtual Root node, index 24)
    root_cluster = FbxCluster.Create(scene, "cluster_root")
    root_cluster.SetLink(joints[24])
    root_cluster.SetLinkMode(0)
    root_cluster.SetTransformMatrix(mesh_matrix)
    root_cluster.SetTransformLinkMatrix(joints[24].EvaluateGlobalTransform())
    skin_deformer.AddCluster(root_cluster)

    # One cluster per SMPL joint
    for j in range(NUM_JOINTS):
        cluster = FbxCluster.Create(scene, "cluster_{j}")

        for vert_idx in range(6890):
            weight = float(my_weights[j][vert_idx])
            if weight != 0.0:
                cluster.AddControlPointIndex(vert_idx, weight)

        cluster.SetLink(joints[j])
        cluster.SetLinkMode(0)
        cluster.SetTransformMatrix(mesh_matrix)
        cluster.SetTransformLinkMatrix(joints[j].EvaluateGlobalTransform())
        skin_deformer.AddCluster(cluster)

    # Bind pose
    bind_pose = FbxPose.Create(sdk_manager, "bindPose")
    bind_pose.SetIsBindPose(True)
    bind_pose.Add(joints[24], FbxMatrix(joints[24].EvaluateGlobalTransform()))
    for i in range(NUM_JOINTS):
        bind_pose.Add(joints[i], FbxMatrix(joints[i].EvaluateGlobalTransform()))
    scene.AddPose(bind_pose)

    return mesh_node, joints, mesh
