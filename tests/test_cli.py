import os

import pytest

import main


@pytest.mark.parametrize("output, fmt", [
    ("a.fbx", "fbx"), ("a.glb", "gltf"), ("a.GLTF", "gltf"),
    ("a.usd", "usd"), ("a.usda", "usd"), ("a.usdc", "usd"), ("a.usdz", "usd"),
])
def test_format_from_extension(output, fmt):
    assert main.parse_args(["p.mat", "m.mat", "-o", output]).format == fmt


@pytest.mark.parametrize("fmt, ext", [("fbx", ".fbx"), ("gltf", ".glb"), ("usd", ".usdc")])
def test_default_output_name(fmt, ext):
    args = main.parse_args(["dir/run_info.mat", "m.mat", "-f", fmt])
    assert args.output == os.path.join("resFbx", "run_info" + ext)


def test_default_format_is_fbx():
    assert main.parse_args(["p.mat", "m.mat"]).format == "fbx"


@pytest.mark.parametrize("argv", [
    ["p.mat", "m.mat", "-o", "a.obj"],
    ["p.mat", "m.mat", "-o", "a.glb", "-f", "usd"],
])
def test_invalid_combinations(argv):
    with pytest.raises(SystemExit):
        main.parse_args(argv)
