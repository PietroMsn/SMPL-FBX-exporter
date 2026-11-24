# SMPL → FBX / glTF / USD Animation Pipeline

Convert [SURREAL](https://www.di.ens.fr/willow/research/surreal/) pose data into rigged, skinned and animated 3D files using the [SMPL](https://smpl.is.tue.mpg.de/) body model. Supported output formats: **FBX**, **glTF 2.0** and **OpenUSD**.

---

## Overview

The pipeline takes a SURREAL `.mat` file containing per-frame SMPL pose parameters, applies them to a 3D human mesh and exports a file with:

- a **24-joint skeleton** following the SMPL topology (plus a virtual `Root`)
- per-vertex **skin weights** bound to the skeleton
- **baked joint rotations** for every frame, timed at the source frame rate
- the T-pose as **bind pose**

| Format | Extensions | Needs | Good for |
|---|---|---|---|
| **FBX** | `.fbx` | Autodesk FBX Python SDK | Maya, 3ds Max, Unity, Unreal |
| **glTF 2.0** | `.glb`, `.gltf` (+ `.bin`) | nothing extra | Web viewers (three.js, Babylon.js), Blender, game engines |
| **OpenUSD** | `.usd`, `.usda`, `.usdc`, `.usdz` | `usd-core` | Omniverse, Houdini, Blender, Apple AR (`.usdz`) |

---

## Project Structure

```
.
├── main.py              # Command-line entry point
├── rig.py               # Format-independent skeleton + mesh + animation data
├── smpl_math.py         # Pure math: Rodrigues → Euler, joint positions
├── smpl_model.py        # Loads the SMPL joint regressor (no chumpy needed)
├── geometry.py          # Mesh loading from .mat files
├── exporters/
│   ├── fbx_export.py    # FBX writer (Autodesk FBX SDK)
│   ├── gltf_export.py   # glTF 2.0 writer (pure numpy)
│   ├── usd_export.py    # USD writer (UsdSkel)
│   └── skinning.py      # Helpers shared by glTF and USD
├── attach_anim.py       # Diagnostic: print the pose array of a .mat file
├── myWeights.npy        # Skin weights, shape (24, 6890)
├── meshes/              # Sample SMPL meshes (VERT / TRIV)
├── animations/          # Sample SURREAL pose sequences
└── tests/               # pytest suite
```

---

## Installation

### 1. Python and pip packages

Python **3**. If you need FBX, use the Python version your build of the FBX Python SDK supports (check the wheel name, e.g. `cp310` = Python 3.10).

```bash
pip install -r requirements.txt
```

This installs everything needed for glTF and USD.

### 2. Autodesk FBX Python SDK (FBX only)

Not available on PyPI. Download the **FBX Python SDK** for your OS from the [Autodesk FBX SDK page](https://aps.autodesk.com/developer/overview/autodesk-fbx-sdk) and install the wheel it ships with:

```bash
pip install fbx-<version>-cp3XX-none-<platform>.whl
```

Check it with `python -c "import fbx"`. Each exporter is loaded only when it is used, so glTF and USD export work without the FBX SDK.

### 3. SMPL model

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
| `-o`, `--output` | Output path. Its extension selects the format. Default: `resFbx/<pose file name>.<ext>` (the folder is created) |
| `-f`, `--format` | `fbx`, `gltf` or `usd`. Default: from the `--output` extension, otherwise `fbx` |
| `-s`, `--scale` | Scale factor applied to the mesh vertices. Default: `1` |
| `--fps` | Animation frame rate. Default: `30` (the SURREAL video frame rate) |
| `--start`, `--end` | Frame range to export (end exclusive). Default: all frames |
| `--model` | SMPL model or joint regressor. Default: `models/basicmodel_m_lbs_10_207_0_v1.0.0.pkl` |
| `--weights` | Skin weights `.npy`, shape (24, vertices). Default: `myWeights.npy` |

**Examples**, using the sample data in the repository:

```bash
# FBX
python main.py animations/104_03_c0003_info.mat meshes/MESH1_SMPL.mat -o resFbx/104_03.fbx

# glTF binary (single file)
python main.py animations/104_03_c0003_info.mat meshes/MESH1_SMPL.mat -o resFbx/104_03.glb

# USD: .usda = text, .usdc = binary, .usdz = packaged for AR
python main.py animations/104_03_c0003_info.mat meshes/MESH1_SMPL.mat -o resFbx/104_03.usdc

# Format only: default file name resFbx/104_03_c0003_info.glb
python main.py animations/104_03_c0003_info.mat meshes/MESH1_SMPL.mat -f gltf
```

### Diagnostic tool

Print the pose array stored in a `.mat` file:

```bash
python attach_anim.py animations/104_03_c0003_info.mat
```

---

## Pipeline Details

1. **`rig.py`** collects everything into one `Rig` object, used by all exporters:
   - mesh from **`geometry.py`**, scaled, with faces converted from 1-based to 0-based indices
   - joint regressor from **`smpl_model.py`**
   - rest-pose joint offsets from **`smpl_math.py`** (each joint relative to its parent)
   - per-frame local joint rotations (SMPL Rodrigues vectors)
2. The selected exporter writes the rig in its own format:
   - **FBX**: Euler XYZ rotation curves in degrees. The Pelvis uses linear interpolation and also gets translation keys. The other joints use cubic interpolation. One skin cluster per joint and an FBX bind pose.
   - **glTF**: one node per joint, a skin with inverse bind matrices, up to 4 influences per vertex in each `JOINTS_n`/`WEIGHTS_n` set, and quaternion rotation channels with `LINEAR` (spherical) interpolation. Vertex normals are included.
   - **USD**: a `SkelRoot` containing a `Skeleton` (bind and rest transforms), a `SkelAnimation` with per-frame quaternions, and a `Mesh` bound with `UsdSkel.BindingAPI`. The stage is Y-up, 1 unit = 1 m, and its time codes follow `--fps`.

Coordinates are written as they appear in the input (SMPL: Y-up). Blender and the other tools convert them on import.

### Known limitations

- The global translation of the body (`trans` in SURREAL files) is not exported. The Pelvis stays at its T-pose position.
- Joint positions come from the mesh passed on the command line. Body shape parameters (`shape`) are not applied.
- No materials or textures are exported.

---

## Tests

```bash
python -m pytest tests
```

The tests do not need the FBX SDK or the SMPL model:

- **FBX**: when `fbx` is not installed, a lightweight fake module stands in for it and the whole pipeline runs on the sample data.
- **glTF and USD**: the exported files are read back and the skinned mesh at several frames is compared with an independent linear blend skinning computation. USD skinning is computed by `UsdSkel` itself. The USD tests are skipped if `usd-core` is not installed.

---

## Acknowledgements

- **SMPL** body model, Max Planck Institute for Intelligent Systems.
  *Loper et al., SMPL: A Skinned Multi-Person Linear Model, SIGGRAPH Asia 2015*
- **SURREAL** dataset, INRIA / École Normale Supérieure.
  *Varol et al., Learning from Synthetic Humans, CVPR 2017*
- **Autodesk FBX SDK** for Python, **OpenUSD** (Pixar), **glTF** (Khronos Group)

---

## License

This project is released for research and educational purposes.
Please refer to the SMPL and SURREAL licenses for any restrictions on the underlying model and data.
