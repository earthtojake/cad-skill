from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from array import array
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepGProp import BRepGProp
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.STEPControl import STEPControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.Quantity import Quantity_ColorRGBA
from OCP.TDF import TDF_ChildIterator, TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_REVERSED,
    TopAbs_SHELL,
    TopAbs_SOLID,
    TopAbs_VERTEX,
)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import (
    XCAFDoc_ColorCurv,
    XCAFDoc_ColorGen,
    XCAFDoc_ColorSurf,
    XCAFDoc_ColorTool,
    XCAFDoc_DocumentTool,
    XCAFDoc_ShapeTool,
)


REPO_ROOT = Path.cwd().resolve()
ColorRGBA = tuple[float, float, float, float]


class SelectorProfile(str, Enum):
    SUMMARY = "summary"
    REFS = "refs"
    ARTIFACT = "artifact"


@dataclass(frozen=True)
class SelectorOptions:
    linear_deflection: float = 0.006
    angular_deflection: float = 0.6
    relative: bool = True
    edge_deflection: float | None = None
    edge_deflection_ratio: float = 0.00075
    max_edge_points: int = 96
    digits: int | None = 6


@dataclass
class SelectorBundle:
    manifest: dict[str, Any]
    buffers: dict[str, array] = field(default_factory=dict)


@dataclass
class LoadedStepScene:
    step_path: Path
    roots: list["OccurrenceNode"]
    prototype_shapes: dict[int, Any]
    prototype_names: dict[int, str | None] = field(default_factory=dict)
    prototype_colors: dict[int, ColorRGBA] = field(default_factory=dict)
    prototype_face_colors: dict[int, dict[int, ColorRGBA]] = field(default_factory=dict)
    load_elapsed: float = 0.0
    step_hash: str | None = None
    mesh_signature: tuple[float, float, bool] | None = None
    export_shape: Any | None = None


@dataclass
class OccurrenceNode:
    path: tuple[int, ...]
    name: str | None
    source_name: str | None
    transform: tuple[float, ...]
    prototype_key: int | None
    local_transform: tuple[float, ...] = field(default_factory=lambda: _identity_transform_matrix())
    color: ColorRGBA | None = None
    location: object | None = None
    children: list["OccurrenceNode"] = field(default_factory=list)
    row_index: int = -1


def _enum_name(value: Any, prefix: str) -> str:
    name = str(value).split(".")[-1]
    if name.startswith(prefix):
        return name[len(prefix) :].lower()
    return name.lower()


def _round_value(value: float, digits: int | None) -> float:
    if digits is None:
        return float(value)
    return round(float(value), digits)


def _round_point(point: list[float] | tuple[float, float, float], digits: int | None) -> list[float]:
    return [_round_value(point[0], digits), _round_value(point[1], digits), _round_value(point[2], digits)]


def _round_transform(matrix: tuple[float, ...], digits: int | None) -> list[float]:
    return [_round_value(value, digits) for value in matrix]


def _normalize(vector: tuple[float, float, float] | list[float]) -> list[float] | None:
    x, y, z = vector
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-12:
        return None
    return [x / length, y / length, z / length]


def _cross(a: list[float], b: list[float], c: list[float]) -> tuple[float, float, float]:
    abx = b[0] - a[0]
    aby = b[1] - a[1]
    abz = b[2] - a[2]
    acx = c[0] - a[0]
    acy = c[1] - a[1]
    acz = c[2] - a[2]
    return (
        aby * acz - abz * acy,
        abz * acx - abx * acz,
        abx * acy - aby * acx,
    )


def _distance(a: list[float], b: list[float]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _bbox_from_points(points: list[list[float]]) -> dict[str, Any]:
    if not points:
        zero = [0.0, 0.0, 0.0]
        return {"min": zero[:], "max": zero[:], "center": zero[:], "size": zero[:], "diag": 0.0}
    min_x = max_x = points[0][0]
    min_y = max_y = points[0][1]
    min_z = max_z = points[0][2]
    for x, y, z in points[1:]:
        if x < min_x:
            min_x = x
        if x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
        if z < min_z:
            min_z = z
        if z > max_z:
            max_z = z
    size = [max_x - min_x, max_y - min_y, max_z - min_z]
    center = [min_x + size[0] * 0.5, min_y + size[1] * 0.5, min_z + size[2] * 0.5]
    return {
        "min": [min_x, min_y, min_z],
        "max": [max_x, max_y, max_z],
        "center": center,
        "size": size,
        "diag": math.sqrt(size[0] * size[0] + size[1] * size[1] + size[2] * size[2]),
    }


def _merge_bbox(boxes: list[dict[str, Any]]) -> dict[str, Any]:
    points: list[list[float]] = []
    for box in boxes:
        points.append(list(box["min"]))
        points.append(list(box["max"]))
    return _bbox_from_points(points)


def _compact_bbox(box: dict[str, Any], digits: int | None) -> dict[str, Any]:
    return {
        "min": _round_point(box["min"], digits),
        "max": _round_point(box["max"], digits),
    }


def _bbox_from_shape(shape: Any) -> dict[str, Any]:
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    if box.IsVoid():
        return _bbox_from_points([])
    min_x, min_y, min_z, max_x, max_y, max_z = box.Get()
    return _bbox_from_points(
        [
            [min_x, min_y, min_z],
            [max_x, max_y, max_z],
        ]
    )


def _transform_point_from_occ(point: Any, location: TopLoc_Location) -> list[float]:
    transformed = point.Transformed(location.Transformation())
    return [transformed.X(), transformed.Y(), transformed.Z()]


def _point_from_occ(point: Any) -> list[float]:
    return [point.X(), point.Y(), point.Z()]


def _apply_transform_point(transform: tuple[float, ...], point: list[float]) -> list[float]:
    x, y, z = point
    return [
        (transform[0] * x) + (transform[1] * y) + (transform[2] * z) + transform[3],
        (transform[4] * x) + (transform[5] * y) + (transform[6] * z) + transform[7],
        (transform[8] * x) + (transform[9] * y) + (transform[10] * z) + transform[11],
    ]


def _apply_transform_vector(transform: tuple[float, ...], vector: list[float]) -> list[float] | None:
    x, y, z = vector
    return _normalize(
        (
            (transform[0] * x) + (transform[1] * y) + (transform[2] * z),
            (transform[4] * x) + (transform[5] * y) + (transform[6] * z),
            (transform[8] * x) + (transform[9] * y) + (transform[10] * z),
        )
    )


def _transform_bbox(box: dict[str, Any], transform: tuple[float, ...]) -> dict[str, Any]:
    min_x, min_y, min_z = box["min"]
    max_x, max_y, max_z = box["max"]
    corners = [
        [min_x, min_y, min_z],
        [min_x, min_y, max_z],
        [min_x, max_y, min_z],
        [min_x, max_y, max_z],
        [max_x, min_y, min_z],
        [max_x, min_y, max_z],
        [max_x, max_y, min_z],
        [max_x, max_y, max_z],
    ]
    return _bbox_from_points([_apply_transform_point(transform, corner) for corner in corners])


def _transform_param_dict(params: dict[str, Any], transform: tuple[float, ...], digits: int | None) -> dict[str, Any]:
    point_keys = {"origin", "center", "location"}
    vector_keys = {"axis", "direction", "normal"}
    transformed: dict[str, Any] = {}
    for key, value in params.items():
        if key in point_keys and isinstance(value, list) and len(value) == 3:
            transformed[key] = _round_point(_apply_transform_point(transform, value), digits)
        elif key in vector_keys and isinstance(value, list) and len(value) == 3:
            vector = _apply_transform_vector(transform, value)
            transformed[key] = _round_point(vector or value, digits)
        else:
            transformed[key] = value
    return transformed


def _dedupe_consecutive(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if not points:
        return points
    deduped = [points[0]]
    for point in points[1:]:
        if _distance(deduped[-1], point) > tolerance:
            deduped.append(point)
    return deduped


def _decimate_polyline(points: list[list[float]], max_points: int) -> list[list[float]]:
    if max_points <= 1 or len(points) <= max_points:
        return points
    stride = (len(points) - 1) / float(max_points - 1)
    result = []
    last_index = -1
    for i in range(max_points):
        index = int(round(i * stride))
        if index >= len(points):
            index = len(points) - 1
        if index != last_index:
            result.append(points[index])
            last_index = index
    if result[-1] != points[-1]:
        result[-1] = points[-1]
    return result


def _polyline_length(points: list[list[float]], closed: bool) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for left, right in zip(points, points[1:]):
        total += _distance(left, right)
    if closed and _distance(points[0], points[-1]) > 1e-9:
        total += _distance(points[-1], points[0])
    return total


def _polyline_center(points: list[list[float]]) -> list[float]:
    if not points:
        return [0.0, 0.0, 0.0]
    total = [0.0, 0.0, 0.0]
    for point in points:
        total[0] += point[0]
        total[1] += point[1]
        total[2] += point[2]
    inv = 1.0 / len(points)
    return [total[0] * inv, total[1] * inv, total[2] * inv]


def _curve_params(adaptor: BRepAdaptor_Curve, digits: int | None) -> dict[str, Any]:
    curve_type = _enum_name(adaptor.GetType(), "GeomAbs_")
    params: dict[str, Any] = {}
    if curve_type == "line":
        line = adaptor.Line()
        params["origin"] = _round_point(_point_from_occ(line.Location()), digits)
        params["direction"] = _round_point(_point_from_occ(line.Direction()), digits)
    elif curve_type == "circle":
        circle = adaptor.Circle()
        params["center"] = _round_point(_point_from_occ(circle.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(circle.Axis().Direction()), digits)
        params["radius"] = _round_value(circle.Radius(), digits)
    elif curve_type == "ellipse":
        ellipse = adaptor.Ellipse()
        params["center"] = _round_point(_point_from_occ(ellipse.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(ellipse.Axis().Direction()), digits)
        params["majorRadius"] = _round_value(ellipse.MajorRadius(), digits)
        params["minorRadius"] = _round_value(ellipse.MinorRadius(), digits)
    elif curve_type == "hyperbola":
        hyperbola = adaptor.Hyperbola()
        params["center"] = _round_point(_point_from_occ(hyperbola.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(hyperbola.Axis().Direction()), digits)
        params["majorRadius"] = _round_value(hyperbola.MajorRadius(), digits)
        params["minorRadius"] = _round_value(hyperbola.MinorRadius(), digits)
    elif curve_type == "parabola":
        parabola = adaptor.Parabola()
        params["center"] = _round_point(_point_from_occ(parabola.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(parabola.Axis().Direction()), digits)
        params["focal"] = _round_value(parabola.Focal(), digits)
    elif curve_type in {"beziercurve", "bsplinecurve"}:
        params["degree"] = int(adaptor.Degree())
        params["periodic"] = bool(adaptor.IsPeriodic())
        params["rational"] = bool(adaptor.IsRational())
    return params


def _surface_params(adaptor: BRepAdaptor_Surface, digits: int | None) -> dict[str, Any]:
    surface_type = _enum_name(adaptor.GetType(), "GeomAbs_")
    params: dict[str, Any] = {}
    if surface_type == "plane":
        plane = adaptor.Plane()
        params["origin"] = _round_point(_point_from_occ(plane.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(plane.Axis().Direction()), digits)
    elif surface_type == "cylinder":
        cylinder = adaptor.Cylinder()
        params["origin"] = _round_point(_point_from_occ(cylinder.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(cylinder.Axis().Direction()), digits)
        params["radius"] = _round_value(cylinder.Radius(), digits)
    elif surface_type == "cone":
        cone = adaptor.Cone()
        params["origin"] = _round_point(_point_from_occ(cone.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(cone.Axis().Direction()), digits)
        params["semiAngleRad"] = _round_value(cone.SemiAngle(), digits)
    elif surface_type == "sphere":
        sphere = adaptor.Sphere()
        params["center"] = _round_point(_point_from_occ(sphere.Location()), digits)
        params["radius"] = _round_value(sphere.Radius(), digits)
    elif surface_type == "torus":
        torus = adaptor.Torus()
        params["center"] = _round_point(_point_from_occ(torus.Location()), digits)
        params["axis"] = _round_point(_point_from_occ(torus.Axis().Direction()), digits)
        params["majorRadius"] = _round_value(torus.MajorRadius(), digits)
        params["minorRadius"] = _round_value(torus.MinorRadius(), digits)
    elif surface_type in {"beziersurface", "bsplinesurface"}:
        params["uClosed"] = bool(adaptor.IsUPeriodic())
        params["vClosed"] = bool(adaptor.IsVPeriodic())
    return params


def _extract_face_geometry(face: Any) -> dict[str, Any]:
    location = TopLoc_Location()
    triangulation = BRep_Tool.Triangulation_s(face, location)
    if triangulation is None:
        return {
            "nodes": [],
            "triangles": [],
            "triangleCount": 0,
            "area": 0.0,
            "center": [0.0, 0.0, 0.0],
            "normal": None,
            "bbox": _bbox_from_points([]),
            "triangulation": None,
            "location": location,
        }

    nodes = [_transform_point_from_occ(triangulation.Node(index), location) for index in range(1, triangulation.NbNodes() + 1)]
    triangles: list[tuple[int, int, int]] = []
    area_sum = 0.0
    centroid_sum = [0.0, 0.0, 0.0]
    normal_sum = [0.0, 0.0, 0.0]

    for index in range(1, triangulation.NbTriangles() + 1):
        node_a, node_b, node_c = triangulation.Triangle(index).Get()
        point_a = nodes[node_a - 1]
        point_b = nodes[node_b - 1]
        point_c = nodes[node_c - 1]
        normal_x, normal_y, normal_z = _cross(point_a, point_b, point_c)
        twice_area = math.sqrt((normal_x * normal_x) + (normal_y * normal_y) + (normal_z * normal_z))
        if twice_area <= 1e-12:
            continue
        area = twice_area * 0.5
        centroid_sum[0] += (point_a[0] + point_b[0] + point_c[0]) * area / 3.0
        centroid_sum[1] += (point_a[1] + point_b[1] + point_c[1]) * area / 3.0
        centroid_sum[2] += (point_a[2] + point_b[2] + point_c[2]) * area / 3.0
        normal_sum[0] += normal_x
        normal_sum[1] += normal_y
        normal_sum[2] += normal_z
        area_sum += area
        triangles.append((node_a - 1, node_b - 1, node_c - 1))

    if not nodes:
        center = [0.0, 0.0, 0.0]
    elif area_sum > 1e-12:
        center = [
            centroid_sum[0] / area_sum,
            centroid_sum[1] / area_sum,
            centroid_sum[2] / area_sum,
        ]
    else:
        center = _bbox_from_points(nodes)["center"]

    normal = _normalize((normal_sum[0], normal_sum[1], normal_sum[2]))
    if normal and face.Orientation() == TopAbs_REVERSED:
        normal = [-normal[0], -normal[1], -normal[2]]

    return {
        "nodes": nodes,
        "triangles": triangles,
        "triangleCount": len(triangles),
        "area": area_sum,
        "center": center,
        "normal": normal,
        "bbox": _bbox_from_points(nodes),
        "triangulation": triangulation,
        "location": location,
    }


def _extract_edge_points_from_face_mesh(edge: Any, face_mesh: dict[str, Any], max_points: int) -> list[list[float]]:
    triangulation = face_mesh["triangulation"]
    if triangulation is None:
        return []
    polygon = BRep_Tool.PolygonOnTriangulation_s(edge, triangulation, face_mesh["location"])
    if polygon is None:
        return []
    points = [face_mesh["nodes"][polygon.Node(index) - 1] for index in range(1, polygon.NbNodes() + 1)]
    points = _dedupe_consecutive(points, 1e-9)
    if points and max_points > 1:
        points = _decimate_polyline(points, max_points)
    return points


def _extract_edge_points_from_curve(edge: Any, deflection: float, max_points: int) -> list[list[float]]:
    adaptor = BRepAdaptor_Curve(edge)
    curve_type = _enum_name(adaptor.GetType(), "GeomAbs_")
    if curve_type == "line":
        points = [
            _point_from_occ(adaptor.Value(adaptor.FirstParameter())),
            _point_from_occ(adaptor.Value(adaptor.LastParameter())),
        ]
        return _dedupe_consecutive(points, max(deflection * 0.25, 1e-9))

    points: list[list[float]] = []
    try:
        sampler = GCPnts_QuasiUniformDeflection(
            adaptor,
            deflection,
            adaptor.FirstParameter(),
            adaptor.LastParameter(),
        )
        if sampler.IsDone():
            points = [_point_from_occ(sampler.Value(index)) for index in range(1, sampler.NbPoints() + 1)]
    except Exception:
        points = []

    if not points:
        vertex_points = []
        explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
        while explorer.More():
            vertex = TopoDS.Vertex_s(explorer.Current())
            vertex_points.append(_point_from_occ(BRep_Tool.Pnt_s(vertex)))
            explorer.Next()
        points = vertex_points

    points = _dedupe_consecutive(points, max(deflection * 0.25, 1e-9))
    if points and max_points > 1:
        points = _decimate_polyline(points, max_points)
    return points


def _face_flags(face_data: dict[str, Any]) -> int:
    return 1 if not face_data.get("referenceable", True) else 0


def _edge_flags(edge_data: dict[str, Any]) -> int:
    flags = 0
    if edge_data.get("closed", False):
        flags |= 1
    if edge_data.get("degenerated", False):
        flags |= 2
    if edge_data.get("seam", False):
        flags |= 4
    if not edge_data.get("referenceable", True):
        flags |= 8
    return flags


def _vertex_flags(vertex_data: dict[str, Any]) -> int:
    return 1 if not vertex_data.get("referenceable", True) else 0


def _shape_hash(shape: Any) -> int:
    return hash(shape)


def _shape_location(topods_shape: object) -> object | None:
    location = getattr(topods_shape, "Location", None)
    if not callable(location):
        return None
    try:
        return location()
    except Exception:
        return None


def _compose_locations(parent_location: object | None, child_location: object | None) -> object | None:
    if parent_location is None:
        return child_location
    if child_location is None:
        return parent_location
    try:
        return parent_location.Multiplied(child_location)
    except Exception:
        return child_location


def _located_shape(topods_shape: object, location: object | None) -> object:
    if location is None:
        return topods_shape
    located = getattr(topods_shape, "Located", None)
    if not callable(located):
        return topods_shape
    try:
        return located(location)
    except Exception:
        return topods_shape


def _identity_transform_matrix() -> tuple[float, ...]:
    return (
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    )


def _location_transform_matrix(location: object | None) -> tuple[float, ...]:
    if location is None:
        return _identity_transform_matrix()
    transformation = getattr(location, "Transformation", None)
    if not callable(transformation):
        return _identity_transform_matrix()
    try:
        trsf = transformation()
    except Exception:
        return _identity_transform_matrix()
    rows: list[float] = []
    try:
        for row in range(1, 4):
            rows.extend(float(trsf.Value(row, column)) for column in range(1, 5))
    except Exception:
        return _identity_transform_matrix()
    rows.extend((0.0, 0.0, 0.0, 1.0))
    return tuple(rows)


def _normalize_label_name(raw_name: object) -> str | None:
    if raw_name is None:
        return None
    text = " ".join(str(raw_name).split())
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith("open cascade step translator"):
        return None
    if lowered in {"assembly", "solid", "compound", "compsolid", "shell", "face", "wire", "edge", "vertex"}:
        return None
    if text.isdigit():
        return None
    return text


def _label_name(label: object) -> str | None:
    name = TDataStd_Name()
    if not label.FindAttribute(TDataStd_Name.GetID_s(), name):
        return None
    return _normalize_label_name(name.Get().ToExtString())


def _resolve_referred_label(shape_tool: Any, label: object) -> object:
    if not shape_tool.IsReference_s(label):
        return label
    referred = TDF_Label()
    if shape_tool.GetReferredShape_s(label, referred):
        return referred
    return label


def _color_tuple(color: Quantity_ColorRGBA) -> ColorRGBA:
    rgb = color.GetRGB()
    return (
        float(rgb.Red()),
        float(rgb.Green()),
        float(rgb.Blue()),
        float(color.Alpha()),
    )


def _color_from_label(color_tool: Any, label: object) -> ColorRGBA | None:
    color = Quantity_ColorRGBA()
    for color_type in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen, XCAFDoc_ColorCurv):
        try:
            if XCAFDoc_ColorTool.GetColor_s(label, color_type, color):
                return _color_tuple(color)
        except Exception:
            continue
    return None


def _color_from_shape(color_tool: Any, shape: object) -> ColorRGBA | None:
    if getattr(shape, "IsNull", lambda: True)():
        return None
    color = Quantity_ColorRGBA()
    for color_type in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen, XCAFDoc_ColorCurv):
        try:
            if color_tool.GetColor(shape, color_type, color):
                return _color_tuple(color)
        except Exception:
            pass
        try:
            if color_tool.GetInstanceColor(shape, color_type, color):
                return _color_tuple(color)
        except Exception:
            pass
    return None


def _face_color_map_from_label(shape_tool: Any, color_tool: Any, label: object) -> dict[int, ColorRGBA]:
    face_colors: dict[int, ColorRGBA] = {}

    def collect(colored_label: object) -> None:
        label_color = _color_from_label(color_tool, colored_label)
        if label_color is not None:
            try:
                shape = shape_tool.GetShape_s(colored_label)
            except Exception:
                shape = None
            if shape is not None and not shape.IsNull():
                explorer = TopExp_Explorer(shape, TopAbs_FACE)
                while explorer.More():
                    face_colors[_shape_hash(TopoDS.Face_s(explorer.Current()))] = label_color
                    explorer.Next()
        iterator = TDF_ChildIterator(colored_label, False)
        while iterator.More():
            collect(iterator.Value())
            iterator.Next()

    collect(label)
    return face_colors


def _xcaf_children(shape_tool: Any, label: object, resolved_label: object) -> list[object]:
    children = TDF_LabelSequence()
    has_children = XCAFDoc_ShapeTool.GetComponents_s(label, children, False)
    if (not has_children or children.Length() <= 0) and resolved_label != label:
        children = TDF_LabelSequence()
        has_children = XCAFDoc_ShapeTool.GetComponents_s(resolved_label, children, False)
    if not has_children or children.Length() <= 0:
        return []
    return [children.Value(index) for index in range(1, children.Length() + 1)]


def _load_occurrence_tree(
    step_path: Path,
) -> tuple[list[OccurrenceNode], dict[int, Any], dict[int, str | None], dict[int, ColorRGBA], dict[int, dict[int, ColorRGBA]]]:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("step-selectors"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)

    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    for mode_name in ("SetMatMode", "SetLayerMode", "SetSHUOMode"):
        mode = getattr(reader, mode_name, None)
        if callable(mode):
            mode(True)
    read_status = reader.ReadFile(str(step_path))
    if int(read_status) != int(IFSelect_RetDone):
        return _load_fallback_occurrence_tree(step_path)
    if not reader.Transfer(doc):
        return _load_fallback_occurrence_tree(step_path)

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    free_labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free_labels)
    if free_labels.Length() <= 0:
        return _load_fallback_occurrence_tree(step_path)

    prototypes: dict[int, Any] = {}
    prototype_names: dict[int, str | None] = {}
    prototype_colors: dict[int, ColorRGBA] = {}
    prototype_face_colors: dict[int, dict[int, ColorRGBA]] = {}

    def collect(label: object, *, path: tuple[int, ...], parent_location: object | None = None) -> OccurrenceNode | None:
        resolved_label = _resolve_referred_label(shape_tool, label)
        instance_shape = shape_tool.GetShape_s(label)
        resolved_shape = shape_tool.GetShape_s(resolved_label)
        base_shape = instance_shape if not instance_shape.IsNull() else resolved_shape
        local_location = _shape_location(base_shape)
        current_location = _compose_locations(parent_location, local_location)
        children = _xcaf_children(shape_tool, label, resolved_label)
        name = _label_name(label) or _label_name(resolved_label)
        source_name = _label_name(resolved_label) or name
        occurrence_color = (
            _color_from_label(color_tool, label)
            or _color_from_shape(color_tool, instance_shape)
            or _color_from_label(color_tool, resolved_label)
            or _color_from_shape(color_tool, resolved_shape)
        )
        prototype_key: int | None = None
        if not children and not resolved_shape.IsNull():
            prototype_key = _shape_hash(resolved_shape)
            prototypes.setdefault(prototype_key, resolved_shape)
        elif not children and not base_shape.IsNull():
            prototype_key = _shape_hash(base_shape)
            prototypes.setdefault(prototype_key, base_shape)
        if prototype_key is not None:
            prototype_names.setdefault(prototype_key, source_name or name)
            prototype_color = _color_from_label(color_tool, resolved_label) or _color_from_shape(color_tool, resolved_shape)
            if prototype_color is not None:
                prototype_colors.setdefault(prototype_key, prototype_color)
            face_colors = _face_color_map_from_label(shape_tool, color_tool, resolved_label)
            if label != resolved_label:
                face_colors.update(_face_color_map_from_label(shape_tool, color_tool, label))
            if face_colors:
                prototype_face_colors.setdefault(prototype_key, {}).update(face_colors)
        child_nodes = [
            child_node
            for index, child in enumerate(children, start=1)
            if (child_node := collect(child, path=(*path, index), parent_location=current_location)) is not None
        ]
        if prototype_key is None and not child_nodes:
            return None
        return OccurrenceNode(
            path=path,
            name=name,
            source_name=source_name,
            transform=_location_transform_matrix(current_location),
            prototype_key=prototype_key,
            local_transform=_location_transform_matrix(local_location),
            color=occurrence_color,
            location=current_location,
            children=child_nodes,
        )

    roots = [
        node
        for index in range(1, free_labels.Length() + 1)
        if (node := collect(free_labels.Value(index), path=(index,))) is not None
    ]
    if not roots:
        return _load_fallback_occurrence_tree(step_path)
    return roots, prototypes, prototype_names, prototype_colors, prototype_face_colors


def _load_fallback_occurrence_tree(
    step_path: Path,
) -> tuple[list[OccurrenceNode], dict[int, Any], dict[int, str | None], dict[int, ColorRGBA], dict[int, dict[int, ColorRGBA]]]:
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(step_path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"failed to read STEP file: {step_path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise RuntimeError(f"STEP file produced no shape: {step_path}")
    prototype_key = _shape_hash(shape)
    return (
        [
            OccurrenceNode(
                path=(1,),
                name=step_path.stem,
                source_name=step_path.stem,
                transform=_identity_transform_matrix(),
                prototype_key=prototype_key,
                local_transform=_identity_transform_matrix(),
                location=None,
            )
        ],
        {prototype_key: shape},
        {prototype_key: step_path.stem},
        {},
        {},
    )


def load_step_scene(step_path: Path) -> LoadedStepScene:
    resolved_step_path = step_path.expanduser().resolve()
    if not resolved_step_path.exists():
        raise FileNotFoundError(f"STEP file does not exist: {resolved_step_path}")
    load_started = time.perf_counter()
    roots, prototype_shapes, prototype_names, prototype_colors, prototype_face_colors = _load_occurrence_tree(resolved_step_path)
    return LoadedStepScene(
        step_path=resolved_step_path,
        roots=roots,
        prototype_shapes=prototype_shapes,
        prototype_names=prototype_names,
        prototype_colors=prototype_colors,
        prototype_face_colors=prototype_face_colors,
        load_elapsed=time.perf_counter() - load_started,
    )


def _scene_step_hash(scene: LoadedStepScene) -> str:
    if scene.step_hash is None:
        scene.step_hash = _step_hash(scene.step_path)
    return scene.step_hash


def mesh_step_scene(
    scene: LoadedStepScene,
    *,
    linear_deflection: float,
    angular_deflection: float,
    relative: bool,
) -> None:
    signature = (float(linear_deflection), float(angular_deflection), bool(relative))
    if scene.mesh_signature == signature:
        return
    for shape in scene.prototype_shapes.values():
        BRepMesh_IncrementalMesh(
            shape,
            signature[0],
            signature[2],
            signature[1],
            True,
        )
    scene.mesh_signature = signature


def _iter_leaf_occurrences(nodes: list[OccurrenceNode]) -> list[OccurrenceNode]:
    leaves: list[OccurrenceNode] = []
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        if node.prototype_key is not None:
            leaves.append(node)
        if node.children:
            stack.extend(reversed(node.children))
    return leaves


def occurrence_selector_id(node: OccurrenceNode) -> str:
    return _selector_id(node.path)


def scene_leaf_occurrences(scene: LoadedStepScene) -> list[OccurrenceNode]:
    return _iter_leaf_occurrences(scene.roots)


def scene_occurrence_shape(scene: LoadedStepScene, node: OccurrenceNode) -> Any:
    if node.prototype_key is None or node.prototype_key not in scene.prototype_shapes:
        raise RuntimeError(f"Occurrence {occurrence_selector_id(node)} has no prototype shape")
    return _located_shape(scene.prototype_shapes[node.prototype_key], node.location)


def scene_occurrence_prototype_shape(scene: LoadedStepScene, node: OccurrenceNode) -> Any:
    if node.prototype_key is None or node.prototype_key not in scene.prototype_shapes:
        raise RuntimeError(f"Occurrence {occurrence_selector_id(node)} has no prototype shape")
    return scene.prototype_shapes[node.prototype_key]


def scene_export_shape(scene: LoadedStepScene) -> Any:
    if scene.export_shape is not None:
        return scene.export_shape
    leaf_shapes = [
        scene_occurrence_shape(scene, node)
        for node in _iter_leaf_occurrences(scene.roots)
        if node.prototype_key is not None and node.prototype_key in scene.prototype_shapes
    ]
    if not leaf_shapes:
        raise RuntimeError(f"No CAD geometry available for STL export: {scene.step_path}")
    if len(leaf_shapes) == 1:
        scene.export_shape = leaf_shapes[0]
        return scene.export_shape
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in leaf_shapes:
        builder.Add(compound, shape)
    scene.export_shape = compound
    return scene.export_shape


def _face_ordinals_from_shape(shape: Any, face_ord_by_hash: dict[int, int]) -> list[int]:
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    ordinals: list[int] = []
    seen: set[int] = set()
    while explorer.More():
        ordinal = face_ord_by_hash.get(_shape_hash(explorer.Current()))
        if ordinal is not None and ordinal not in seen:
            ordinals.append(ordinal)
            seen.add(ordinal)
        explorer.Next()
    return ordinals


def _edge_ordinals_from_shape(shape: Any, edge_ord_by_hash: dict[int, int]) -> list[int]:
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    ordinals: list[int] = []
    seen: set[int] = set()
    while explorer.More():
        ordinal = edge_ord_by_hash.get(_shape_hash(explorer.Current()))
        if ordinal is not None and ordinal not in seen:
            ordinals.append(ordinal)
            seen.add(ordinal)
        explorer.Next()
    return ordinals


def _vertex_ordinals_from_shape(shape: Any, vertex_ord_by_hash: dict[int, int]) -> list[int]:
    explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
    ordinals: list[int] = []
    seen: set[int] = set()
    while explorer.More():
        ordinal = vertex_ord_by_hash.get(_shape_hash(explorer.Current()))
        if ordinal is not None and ordinal not in seen:
            ordinals.append(ordinal)
            seen.add(ordinal)
        explorer.Next()
    return ordinals


def _prototype_shape_entries(root_shape: Any) -> tuple[str, list[dict[str, Any]], dict[int, int], dict[int, int]]:
    solid_map = TopTools_IndexedMapOfShape()
    shell_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(root_shape, TopAbs_SOLID, solid_map)
    TopExp.MapShapes_s(root_shape, TopAbs_SHELL, shell_map)

    entries: list[dict[str, Any]] = []
    face_to_shape: dict[int, int] = {}
    edge_to_shape: dict[int, int] = {}

    if solid_map.Extent() > 0:
        kind = "solid"
        map_source = solid_map
    elif shell_map.Extent() > 0:
        kind = "shell"
        map_source = shell_map
    else:
        kind = "compound"
        map_source = None

    if map_source is None:
        entries.append({"ordinal": 1, "shape": root_shape, "kind": kind})
        return kind, entries, face_to_shape, edge_to_shape

    for ordinal in range(1, map_source.Extent() + 1):
        entries.append({"ordinal": ordinal, "shape": map_source.FindKey(ordinal), "kind": kind})
    return kind, entries, face_to_shape, edge_to_shape


def _extract_summary_prototype(root_shape: Any, options: SelectorOptions) -> dict[str, Any]:
    face_map = TopTools_IndexedMapOfShape()
    edge_map = TopTools_IndexedMapOfShape()
    vertex_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(root_shape, TopAbs_FACE, face_map)
    TopExp.MapShapes_s(root_shape, TopAbs_EDGE, edge_map)
    TopExp.MapShapes_s(root_shape, TopAbs_VERTEX, vertex_map)
    kind, shape_entries, _face_to_shape, _edge_to_shape = _prototype_shape_entries(root_shape)
    return {
        "kind": kind,
        "bbox": _bbox_from_shape(root_shape),
        "shapeCount": len(shape_entries) if shape_entries else 0,
        "faceCount": face_map.Extent(),
        "edgeCount": edge_map.Extent(),
        "vertexCount": vertex_map.Extent(),
    }


def _extract_refs_prototype(
    root_shape: Any,
    options: SelectorOptions,
    *,
    include_buffers: bool,
    already_meshed: bool,
) -> dict[str, Any]:
    if not already_meshed:
        BRepMesh_IncrementalMesh(
            root_shape,
            options.linear_deflection,
            options.relative,
            options.angular_deflection,
            True,
        )

    face_map = TopTools_IndexedMapOfShape()
    edge_map = TopTools_IndexedMapOfShape()
    vertex_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(root_shape, TopAbs_FACE, face_map)
    TopExp.MapShapes_s(root_shape, TopAbs_EDGE, edge_map)
    TopExp.MapShapes_s(root_shape, TopAbs_VERTEX, vertex_map)
    face_ord_by_hash = {_shape_hash(face_map.FindKey(index)): index for index in range(1, face_map.Extent() + 1)}
    edge_ord_by_hash = {_shape_hash(edge_map.FindKey(index)): index for index in range(1, edge_map.Extent() + 1)}
    vertex_ord_by_hash = {_shape_hash(vertex_map.FindKey(index)): index for index in range(1, vertex_map.Extent() + 1)}

    kind, shape_entries, _face_to_shape, _edge_to_shape = _prototype_shape_entries(root_shape)
    if not shape_entries and (face_map.Extent() > 0 or edge_map.Extent() > 0):
        shape_entries = [{"ordinal": 1, "shape": root_shape, "kind": "compound"}]

    shape_local_by_face: dict[int, int] = {}
    shape_local_by_edge: dict[int, int] = {}
    shape_local_by_vertex: dict[int, int] = {}
    for shape_entry in shape_entries:
        face_ordinals = _face_ordinals_from_shape(shape_entry["shape"], face_ord_by_hash)
        edge_ordinals = _edge_ordinals_from_shape(shape_entry["shape"], edge_ord_by_hash)
        vertex_ordinals = _vertex_ordinals_from_shape(shape_entry["shape"], vertex_ord_by_hash)
        shape_entry["faceOrdinals"] = face_ordinals
        shape_entry["edgeOrdinals"] = edge_ordinals
        shape_entry["vertexOrdinals"] = vertex_ordinals
        for ordinal in face_ordinals:
            shape_local_by_face.setdefault(ordinal, shape_entry["ordinal"])
        for ordinal in edge_ordinals:
            shape_local_by_edge.setdefault(ordinal, shape_entry["ordinal"])
        for ordinal in vertex_ordinals:
            shape_local_by_vertex.setdefault(ordinal, shape_entry["ordinal"])

    face_edge_ordinals: dict[int, list[int]] = {}
    edge_face_ordinals: dict[int, list[int]] = {}
    edge_vertex_ordinals: dict[int, list[int]] = {}
    vertex_edge_ordinals: dict[int, list[int]] = {}
    for face_ordinal in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(face_ordinal))
        edge_ordinals = _edge_ordinals_from_shape(face, edge_ord_by_hash)
        face_edge_ordinals[face_ordinal] = edge_ordinals
        for edge_ordinal in edge_ordinals:
            edge_face_ordinals.setdefault(edge_ordinal, []).append(face_ordinal)
    for edge_ordinal in range(1, edge_map.Extent() + 1):
        edge = TopoDS.Edge_s(edge_map.FindKey(edge_ordinal))
        vertex_ordinals = _vertex_ordinals_from_shape(edge, vertex_ord_by_hash)
        edge_vertex_ordinals[edge_ordinal] = vertex_ordinals
        for vertex_ordinal in vertex_ordinals:
            vertex_edge_ordinals.setdefault(vertex_ordinal, []).append(edge_ordinal)

    face_boxes: dict[int, dict[str, Any]] = {}
    face_meshes: dict[int, dict[str, Any]] = {}
    total_face_area = 0.0
    faces: list[dict[str, Any]] = []
    for face_ordinal in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(face_ordinal))
        surface = BRepAdaptor_Surface(face)
        geometry = _extract_face_geometry(face)
        face_boxes[face_ordinal] = geometry["bbox"]
        face_meshes[face_ordinal] = geometry
        total_face_area += geometry["area"]
        face_data = {
            "ordinal": face_ordinal,
            "shapeOrdinal": shape_local_by_face.get(face_ordinal, 1),
            "surfaceType": _enum_name(surface.GetType(), "GeomAbs_"),
            "area": geometry["area"],
            "center": geometry["center"],
            "normal": geometry["normal"],
            "bbox": geometry["bbox"],
            "edgeOrdinals": tuple(face_edge_ordinals.get(face_ordinal, [])),
            "triangleNodes": geometry["nodes"],
            "triangles": geometry["triangles"],
        }
        if not (geometry["triangleCount"] > 0 and geometry["area"] > 1e-12):
            face_data["referenceable"] = False
        params = _surface_params(surface, options.digits)
        if params:
            face_data["params"] = params
        faces.append(face_data)

    global_box = _merge_bbox(list(face_boxes.values())) if face_boxes else _bbox_from_shape(root_shape)
    diag = max(global_box["diag"], 1e-9)
    edge_deflection = options.edge_deflection if options.edge_deflection is not None else diag * options.edge_deflection_ratio
    edge_deflection = max(edge_deflection, 1e-7)

    total_edge_length = 0.0
    edge_boxes: dict[int, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for edge_ordinal in range(1, edge_map.Extent() + 1):
        edge = TopoDS.Edge_s(edge_map.FindKey(edge_ordinal))
        curve = BRepAdaptor_Curve(edge)
        points: list[list[float]] = []
        for face_ordinal in edge_face_ordinals.get(edge_ordinal, []):
            points = _extract_edge_points_from_face_mesh(edge, face_meshes[face_ordinal], options.max_edge_points)
            if points:
                break
        if not points:
            points = _extract_edge_points_from_curve(edge, edge_deflection, options.max_edge_points)
        closed = bool(BRep_Tool.IsClosed_s(edge))
        length = _polyline_length(points, closed)
        total_edge_length += length
        bbox = _bbox_from_points(points)
        edge_boxes[edge_ordinal] = bbox
        seam = any(BRep_Tool.IsClosed_s(edge, TopoDS.Face_s(face_map.FindKey(face_ordinal))) for face_ordinal in edge_face_ordinals.get(edge_ordinal, []))
        degenerated = bool(BRep_Tool.Degenerated_s(edge))
        edge_data = {
            "ordinal": edge_ordinal,
            "shapeOrdinal": shape_local_by_edge.get(edge_ordinal, 1),
            "curveType": _enum_name(curve.GetType(), "GeomAbs_"),
            "length": length,
            "center": _polyline_center(points),
            "bbox": bbox,
            "faceOrdinals": tuple(edge_face_ordinals.get(edge_ordinal, [])),
            "vertexOrdinals": tuple(edge_vertex_ordinals.get(edge_ordinal, [])),
            "points": points,
        }
        if closed:
            edge_data["closed"] = True
        if degenerated:
            edge_data["degenerated"] = True
        if seam:
            edge_data["seam"] = True
        if degenerated or len(points) < 2:
            edge_data["referenceable"] = False
        params = _curve_params(curve, options.digits)
        if params:
            edge_data["params"] = params
        edges.append(edge_data)

    total_area = max(total_face_area, 1e-12)
    total_length = max(total_edge_length, 1e-12)
    size_floor = max(diag * diag * 1e-6, 1e-12)
    length_floor = max(diag * 1e-5, 1e-12)

    for face_data in faces:
        area = float(face_data["area"])
        score = 100.0 * math.sqrt(max(area, 0.0) / total_area)
        if face_data["surfaceType"] in {"plane", "cylinder", "cone", "sphere", "torus"}:
            score += 8.0
        if area < size_floor:
            score -= 45.0
        if not face_data.get("referenceable", True):
            score = 0.0
        face_data["relevance"] = max(0, min(100, int(round(score))))
        face_data["flags"] = _face_flags(face_data)

    for edge_data in edges:
        length = float(edge_data["length"])
        score = 100.0 * math.sqrt(max(length, 0.0) / total_length)
        if edge_data["curveType"] in {"line", "circle", "ellipse"}:
            score += 10.0
        if edge_data.get("seam", False):
            score -= 30.0
        if edge_data.get("degenerated", False):
            score -= 80.0
        if length < length_floor:
            score -= 35.0
        if not edge_data.get("referenceable", True):
            score = 0.0
        edge_data["relevance"] = max(0, min(100, int(round(score))))
        edge_data["flags"] = _edge_flags(edge_data)

    vertices: list[dict[str, Any]] = []
    for vertex_ordinal in range(1, vertex_map.Extent() + 1):
        vertex = TopoDS.Vertex_s(vertex_map.FindKey(vertex_ordinal))
        point = _point_from_occ(BRep_Tool.Pnt_s(vertex))
        edge_ordinals = tuple(vertex_edge_ordinals.get(vertex_ordinal, []))
        referenceable_edge_count = sum(
            1
            for edge_ordinal in edge_ordinals
            if 1 <= edge_ordinal <= len(edges) and edges[edge_ordinal - 1].get("referenceable", True)
        )
        vertex_data = {
            "ordinal": vertex_ordinal,
            "shapeOrdinal": shape_local_by_vertex.get(vertex_ordinal, 1),
            "center": point,
            "bbox": _bbox_from_points([point]),
            "edgeOrdinals": edge_ordinals,
        }
        if referenceable_edge_count < 2:
            vertex_data["referenceable"] = False
        score = 55.0 + (10.0 * min(referenceable_edge_count, 4))
        if not vertex_data.get("referenceable", True):
            score = 0.0
        vertex_data["relevance"] = max(0, min(100, int(round(score))))
        vertex_data["flags"] = _vertex_flags(vertex_data)
        vertices.append(vertex_data)

    for shape_entry in shape_entries:
        shape = shape_entry["shape"]
        face_ordinals = shape_entry.get("faceOrdinals", [])
        boxes = [face_boxes[ordinal] for ordinal in face_ordinals if ordinal in face_boxes]
        bbox = _merge_bbox(boxes) if boxes else _bbox_from_shape(shape)
        shape_entry["bbox"] = bbox
        shape_entry["area"] = sum(faces[ordinal - 1]["area"] for ordinal in face_ordinals)
        if shape_entry["kind"] == "solid":
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(shape, props, False, False, True)
            shape_entry["volume"] = props.Mass()
            shape_entry["center"] = _point_from_occ(props.CentreOfMass())
        else:
            shape_entry["center"] = bbox["center"]

    return {
        "kind": kind,
        "bbox": global_box,
        "shapeCount": len(shape_entries),
        "faceCount": len(faces),
        "edgeCount": len(edges),
        "vertexCount": len(vertices),
        "shapes": shape_entries,
        "faces": faces,
        "edges": edges,
        "vertices": vertices,
        "includeBuffers": include_buffers,
    }


def _selector_id(path: tuple[int, ...]) -> str:
    return "o" + ".".join(str(segment) for segment in path)


def _cad_ref_for_step_path(step_path: Path) -> str:
    try:
        return step_path.resolve().relative_to(REPO_ROOT).with_suffix("").as_posix()
    except ValueError:
        return step_path.resolve().with_suffix("").as_posix()


def _relative_step_path(step_path: Path) -> str:
    resolved = step_path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _step_hash(step_path: Path) -> str:
    digest = hashlib.sha256()
    with step_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_binary_bundle(output_path: Path, buffers: dict[str, array]) -> tuple[Path, dict[str, Any]]:
    bin_path = output_path.with_suffix(".bin")
    views: dict[str, Any] = {}
    offset = 0
    with bin_path.open("wb") as handle:
        for name, values in buffers.items():
            raw = values.tobytes()
            handle.write(raw)
            views[name] = {
                "dtype": "float32" if values.typecode == "f" else "uint32",
                "offset": offset,
                "count": len(values),
                "itemSize": values.itemsize,
            }
            offset += len(raw)
    return bin_path, views


def _normalize_selector_options(options: SelectorOptions | None) -> SelectorOptions:
    normalized_options = options or SelectorOptions()
    if normalized_options.digits is not None and normalized_options.digits < 0:
        return SelectorOptions(
            linear_deflection=normalized_options.linear_deflection,
            angular_deflection=normalized_options.angular_deflection,
            relative=normalized_options.relative,
            edge_deflection=normalized_options.edge_deflection,
            edge_deflection_ratio=normalized_options.edge_deflection_ratio,
            max_edge_points=normalized_options.max_edge_points,
            digits=None,
        )
    return normalized_options


def _extract_prototype(
    shape: Any,
    profile: SelectorProfile,
    options: SelectorOptions,
    *,
    already_meshed: bool = False,
) -> dict[str, Any]:
    if profile == SelectorProfile.SUMMARY:
        return _extract_summary_prototype(shape, options)
    return _extract_refs_prototype(
        shape,
        options,
        include_buffers=(profile == SelectorProfile.ARTIFACT),
        already_meshed=already_meshed,
    )


def extract_selectors_from_scene(
    scene: LoadedStepScene,
    *,
    cad_ref: str | None = None,
    profile: SelectorProfile = SelectorProfile.ARTIFACT,
    options: SelectorOptions | None = None,
) -> SelectorBundle:
    started = time.perf_counter()
    resolved_step_path = scene.step_path
    if cad_ref is None:
        cad_ref = _cad_ref_for_step_path(resolved_step_path)

    normalized_options = _normalize_selector_options(options)
    if profile != SelectorProfile.SUMMARY:
        mesh_step_scene(
            scene,
            linear_deflection=normalized_options.linear_deflection,
            angular_deflection=normalized_options.angular_deflection,
            relative=normalized_options.relative,
        )

    prototype_started = time.perf_counter()
    prototypes = {
        key: _extract_prototype(
            shape,
            profile,
            normalized_options,
            already_meshed=(profile != SelectorProfile.SUMMARY),
        )
        for key, shape in scene.prototype_shapes.items()
    }
    prototype_elapsed = time.perf_counter() - prototype_started
    load_elapsed = scene.load_elapsed

    roots = scene.roots

    occurrence_columns = [
        "id",
        "path",
        "name",
        "sourceName",
        "parentId",
        "transform",
        "bbox",
        "shapeStart",
        "shapeCount",
        "faceStart",
        "faceCount",
        "edgeStart",
        "edgeCount",
        "vertexStart",
        "vertexCount",
    ]
    shape_columns = [
        "id",
        "occurrenceId",
        "ordinal",
        "kind",
        "bbox",
        "center",
        "area",
        "volume",
        "faceStart",
        "faceCount",
        "edgeStart",
        "edgeCount",
        "vertexStart",
        "vertexCount",
    ]
    face_columns = [
        "id",
        "occurrenceId",
        "shapeId",
        "ordinal",
        "surfaceType",
        "area",
        "center",
        "normal",
        "bbox",
        "edgeStart",
        "edgeCount",
        "relevance",
        "flags",
        "params",
        "triangleStart",
        "triangleCount",
    ]
    edge_columns = [
        "id",
        "occurrenceId",
        "shapeId",
        "ordinal",
        "curveType",
        "length",
        "center",
        "bbox",
        "faceStart",
        "faceCount",
        "vertexStart",
        "vertexCount",
        "relevance",
        "flags",
        "params",
        "segmentStart",
        "segmentCount",
    ]
    vertex_columns = [
        "id",
        "occurrenceId",
        "shapeId",
        "ordinal",
        "center",
        "bbox",
        "edgeStart",
        "edgeCount",
        "relevance",
        "flags",
    ]

    occurrence_rows: list[list[Any]] = []
    shape_rows: list[list[Any]] = []
    face_rows: list[list[Any]] = []
    edge_rows: list[list[Any]] = []
    vertex_rows: list[list[Any]] = []

    face_edge_rows = array("I")
    edge_face_rows = array("I")
    edge_vertex_rows = array("I")
    vertex_edge_rows = array("I")
    face_proxy_positions = array("f")
    face_proxy_indices = array("I")
    face_proxy_ids = array("I")
    edge_proxy_positions = array("f")
    edge_proxy_indices = array("I")
    edge_proxy_ids = array("I")
    vertex_proxy_positions = array("f")
    vertex_proxy_ids = array("I")

    entry_bbox_boxes: list[dict[str, Any]] = []
    leaf_occurrence_count = 0
    summary_shape_count = 0
    summary_face_count = 0
    summary_edge_count = 0
    summary_vertex_count = 0

    def append_occurrence_row(node: OccurrenceNode) -> str:
        occurrence_id = _selector_id(node.path)
        parent_id = _selector_id(node.path[:-1]) if len(node.path) > 1 else None
        node.row_index = len(occurrence_rows)
        occurrence_rows.append(
            [
                occurrence_id,
                ".".join(str(segment) for segment in node.path),
                node.name,
                node.source_name,
                parent_id,
                _round_transform(node.transform, normalized_options.digits),
                None,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ]
        )
        return occurrence_id

    def finalize_occurrence_row(node: OccurrenceNode, bbox: dict[str, Any], ranges: dict[str, int]) -> None:
        occurrence_rows[node.row_index][6] = _compact_bbox(bbox, normalized_options.digits)
        occurrence_rows[node.row_index][7] = ranges["shapeStart"]
        occurrence_rows[node.row_index][8] = ranges["shapeCount"]
        occurrence_rows[node.row_index][9] = ranges["faceStart"]
        occurrence_rows[node.row_index][10] = ranges["faceCount"]
        occurrence_rows[node.row_index][11] = ranges["edgeStart"]
        occurrence_rows[node.row_index][12] = ranges["edgeCount"]
        occurrence_rows[node.row_index][13] = ranges["vertexStart"]
        occurrence_rows[node.row_index][14] = ranges["vertexCount"]

    def emit_leaf(node: OccurrenceNode, occurrence_id: str, prototype: dict[str, Any]) -> dict[str, Any]:
        nonlocal leaf_occurrence_count, summary_shape_count, summary_face_count, summary_edge_count, summary_vertex_count
        leaf_occurrence_count += 1

        start_shape = len(shape_rows)
        start_face = len(face_rows)
        start_edge = len(edge_rows)
        start_vertex = len(vertex_rows)

        if profile == SelectorProfile.SUMMARY:
            summary_shape_count += int(prototype.get("shapeCount") or 0)
            summary_face_count += int(prototype.get("faceCount") or 0)
            summary_edge_count += int(prototype.get("edgeCount") or 0)
            summary_vertex_count += int(prototype.get("vertexCount") or 0)
            bbox = _transform_bbox(prototype["bbox"], node.transform)
            entry_bbox_boxes.append(bbox)
            return {
                "bbox": bbox,
                "shapeStart": 0,
                "shapeCount": int(prototype.get("shapeCount") or 0),
                "faceStart": 0,
                "faceCount": int(prototype.get("faceCount") or 0),
                "edgeStart": 0,
                "edgeCount": int(prototype.get("edgeCount") or 0),
                "vertexStart": 0,
                "vertexCount": int(prototype.get("vertexCount") or 0),
            }

        local_shape_index_to_global_row: dict[int, int] = {}
        for shape_entry in prototype.get("shapes", []):
            local_shape_index_to_global_row[int(shape_entry["ordinal"])] = len(shape_rows)
            shape_rows.append(
                [
                    f"{occurrence_id}.s{shape_entry['ordinal']}",
                    occurrence_id,
                    int(shape_entry["ordinal"]),
                    shape_entry["kind"],
                    _compact_bbox(_transform_bbox(shape_entry["bbox"], node.transform), normalized_options.digits),
                    _round_point(_apply_transform_point(node.transform, shape_entry["center"]), normalized_options.digits),
                    _round_value(shape_entry.get("area", 0.0), normalized_options.digits),
                    None if shape_entry.get("volume") is None else _round_value(shape_entry["volume"], normalized_options.digits),
                    0,
                    len(shape_entry.get("faceOrdinals", [])),
                    0,
                    len(shape_entry.get("edgeOrdinals", [])),
                    0,
                    len(shape_entry.get("vertexOrdinals", [])),
                ]
            )

        local_face_index_to_global_row: dict[int, int] = {}
        for face_entry in prototype.get("faces", []):
            local_face_index_to_global_row[int(face_entry["ordinal"])] = len(face_rows)
            edge_start = len(face_edge_rows)
            face_rows.append(
                [
                    f"{occurrence_id}.f{face_entry['ordinal']}",
                    occurrence_id,
                    f"{occurrence_id}.s{face_entry['shapeOrdinal']}",
                    int(face_entry["ordinal"]),
                    face_entry["surfaceType"],
                    _round_value(face_entry["area"], normalized_options.digits),
                    _round_point(_apply_transform_point(node.transform, face_entry["center"]), normalized_options.digits),
                    None
                    if face_entry.get("normal") is None
                    else _round_point(_apply_transform_vector(node.transform, face_entry["normal"]) or face_entry["normal"], normalized_options.digits),
                    _compact_bbox(_transform_bbox(face_entry["bbox"], node.transform), normalized_options.digits),
                    edge_start,
                    len(face_entry["edgeOrdinals"]),
                    int(face_entry.get("relevance", 0)),
                    int(face_entry.get("flags", 0)),
                    None
                    if face_entry.get("params") is None
                    else _transform_param_dict(face_entry["params"], node.transform, normalized_options.digits),
                    0,
                    0,
                ]
            )

        local_edge_index_to_global_row: dict[int, int] = {}
        for edge_entry in prototype.get("edges", []):
            local_edge_index_to_global_row[int(edge_entry["ordinal"])] = len(edge_rows)
            face_start = len(edge_face_rows)
            edge_rows.append(
                [
                    f"{occurrence_id}.e{edge_entry['ordinal']}",
                    occurrence_id,
                    f"{occurrence_id}.s{edge_entry['shapeOrdinal']}",
                    int(edge_entry["ordinal"]),
                    edge_entry["curveType"],
                    _round_value(edge_entry["length"], normalized_options.digits),
                    _round_point(_apply_transform_point(node.transform, edge_entry["center"]), normalized_options.digits),
                    _compact_bbox(_transform_bbox(edge_entry["bbox"], node.transform), normalized_options.digits),
                    face_start,
                    len(edge_entry["faceOrdinals"]),
                    0,
                    len(edge_entry.get("vertexOrdinals", [])),
                    int(edge_entry.get("relevance", 0)),
                    int(edge_entry.get("flags", 0)),
                    None
                    if edge_entry.get("params") is None
                    else _transform_param_dict(edge_entry["params"], node.transform, normalized_options.digits),
                    0,
                    0,
                ]
            )

        local_vertex_index_to_global_row: dict[int, int] = {}
        for vertex_entry in prototype.get("vertices", []):
            local_vertex_index_to_global_row[int(vertex_entry["ordinal"])] = len(vertex_rows)
            vertex_rows.append(
                [
                    f"{occurrence_id}.v{vertex_entry['ordinal']}",
                    occurrence_id,
                    f"{occurrence_id}.s{vertex_entry['shapeOrdinal']}",
                    int(vertex_entry["ordinal"]),
                    _round_point(_apply_transform_point(node.transform, vertex_entry["center"]), normalized_options.digits),
                    _compact_bbox(_transform_bbox(vertex_entry["bbox"], node.transform), normalized_options.digits),
                    0,
                    len(vertex_entry["edgeOrdinals"]),
                    int(vertex_entry.get("relevance", 0)),
                    int(vertex_entry.get("flags", 0)),
                ]
            )

        for shape_entry in prototype.get("shapes", []):
            global_shape_row = local_shape_index_to_global_row[int(shape_entry["ordinal"])]
            if shape_entry.get("faceOrdinals"):
                first_face_global = local_face_index_to_global_row[shape_entry["faceOrdinals"][0]]
            else:
                first_face_global = len(face_rows)
            if shape_entry.get("edgeOrdinals"):
                first_edge_global = local_edge_index_to_global_row[shape_entry["edgeOrdinals"][0]]
            else:
                first_edge_global = len(edge_rows)
            if shape_entry.get("vertexOrdinals"):
                first_vertex_global = local_vertex_index_to_global_row[shape_entry["vertexOrdinals"][0]]
            else:
                first_vertex_global = len(vertex_rows)
            shape_rows[global_shape_row][8] = first_face_global
            shape_rows[global_shape_row][10] = first_edge_global
            shape_rows[global_shape_row][12] = first_vertex_global

        for face_entry in prototype.get("faces", []):
            global_face_row = local_face_index_to_global_row[int(face_entry["ordinal"])]
            edge_start = len(face_edge_rows)
            face_rows[global_face_row][9] = edge_start
            for edge_ordinal in face_entry["edgeOrdinals"]:
                face_edge_rows.append(local_edge_index_to_global_row[int(edge_ordinal)])

        for edge_entry in prototype.get("edges", []):
            global_edge_row = local_edge_index_to_global_row[int(edge_entry["ordinal"])]
            face_start = len(edge_face_rows)
            vertex_start = len(edge_vertex_rows)
            edge_rows[global_edge_row][8] = face_start
            edge_rows[global_edge_row][10] = vertex_start
            for face_ordinal in edge_entry["faceOrdinals"]:
                edge_face_rows.append(local_face_index_to_global_row[int(face_ordinal)])
            for vertex_ordinal in edge_entry.get("vertexOrdinals", []):
                edge_vertex_rows.append(local_vertex_index_to_global_row[int(vertex_ordinal)])

        for vertex_entry in prototype.get("vertices", []):
            global_vertex_row = local_vertex_index_to_global_row[int(vertex_entry["ordinal"])]
            edge_start = len(vertex_edge_rows)
            vertex_rows[global_vertex_row][6] = edge_start
            for edge_ordinal in vertex_entry["edgeOrdinals"]:
                vertex_edge_rows.append(local_edge_index_to_global_row[int(edge_ordinal)])

        if profile == SelectorProfile.ARTIFACT:
            for face_entry in prototype.get("faces", []):
                global_face_row = local_face_index_to_global_row[int(face_entry["ordinal"])]
                vertex_offset = len(face_proxy_positions) // 3
                triangle_start = len(face_proxy_ids)
                for point in face_entry["triangleNodes"]:
                    transformed = _apply_transform_point(node.transform, point)
                    face_proxy_positions.extend(_round_point(transformed, normalized_options.digits))
                for node_a, node_b, node_c in face_entry["triangles"]:
                    face_proxy_indices.extend([vertex_offset + node_a, vertex_offset + node_b, vertex_offset + node_c])
                    face_proxy_ids.append(global_face_row)
                face_rows[global_face_row][14] = triangle_start
                face_rows[global_face_row][15] = len(face_entry["triangles"])

            for edge_entry in prototype.get("edges", []):
                global_edge_row = local_edge_index_to_global_row[int(edge_entry["ordinal"])]
                points = edge_entry["points"]
                if len(points) < 2:
                    continue
                vertex_offset = len(edge_proxy_positions) // 3
                segment_start = len(edge_proxy_ids)
                for point in points:
                    transformed = _apply_transform_point(node.transform, point)
                    edge_proxy_positions.extend(_round_point(transformed, normalized_options.digits))
                for local_index in range(len(points) - 1):
                    edge_proxy_indices.extend([vertex_offset + local_index, vertex_offset + local_index + 1])
                    edge_proxy_ids.append(global_edge_row)
                if edge_entry.get("closed", False) and _distance(points[0], points[-1]) > 1e-9:
                    edge_proxy_indices.extend([vertex_offset + len(points) - 1, vertex_offset])
                    edge_proxy_ids.append(global_edge_row)
                edge_rows[global_edge_row][15] = segment_start
                edge_rows[global_edge_row][16] = len(edge_proxy_ids) - segment_start

            for vertex_entry in prototype.get("vertices", []):
                global_vertex_row = local_vertex_index_to_global_row[int(vertex_entry["ordinal"])]
                point = _apply_transform_point(node.transform, vertex_entry["center"])
                vertex_proxy_positions.extend(_round_point(point, normalized_options.digits))
                vertex_proxy_ids.append(global_vertex_row)

        bbox = _transform_bbox(prototype["bbox"], node.transform)
        entry_bbox_boxes.append(bbox)
        return {
            "bbox": bbox,
            "shapeStart": start_shape,
            "shapeCount": len(shape_rows) - start_shape,
            "faceStart": start_face,
            "faceCount": len(face_rows) - start_face,
            "edgeStart": start_edge,
            "edgeCount": len(edge_rows) - start_edge,
            "vertexStart": start_vertex,
            "vertexCount": len(vertex_rows) - start_vertex,
        }

    def emit_node(node: OccurrenceNode) -> dict[str, Any]:
        occurrence_id = append_occurrence_row(node)
        shape_start = len(shape_rows)
        face_start = len(face_rows)
        edge_start = len(edge_rows)
        vertex_start = len(vertex_rows)
        child_boxes: list[dict[str, Any]] = []
        aggregated_shape_count = 0
        aggregated_face_count = 0
        aggregated_edge_count = 0
        aggregated_vertex_count = 0

        if node.prototype_key is not None:
            leaf_result = emit_leaf(node, occurrence_id, prototypes[node.prototype_key])
            child_boxes.append(leaf_result["bbox"])
            aggregated_shape_count += int(leaf_result["shapeCount"])
            aggregated_face_count += int(leaf_result["faceCount"])
            aggregated_edge_count += int(leaf_result["edgeCount"])
            aggregated_vertex_count += int(leaf_result["vertexCount"])

        for child in node.children:
            child_result = emit_node(child)
            child_boxes.append(child_result["bbox"])
            aggregated_shape_count += int(child_result["shapeCount"])
            aggregated_face_count += int(child_result["faceCount"])
            aggregated_edge_count += int(child_result["edgeCount"])
            aggregated_vertex_count += int(child_result["vertexCount"])

        bbox = _merge_bbox(child_boxes) if child_boxes else _bbox_from_points([])
        ranges = {
            "shapeStart": shape_start if profile != SelectorProfile.SUMMARY else 0,
            "shapeCount": aggregated_shape_count if profile == SelectorProfile.SUMMARY else len(shape_rows) - shape_start,
            "faceStart": face_start if profile != SelectorProfile.SUMMARY else 0,
            "faceCount": aggregated_face_count if profile == SelectorProfile.SUMMARY else len(face_rows) - face_start,
            "edgeStart": edge_start if profile != SelectorProfile.SUMMARY else 0,
            "edgeCount": aggregated_edge_count if profile == SelectorProfile.SUMMARY else len(edge_rows) - edge_start,
            "vertexStart": vertex_start if profile != SelectorProfile.SUMMARY else 0,
            "vertexCount": aggregated_vertex_count if profile == SelectorProfile.SUMMARY else len(vertex_rows) - vertex_start,
        }
        finalize_occurrence_row(node, bbox, ranges)
        return {"bbox": bbox, **ranges}

    for root in roots:
        emit_node(root)

    overall_bbox = _merge_bbox(entry_bbox_boxes) if entry_bbox_boxes else _bbox_from_points([])
    elapsed = load_elapsed + (time.perf_counter() - started)

    stats = {
        "occurrenceCount": len(occurrence_rows),
        "leafOccurrenceCount": leaf_occurrence_count,
        "shapeCount": summary_shape_count if profile == SelectorProfile.SUMMARY else len(shape_rows),
        "faceCount": summary_face_count if profile == SelectorProfile.SUMMARY else len(face_rows),
        "edgeCount": summary_edge_count if profile == SelectorProfile.SUMMARY else len(edge_rows),
        "vertexCount": summary_vertex_count if profile == SelectorProfile.SUMMARY else len(vertex_rows),
        "faceProxyVertexCount": len(face_proxy_positions) // 3 if profile == SelectorProfile.ARTIFACT else 0,
        "faceProxyTriangleCount": len(face_proxy_ids) if profile == SelectorProfile.ARTIFACT else 0,
        "edgeProxyVertexCount": len(edge_proxy_positions) // 3 if profile == SelectorProfile.ARTIFACT else 0,
        "edgeProxySegmentCount": len(edge_proxy_ids) if profile == SelectorProfile.ARTIFACT else 0,
        "vertexProxyPointCount": len(vertex_proxy_ids) if profile == SelectorProfile.ARTIFACT else 0,
        "timingMs": {
            "load": round(load_elapsed * 1000.0, 1),
            "extract": round(prototype_elapsed * 1000.0, 1),
            "total": round(elapsed * 1000.0, 1),
        },
    }

    manifest: dict[str, Any] = {
        "schemaVersion": 2,
        "profile": profile.value,
        "cadRef": cad_ref,
        "stepPath": _relative_step_path(resolved_step_path),
        "stepHash": _scene_step_hash(scene),
        "bbox": _compact_bbox(overall_bbox, normalized_options.digits),
        "stats": stats,
        "tables": {
            "occurrenceColumns": occurrence_columns,
            "shapeColumns": shape_columns,
            "faceColumns": face_columns,
            "edgeColumns": edge_columns,
            "vertexColumns": vertex_columns,
        },
        "occurrences": occurrence_rows,
        "shapes": shape_rows,
        "faces": face_rows,
        "edges": edge_rows,
        "vertices": vertex_rows,
    }

    if profile != SelectorProfile.SUMMARY:
        if profile == SelectorProfile.ARTIFACT:
            manifest["faceProxy"] = {
                "positionsView": "facePositions",
                "indicesView": "faceIndices",
                "faceIdsView": "faceIds",
            }
            manifest["edgeProxy"] = {
                "positionsView": "edgePositions",
                "indicesView": "edgeIndices",
                "edgeIdsView": "edgeIds",
            }
            manifest["vertexProxy"] = {
                "positionsView": "vertexPositions",
                "vertexIdsView": "vertexIds",
            }
            manifest["relations"] = {
                "faceEdgeRowsView": "faceEdgeRows",
                "edgeFaceRowsView": "edgeFaceRows",
                "edgeVertexRowsView": "edgeVertexRows",
                "vertexEdgeRowsView": "vertexEdgeRows",
            }
            buffers = {
                "facePositions": face_proxy_positions,
                "faceIndices": face_proxy_indices,
                "faceIds": face_proxy_ids,
                "edgePositions": edge_proxy_positions,
                "edgeIndices": edge_proxy_indices,
                "edgeIds": edge_proxy_ids,
                "vertexPositions": vertex_proxy_positions,
                "vertexIds": vertex_proxy_ids,
                "faceEdgeRows": face_edge_rows,
                "edgeFaceRows": edge_face_rows,
                "edgeVertexRows": edge_vertex_rows,
                "vertexEdgeRows": vertex_edge_rows,
            }
            return SelectorBundle(manifest=manifest, buffers=buffers)

        manifest["relations"] = {
            "faceEdgeRows": list(face_edge_rows),
            "edgeFaceRows": list(edge_face_rows),
            "edgeVertexRows": list(edge_vertex_rows),
            "vertexEdgeRows": list(vertex_edge_rows),
        }

    return SelectorBundle(manifest=manifest)


def extract_selectors(
    step_path: Path,
    *,
    cad_ref: str | None = None,
    profile: SelectorProfile = SelectorProfile.ARTIFACT,
    options: SelectorOptions | None = None,
) -> SelectorBundle:
    scene = load_step_scene(step_path)
    return extract_selectors_from_scene(
        scene,
        cad_ref=cad_ref,
        profile=profile,
        options=options,
    )


def _rewrite_manifest_paths_for_output(manifest: dict[str, Any], output_path: Path) -> None:
    raw_step_path = manifest.get("stepPath")
    if isinstance(raw_step_path, str) and raw_step_path.strip():
        step_path = Path(raw_step_path)
        resolved_step_path = step_path.resolve() if step_path.is_absolute() else (Path.cwd() / step_path).resolve()
        manifest["stepPath"] = os.path.relpath(resolved_step_path, start=output_path.parent).replace(os.sep, "/")


def write_selector_artifacts(bundle: SelectorBundle, manifest_path: Path) -> Path:
    output_path = manifest_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(bundle.manifest)
    _rewrite_manifest_paths_for_output(manifest, output_path)
    if bundle.buffers:
        bin_path, views = _write_binary_bundle(output_path, bundle.buffers)
        manifest["buffers"] = {
            "uri": bin_path.name,
            "littleEndian": sys.byteorder == "little",
            "views": views,
        }
    output_path.write_text(json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8")
    bundle.manifest = manifest
    return output_path
