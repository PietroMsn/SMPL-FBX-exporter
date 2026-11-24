# SMPL → FBX Animation Pipeline

Convert [SURREAL](https://www.di.ens.fr/willow/research/surreal/) pose data into rigged, skinned and animated FBX files using the [SMPL](https://smpl.is.tue.mpg.de/) body model.

---

## Overview

The pipeline takes a SURREAL `.mat` file containing per-frame SMPL pose parameters, applies them to a 3D human mesh and exports an `.fbx` file with:

- a **24-joint skeleton** following the SMPL topology (plus a virtual `Root`)
- per-vertex **skin weights** bound to the skeleton
- **baked rotation curves** for every joint and frame, timed at the source frame rate
- a **bind pose** registered in the FBX scene

The result can be imported into Blender, Maya, Unreal Engine or Unity.

---

## Project Structure

```
.
├── main.py           # Command-line entry point: builds and exports the scene
├── smpl_math.py      # Pure math: Rodrigues → Euler, joint positions
├── smpl_model.py     # Loads the SMPL joint regressor (no chumpy needed)
├── geometry.py       # Mesh loading from .mat files
├── skeleton.py       # FBX joint hierarchy, skinning, bind pose
├── animate.py        # FBX animation curve baking
├── attach_anim.py    # Diagnostic: print the pose array of a .mat file
├── myWeights.npy     # Skin weights, shape (24, 6890)
├── meshes/           # Sample SMPL meshes (VERT / TRIV)
├── animations/       # Sample SURREAL pose sequences
└── tests/            # pytest suite (runs without the FBX SDK)
```

---

## Installation

### 1. Python

Python **3**. Use the Python version your build of the FBX Python SDK supports (check the wheel name, e.g. `cp310` = Python 3.10).

### 2. pip packages

```bash
pip install -r requirements.txt
```

### 3. Autodesk FBX Python SDK

Not available on PyPI. Download the **FBX Python SDK** for your OS from the [Autodesk FBX SDK page](https://aps.autodesk.com/developer/overview/autodesk-fbx-sdk) and install the wheel it ships with:

```bash
pip install fbx-<version>-cp3XX-none-<platform>.whl
```

Check it with `python -c "import fbx"`.

### 4. SMPL model

1. Register and download SMPL from [smpl.is.tue.mpg.de](https://smpl.is.tue.mpg.de).
2. Put `basicmodel_m_lbs_10_207_0_v1.0.0.pkl` in a `models/` folder at the project root, or pass another file with `--model`.

Only the joint regressor is read from the model. The original Python 2 `.pkl` is loaded directly, without chumpy. A `.npy` file, or a `.npz` with a `J_regressor` key, also works.

---

## Usage

```bash
python main.py <pose_mat> <mesh_mat> [options]
```

| Argument | Description |
|---|---|
| `pose_mat` | SURREAL `*_info.mat` file containing the `pose` array (72 × frames) |
| `mesh_mat` | `.mat` file with the mesh: `VERT` (6890 × 3) and `TRIV` (triangles, 1-based) |
| `-o`, `--output` | Output `.fbx` path. Default: `resFbx/<pose file name>.fbx` (the folder is created) |
| `-s`, `--scale` | Scale factor applied to the mesh vertices. Default: `1` |
| `--fps` | Animation frame rate. Default: `30` (the SURREAL video frame rate) |
| `--start`, `--end` | Frame range to export (end exclusive). Default: all frames |
| `--model` | SMPL model or joint regressor. Default: `models/basicmodel_m_lbs_10_207_0_v1.0.0.pkl` |
| `--weights` | Skin weights `.npy`, shape (24, vertices). Default: `myWeights.npy` |

**Example**, using the sample data in the repository:

```bash
python main.py animations/104_03_c0003_info.mat meshes/MESH1_SMPL.mat --scale 6 -o resFbx/104_03.fbx
```

### Diagnostic tool

Print the pose array stored in a `.mat` file:

```bash
python attach_anim.py animations/104_03_c0003_info.mat
```

---

## Pipeline Details

1. **`smpl_model.py`** reads the SMPL joint regressor (24 × 6890).
2. **`geometry.py`** loads `VERT` and `TRIV`, applies the scale factor and converts the face indices from MATLAB 1-based to 0-based.
3. **`smpl_math.py`** regresses the joint positions from the mesh and expresses each one relative to its parent. It also converts every 72-value SMPL pose into 24 Euler rotations (XYZ order, degrees), matching the FBX default rotation order.
4. **`skeleton.py`** builds a 25-node hierarchy (24 SMPL joints + `Root`), creates one skin cluster per joint from `myWeights.npy` and stores the T-pose as the bind pose.
5. **`animate.py`** writes one rotation key per joint and frame at time `frame / fps`. The Pelvis uses linear interpolation and also gets translation keys. The other joints use cubic interpolation.

### Output

- skinned mesh and 24-joint skeleton with bind pose
- one animation take (`Take001`) on a single base layer

### Known limitations

- The global translation of the body (`trans` in SURREAL files) is not exported. The Pelvis stays at its T-pose position.
- Joint positions come from the mesh passed on the command line. Body shape parameters (`shape`) are not applied.

---

## Tests

```bash
python -m pytest tests
```

The tests do not need the FBX SDK or the SMPL model. When `fbx` is not installed, they replace it with a lightweight fake module and run the whole pipeline on the sample data.

---

## Acknowledgements

- **SMPL** body model, Max Planck Institute for Intelligent Systems.
  *Loper et al., SMPL: A Skinned Multi-Person Linear Model, SIGGRAPH Asia 2015*
- **SURREAL** dataset, INRIA / École Normale Supérieure.
  *Varol et al., Learning from Synthetic Humans, CVPR 2017*
- **Autodesk FBX SDK** for Python

---

## License

This project is released for research and educational purposes.
Please refer to the SMPL and SURREAL licenses for any restrictions on the underlying model and data.
