

# SMPL → FBX Animation Pipeline

Convert [SURREAL](https://www.di.ens.fr/willow/research/surreal/) pose data into fully rigged, skinned, and animated FBX files using the [SMPL](https://smpl.is.tue.mpg.de/) body model.

---

## Overview

This pipeline takes a SURREAL `.mat` file containing per-frame SMPL pose parameters, fits them onto a 3-D human mesh, and exports a production-ready `.fbx` file complete with:

- a **24-joint skeleton** following the SMPL topology
- per-vertex **skin weights** bound to the skeleton
- **baked animation curves** (rotation + root translation) for every frame
- a proper **bind pose** registered in the FBX scene

---

## Project Structure

```
.
├── smpl_math.py      # Pure math: Rodrigues → Euler, joint positions
├── geometry.py       # Mesh loading from .mat files
├── skeleton.py       # FBX node hierarchy, skinning, bind pose
├── animate.py        # FBX animation curve baking
├── main.py           # Entry point — orchestrates the full pipeline
├── attach_anim.py    # Diagnostic script to inspect pose .mat files
└── requirements.txt
```
## Requirements

### Python

Python **2.7** is recommended.

### pip packages

```bash
pip install -r requirements.txt
```

### Manual installations

Two dependencies are **not** available on PyPI and must be installed separately:

| Package | Instructions |
|---|---|
| **FBX Python SDK** | Download from [Autodesk Developer Network](https://www.autodesk.com/developer-network/platform-technologies/fbx-sdk-2020-2) and follow Autodesk's installation guide for your OS. |
| **chumpy** | Use the Python 3 community fork: `pip install git+https://github.com/mattloper/chumpy.git` |

### SMPL model files

1. Register and download the SMPL model from [https://smpl.is.tue.mpg.de](https://smpl.is.tue.mpg.de).
2. Place `basicmodel_m_lbs_10_207_0_v1.0.0.pkl` inside a `models/` folder at the project root.
3. Copy `serialization.py` (included in the SMPL download) to the project root.

### Skin weights

A precomputed `myWeights.npy` file of shape `(24, 6890)` must be present in the project root. Each row contains the per-vertex blend weights for one SMPL joint.

---

## Usage

```bash
python main.py <pose_mat> <output_name> <mesh_mat> <scale>
```

| Argument | Description |
|---|---|
| `pose_mat` | Path to the SURREAL `.mat` file containing the `pose` array |
| `output_name` | Base name for the output file (no `.fbx` extension) |
| `mesh_mat` | Path to the `.mat` file containing `VERT` and `TRIV` arrays |
| `scale` | Integer scale factor applied to vertex coordinates (e.g. `6`) |

**Example:**

```bash
python main.py data/03_01_c0001_info.mat my_animation data/mesh.mat 6
```

The output file will be written to `./resFbx/Buff/my_animation.fbx`.

> **Note:** Make sure the `./resFbx/Buff/` directory exists before running.

### Diagnostic tool

To quickly inspect the pose data in a `.mat` file:

```bash
python attach_anim.py
```

Edit the `MAT_FILE` constant at the top of the script to point to your file.

---

## Pipeline Details

### 1 · `smpl_math.py` — Pure math

- **`rodrigues_to_euler(v)`** — converts a Rodrigues rotation vector to ZYX Euler angles (degrees) using the closed-form Rodrigues formula.
- **`calc_local_position(model, vertices)`** — applies the SMPL joint regressor to mesh vertices to obtain world-space joint positions, then expresses each joint relative to its parent.
- **`pose_to_joint_rotations(model)`** — reshapes the flat 72-element SMPL pose vector into 24 per-joint Euler angle triplets.

### 2 · `geometry.py` — Mesh loading

Loads `VERT` (vertices) and `TRIV` (triangle faces) from a SURREAL `.mat` file, applies a uniform scale factor, and converts face indices from 1-based (MATLAB) to 0-based (Python).

### 3 · `skeleton.py` — FBX skeleton

Builds a 25-node FBX hierarchy (24 SMPL joints + 1 virtual Root), attaches one `FbxCluster` per joint with the corresponding skin weights, and registers the T-pose as the bind pose.

### 4 · `animate.py` — Animation baking

Iterates over every frame in the pose sequence and writes `LclRotation` (and root `LclTranslation`) keyframes onto the FBX animation layer. Supports both rotation-only and translation-only modes for non-root joints.

> **Known limitation:** the time step between keyframes is currently hardcoded (`0.05 s` per frame, `1.0 s` at boundaries). This should be derived from the source video FPS to keep the animation in sync.

---

## Output

The pipeline produces a single `.fbx` file containing:

- The skinned human mesh
- The full 24-joint skeleton with bind pose
- One animation take (`Take001`) on a single base layer
- Linear interpolation on the root joint, cubic on all others

The file can be imported directly into Blender, Maya, Unreal Engine, or Unity.

---

## Acknowledgements

- **SMPL** body model — Max Planck Institute for Intelligent Systems  
  *Loper et al., SMPL: A Skinned Multi-Person Linear Model, SIGGRAPH Asia 2015*
- **SURREAL** dataset — INRIA / École Normale Supérieure  
  *Varol et al., Learning from Synthetic Humans, CVPR 2017*
- **Autodesk FBX SDK** for Python

---

## License

This project is released for research and educational purposes.  
Please refer to the SMPL and SURREAL licenses for any restrictions on the underlying model and data.
