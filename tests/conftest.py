"""
Make the project importable and provide a minimal fake ``fbx`` module, so the
pipeline can be tested without the Autodesk FBX SDK installed.
"""

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Obj:
    """Generic FBX object that records what the exporter does to it."""

    def __init__(self, name=""):
        self.name = name
        self.children = []
        self.attribute = None
        self.props = {}

    @classmethod
    def Create(cls, _owner=None, name=""):
        return cls(name)

    def AddChild(self, child):
        self.children.append(child)

    def SetNodeAttribute(self, attr):
        self.attribute = attr

    def EvaluateGlobalTransform(self):
        return "matrix"

    @property
    def LclTranslation(self):
        return self.props.setdefault("T", _Prop())

    @property
    def LclRotation(self):
        return self.props.setdefault("R", _Prop())

    def __getattr__(self, name):
        # Any other SDK call is accepted and ignored.
        return lambda *a, **k: True


class _Prop:
    def __init__(self):
        self.value = None
        self.curves = {}

    def Set(self, value):
        self.value = value

    def GetCurve(self, _layer, channel, _create):
        return self.curves.setdefault(channel, _Curve())


class _Curve:
    def __init__(self):
        self.keys = []  # [seconds, value, interpolation]

    def KeyModifyBegin(self):
        pass

    def KeyModifyEnd(self):
        pass

    def KeyAdd(self, t):
        self.keys.append([t.seconds, None, None])
        return (len(self.keys) - 1, 0)

    def KeySetValue(self, i, v):
        self.keys[i][1] = v

    def KeySetInterpolation(self, i, interp):
        self.keys[i][2] = interp


class _Time:
    def __init__(self):
        self.seconds = 0.0

    def SetSecondDouble(self, s):
        self.seconds = s


class _Mesh(_Obj):
    def InitControlPoints(self, n):
        self.points = [None] * n
        self.polygons = []
        self.deformers = []

    def GetControlPointsCount(self):
        return len(self.points)

    def SetControlPointAt(self, v, i):
        self.points[i] = v

    def BeginPolygon(self):
        self.polygons.append([])

    def AddPolygon(self, i):
        self.polygons[-1].append(i)

    def AddDeformer(self, d):
        self.deformers.append(d)


class _Cluster(_Obj):
    eNormalize = 0

    def __init__(self, name=""):
        super().__init__(name)
        self.weights = {}
        self.link = None

    def AddControlPointIndex(self, i, w):
        self.weights[i] = w

    def SetLink(self, node):
        self.link = node


class _Skin(_Obj):
    def __init__(self, name=""):
        super().__init__(name)
        self.clusters = []

    def AddCluster(self, c):
        self.clusters.append(c)


class _Scene(_Obj):
    def GetRootNode(self):
        if "root" not in self.__dict__:
            self.__dict__["root"] = _Obj("RootNode")
        return self.__dict__["root"]


class _Exporter(_Obj):
    last = None

    def Initialize(self, path, *_):
        self.path = path
        return True

    def Export(self, scene):
        _Exporter.last = (self.path, scene)
        with open(self.path, "w") as f:
            f.write("fake fbx")
        return True


class _Manager(_Obj):
    def GetIOPluginRegistry(self):
        return types.SimpleNamespace(GetNativeWriterFormat=lambda: 0)


class _Skeleton(_Obj):
    eLimbNode = 1


try:
    import fbx  # noqa: F401
except ImportError:
    fake = types.ModuleType("fbx")
    fake.FbxNode = _Obj
    fake.FbxSkeleton = _Skeleton
    fake.FbxSkin = _Skin
    fake.FbxCluster = _Cluster
    fake.FbxPose = _Obj
    fake.FbxMatrix = lambda m: m
    fake.FbxDouble3 = lambda *v: tuple(v)
    fake.FbxVector4 = lambda *v: tuple(v)
    fake.FbxMesh = _Mesh
    fake.FbxManager = _Manager
    fake.FbxIOSettings = _Obj
    fake.FbxScene = _Scene
    fake.FbxAnimStack = _Obj
    fake.FbxAnimLayer = _Obj
    fake.FbxExporter = _Exporter
    fake.FbxTime = _Time
    fake.FbxAnimCurveDef = types.SimpleNamespace(
        eInterpolationLinear="linear", eInterpolationCubic="cubic")
    fake.IOSROOT = "IOSROOT"
    fake.EXP_FBX_EMBEDDED = "EMBEDDED"
    fake.IS_FAKE = True
    sys.modules["fbx"] = fake
