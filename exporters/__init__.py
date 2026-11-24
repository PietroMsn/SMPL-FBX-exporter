"""
Exporters: one module per file format, each with ``export(rig, output_path)``.

Modules are imported only when used, so e.g. glTF export works without the
FBX SDK or the USD library installed.
"""

import importlib
import os

# format name -> (module, default file extension, pip package hint)
FORMATS = {
    "fbx":  ("exporters.fbx_export",  ".fbx",  "the Autodesk FBX Python SDK (see README)"),
    "gltf": ("exporters.gltf_export", ".glb",  None),
    "usd":  ("exporters.usd_export",  ".usdc", "usd-core  (pip install usd-core)"),
}

# file extension -> format name
EXTENSIONS = {
    ".fbx": "fbx",
    ".glb": "gltf", ".gltf": "gltf",
    ".usd": "usd", ".usda": "usd", ".usdc": "usd", ".usdz": "usd",
}


def format_from_path(path):
    """Return the format matching the extension of *path*, or None."""
    return EXTENSIONS.get(os.path.splitext(path)[1].lower())


def export(rig, output_path, fmt):
    """Export *rig* to *output_path* using the exporter for *fmt*."""
    module_name, _, requirement = FORMATS[fmt]
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        hint = f" Install {requirement}." if requirement else ""
        raise SystemExit(f"Cannot export to {fmt.upper()}: {exc}.{hint}") from exc

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    module.export(rig, output_path)
