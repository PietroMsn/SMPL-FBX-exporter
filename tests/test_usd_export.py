"""USD export: let UsdSkel skin the mesh and compare with the reference LBS."""

import numpy as np
import pytest

pxr = pytest.importorskip("pxr", reason="usd-core is not installed")
from pxr import Usd, UsdGeom, UsdSkel  # noqa: E402

from exporters import usd_export  # noqa: E402
from reference import posed_vertices  # noqa: E402


def _skinned_points(stage, frame):
    cache = UsdSkel.Cache()
    cache.Populate(UsdSkel.Root(stage.GetPrimAtPath("/Character")), Usd.PrimDefaultPredicate)
    skel_query = cache.GetSkelQuery(UsdSkel.Skeleton(stage.GetPrimAtPath("/Character/Skeleton")))
    mesh = stage.GetPrimAtPath("/Character/Human")
    skin_query = cache.GetSkinningQuery(mesh)

    time = Usd.TimeCode(frame)
    points = mesh.GetAttribute("points").Get()
    assert skin_query.ComputeSkinnedPoints(
        skel_query.ComputeSkinningTransforms(time), points, time)
    return np.array(points)


@pytest.mark.parametrize("ext", ["usda", "usdc", "usdz"])
def test_usd_skinning(tmp_path, rig, ext):
    path = tmp_path / f"anim.{ext}"
    usd_export.export(rig, str(path))

    stage = Usd.Stage.Open(str(path))
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y
    assert stage.GetTimeCodesPerSecond() == 30
    assert (stage.GetStartTimeCode(), stage.GetEndTimeCode()) == (0, 19)

    for frame in (0, 7, 19):
        np.testing.assert_allclose(_skinned_points(stage, frame),
                                   posed_vertices(rig, frame), atol=1e-5)
