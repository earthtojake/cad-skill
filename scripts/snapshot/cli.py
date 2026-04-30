from __future__ import annotations

import argparse
import math
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO_ROOT = Path.cwd().resolve()
CAD_ROOT = REPO_ROOT
DEFAULT_MODEL_COLOR = (0.80, 0.84, 0.90)
DEFAULT_BACKGROUND_COLOR = (0.98, 0.985, 0.99)
BUILD123D_GLB_ROOT_CORRECTION = np.asarray(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)
FALLBACK_COMPONENT_COLORS: tuple[tuple[float, float, float], ...] = (
    (0.82, 0.84, 0.88),
    (0.68, 0.77, 0.91),
    (0.70, 0.86, 0.79),
    (0.93, 0.79, 0.62),
    (0.88, 0.72, 0.78),
    (0.76, 0.72, 0.90),
    (0.85, 0.83, 0.62),
    (0.68, 0.86, 0.87),
)
MAX_RENDER_TRIANGLES_PER_MESH = 12000
FEATURE_EDGE_ANGLE_DEG = 32.0
BASE_MARGIN_PX = 12.0
CROP_PADDING_PX = 12
AXIS_BOX_SIZE_PX = 46
VIEW_OUTPUT_ORDER = ("isometric", "front", "back", "right", "left", "top", "bottom")


@dataclass(frozen=True)
class CameraView:
    name: str
    direction: tuple[float, float, float]
    up: tuple[float, float, float]


VIEW_PRESETS: dict[str, CameraView] = {
    "front": CameraView(name="front", direction=(0.0, 0.0, 1.0), up=(0.0, 1.0, 0.0)),
    "back": CameraView(name="back", direction=(0.0, 0.0, -1.0), up=(0.0, 1.0, 0.0)),
    "right": CameraView(name="right", direction=(1.0, 0.0, 0.0), up=(0.0, 1.0, 0.0)),
    "left": CameraView(name="left", direction=(-1.0, 0.0, 0.0), up=(0.0, 1.0, 0.0)),
    "top": CameraView(name="top", direction=(0.0, 1.0, 0.0), up=(0.0, 0.0, 1.0)),
    "bottom": CameraView(name="bottom", direction=(0.0, -1.0, 0.0), up=(0.0, 0.0, 1.0)),
    "isometric": CameraView(name="isometric", direction=(1.0, 1.0, 1.0), up=(0.0, 1.0, 0.0)),
}


@dataclass(frozen=True)
class MeshInstance:
    vertices: np.ndarray
    triangles: np.ndarray
    color_rgb: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class ProjectedMeshInstance:
    screen_points: np.ndarray
    view_points: np.ndarray
    triangles: np.ndarray
    face_brightness: np.ndarray
    face_normals: np.ndarray
    feature_edges: tuple[tuple[int, int], ...]
    color_rgb: tuple[float, float, float]


def _rgb_default(rgb: tuple[float, float, float]) -> str:
    return ",".join(str(channel) for channel in rgb)


def parse_rgb(raw_value: str) -> tuple[float, float, float]:
    parts = [part.strip() for part in raw_value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Invalid RGB value: {raw_value}")
    rgb = tuple(float(part) for part in parts)
    if not all(0.0 <= channel <= 1.0 for channel in rgb):
        raise ValueError(f"RGB values must be in range [0, 1]: {raw_value}")
    return rgb  # type: ignore[return-value]


def resolve_view(view: str | CameraView) -> CameraView:
    return VIEW_PRESETS[view] if isinstance(view, str) else view


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render CAD snapshot PNGs from GLB or STL mesh files. Prefer generated assembly GLBs."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to a part GLB, generated assembly GLB, or STL mesh.",
    )
    parser.add_argument("--out", type=Path, help="Write one PNG snapshot to this path.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Write one PNG per view into this directory. Required with --views.",
    )
    parser.add_argument(
        "--view",
        choices=sorted(VIEW_PRESETS),
        default=None,
        help="Camera preset. Defaults to isometric unless --align-ref is used.",
    )
    parser.add_argument(
        "--align-ref",
        help="Resolve an @cad[...] face or edge ref and choose the closest orthographic view automatically.",
    )
    parser.add_argument(
        "--views",
        help="Comma-separated camera presets, or 'all', for batched snapshots. Requires --out-dir.",
    )
    parser.add_argument("--width", type=int, default=1400, help="Maximum output width")
    parser.add_argument("--height", type=int, default=900, help="Maximum output height")
    parser.add_argument(
        "--color",
        default=_rgb_default(DEFAULT_MODEL_COLOR),
        help="Model RGB in 0..1, e.g. '0.80,0.84,0.90'",
    )
    parser.add_argument(
        "--background",
        default=_rgb_default(DEFAULT_BACKGROUND_COLOR),
        help="Background RGB in 0..1, e.g. '0.98,0.985,0.99'",
    )
    parser.add_argument(
        "--edges",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Overlay visible feature edges. Default: true",
    )
    parser.add_argument(
        "--axes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show orientation axes in a reserved inset. Default: true",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    render_jobs = _resolve_render_jobs(args, parser)

    mesh_instances = load_mesh_instances(args.input)
    if not mesh_instances:
        raise RuntimeError(f"No mesh geometry found in {args.input}")

    model_color = parse_rgb(args.color)
    background_color = parse_rgb(args.background)
    for view_name, png_out in render_jobs:
        render_mesh_instances(
            mesh_instances,
            png_out=png_out,
            view=view_name,
            width=args.width,
            height=args.height,
            model_color=model_color,
            background_color=background_color,
            edges=bool(args.edges),
            axes=bool(args.axes),
        )
        label = f"{view_name} " if len(render_jobs) > 1 else ""
        print(f"saved {label}png: {png_out.resolve()}")
    return 0

def _resolve_render_jobs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[tuple[str, Path]]:
    views = str(args.views or "").strip()
    if views:
        if args.view:
            parser.error("--views cannot be combined with --view")
        if args.align_ref:
            parser.error("--views cannot be combined with --align-ref")
        if args.out:
            parser.error("--views writes multiple files; use --out-dir instead of --out")
        if not args.out_dir:
            parser.error("--views requires --out-dir")
        try:
            view_names = _parse_views_arg(views)
        except ValueError as exc:
            parser.error(str(exc))
        output_stem = _snapshot_output_stem(args.input)
        return [(view_name, args.out_dir / f"{output_stem}-{view_name}.png") for view_name in view_names]

    if args.out_dir:
        parser.error("--out-dir requires --views")
    if not args.out:
        parser.error("--out is required unless --views and --out-dir are used")
    view_name = str(args.view or "").strip() or _resolve_aligned_view_name(args.align_ref) or "isometric"
    return [(view_name, args.out)]


def _parse_views_arg(raw_value: str) -> tuple[str, ...]:
    if raw_value.strip().lower() == "all":
        return VIEW_OUTPUT_ORDER
    view_names: list[str] = []
    for raw_part in raw_value.split(","):
        view_name = raw_part.strip()
        if not view_name:
            continue
        if view_name not in VIEW_PRESETS:
            allowed = ", ".join(VIEW_OUTPUT_ORDER)
            raise ValueError(f"Unknown snapshot view {view_name!r}; expected one of: {allowed}, or all")
        if view_name not in view_names:
            view_names.append(view_name)
    if not view_names:
        raise ValueError("--views must include at least one view")
    return tuple(view_names)


def _snapshot_output_stem(input_path: Path) -> str:
    stem = input_path.stem
    if input_path.name.lower() == "model.glb" and input_path.parent.name.startswith("."):
        stem = input_path.parent.name[1:]
        for suffix in (".step", ".stp"):
            if stem.lower().endswith(suffix):
                stem = stem[: -len(suffix)]
                break
    cleaned = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in stem)
    cleaned = cleaned.strip("_")
    return cleaned or "snapshot"


def _resolve_aligned_view_name(cad_ref: str | None) -> str | None:
    if not cad_ref:
        return None
    from cadref import analysis as cadref_analysis
    from cadref.inspect import CadRefError, inspect_cad_refs

    try:
        result = inspect_cad_refs(cad_ref, facts=True)
    except CadRefError as exc:
        raise ValueError(str(exc)) from exc
    tokens = result.get("tokens")
    if not isinstance(tokens, list) or len(tokens) != 1:
        raise ValueError(f"Failed to resolve render alignment ref: {cad_ref}")
    token = tokens[0]
    if not isinstance(token, dict):
        raise ValueError(f"Failed to resolve render alignment ref: {cad_ref}")
    selections = token.get("selections")
    if not isinstance(selections, list) or len(selections) != 1:
        raise ValueError("snapshot --align-ref expects exactly one face or edge ref.")
    selection = selections[0]
    if not isinstance(selection, dict) or selection.get("status") != "resolved":
        raise ValueError(f"snapshot failed to resolve {cad_ref}")
    selector_type = str(selection.get("selectorType") or "")
    if selector_type not in {"face", "edge"}:
        raise ValueError("snapshot --align-ref only supports face or edge refs.")
    geometry_facts = selection.get("geometryFacts")
    if not isinstance(geometry_facts, dict):
        raise ValueError(f"snapshot could not derive geometry facts for {cad_ref}")
    view_name = cadref_analysis.aligned_view_name_for_facts(selector_type, geometry_facts)
    if not view_name:
        raise ValueError(f"snapshot could not determine an aligned view for {cad_ref}")
    return view_name


def load_mesh_instances(input_path: Path) -> list[MeshInstance]:
    resolved_input = _resolve_cad_path(input_path, kind="input")
    lowered = resolved_input.name.lower()
    if lowered.endswith(".py"):
        raise ValueError(
            "Python assembly inputs are no longer supported by snapshot; "
            "render the generated assembly GLB instead."
        )
    if lowered.endswith(".glb"):
        return [_read_glb_mesh(resolved_input)]
    if lowered.endswith(".stl"):
        return [_read_stl_mesh(resolved_input)]
    raise ValueError(f"Unsupported snapshot input: {input_path}")


def render_mesh_instances(
    mesh_instances: list[MeshInstance],
    *,
    png_out: Path,
    view: str,
    width: int,
    height: int,
    model_color: tuple[float, float, float],
    background_color: tuple[float, float, float],
    edges: bool,
    axes: bool,
) -> None:
    active_instances = [instance for instance in mesh_instances if _instance_has_geometry(instance)]
    if not active_instances:
        raise RuntimeError("No renderable mesh geometry found")

    projected_instances, right, true_up = _project_instances(
        active_instances,
        view=view,
        width=width,
        height=height,
        model_color=model_color,
        include_edges=edges,
    )
    image = _render_scene(
        projected_instances,
        width=width,
        height=height,
        background_color=background_color,
        edges=edges,
        axes=axes,
        right=right,
        true_up=true_up,
    )
    _write_png(image, png_out)


def _resolve_cad_path(path: Path, *, kind: str) -> Path:
    resolved = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"snapshot {kind} not found: {path}")
    lowered = resolved.name.lower()
    if lowered.endswith((".glb", ".stl")):
        return resolved
    return resolved


def _read_glb_mesh(
    glb_path: Path,
    *,
    transform: object | None = None,
    mesh_cache: dict[Path, MeshInstance] | None = None,
) -> MeshInstance:
    import trimesh

    resolved_path = glb_path.resolve()
    base_mesh = mesh_cache.get(resolved_path) if mesh_cache is not None else None
    if base_mesh is None:
        loaded = trimesh.load(resolved_path, force="scene")
        if isinstance(loaded, trimesh.Scene):
            cad_correction = _build123d_glb_cad_correction(loaded)
            mesh = loaded.to_geometry()
        elif isinstance(loaded, trimesh.Trimesh):
            cad_correction = None
            mesh = loaded
        else:
            raise RuntimeError(f"No GLB geometry loaded from {resolved_path}")
        if mesh.vertices.size <= 0 or mesh.faces.size <= 0:
            raise RuntimeError(f"No GLB geometry loaded from {resolved_path}")
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        if cad_correction is not None:
            vertices = _apply_transform(vertices, cad_correction)
        vertices = vertices * 1000.0
        triangles = np.asarray(mesh.faces, dtype=np.int64)
        base_mesh = MeshInstance(vertices=vertices, triangles=triangles)
        if mesh_cache is not None:
            mesh_cache[resolved_path] = base_mesh

    if transform is None:
        return base_mesh
    return MeshInstance(
        vertices=_apply_transform(base_mesh.vertices, transform),
        triangles=base_mesh.triangles,
        color_rgb=base_mesh.color_rgb,
    )


def _build123d_glb_cad_correction(scene: object) -> np.ndarray | None:
    graph = getattr(scene, "graph", None)
    base_frame = getattr(graph, "base_frame", None)
    transforms = getattr(graph, "transforms", None)
    children_by_parent = getattr(transforms, "children", None)
    if graph is None or base_frame is None or not isinstance(children_by_parent, dict):
        return None
    root_children = list(children_by_parent.get(base_frame, ()))
    if len(root_children) != 1:
        return None
    try:
        root_matrix = np.asarray(graph[root_children[0]][0], dtype=np.float64)
    except Exception:
        return None
    if root_matrix.shape != (4, 4):
        return None
    if not np.allclose(root_matrix, BUILD123D_GLB_ROOT_CORRECTION, atol=1e-6, rtol=0.0):
        return None
    return np.linalg.inv(root_matrix)


def _read_stl_mesh(
    stl_path: Path,
    *,
    transform: object | None = None,
    mesh_cache: dict[Path, MeshInstance] | None = None,
) -> MeshInstance:
    vtk, vtk_to_numpy = _vtk_modules()

    resolved_path = stl_path.resolve()
    base_mesh = mesh_cache.get(resolved_path) if mesh_cache is not None else None
    if base_mesh is None:
        reader = vtk.vtkSTLReader()
        reader.SetFileName(str(resolved_path))
        reader.Update()

        polydata = vtk.vtkPolyData()
        polydata.ShallowCopy(reader.GetOutput())
        if polydata.GetNumberOfPoints() <= 0:
            raise RuntimeError(f"No STL geometry loaded from {resolved_path}")

        preview_polydata = _prepare_preview_polydata(polydata)
        triangles = _triangle_indices(preview_polydata)
        points = preview_polydata.GetPoints()
        if points is None or points.GetNumberOfPoints() <= 0:
            raise RuntimeError(f"No STL point data loaded from {resolved_path}")
        vertices = np.asarray(vtk_to_numpy(points.GetData()), dtype=np.float64)
        base_mesh = MeshInstance(vertices=vertices, triangles=triangles)
        if mesh_cache is not None:
            mesh_cache[resolved_path] = base_mesh

    if transform is None:
        return base_mesh
    return MeshInstance(
        vertices=_apply_transform(base_mesh.vertices, transform),
        triangles=base_mesh.triangles,
        color_rgb=base_mesh.color_rgb,
    )


def _vtk_modules() -> tuple[object, object]:
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy

    return vtk, vtk_to_numpy


def _prepare_preview_polydata(polydata: object) -> object:
    vtk, _vtk_to_numpy = _vtk_modules()

    triangle_filter = vtk.vtkTriangleFilter()
    triangle_filter.SetInputData(polydata)
    triangle_filter.Update()

    current = vtk.vtkPolyData()
    current.ShallowCopy(triangle_filter.GetOutput())
    triangle_count = max(current.GetNumberOfPolys(), current.GetNumberOfCells())
    if triangle_count > MAX_RENDER_TRIANGLES_PER_MESH:
        decimator = vtk.vtkQuadricDecimation()
        decimator.SetInputData(current)
        decimator.SetTargetReduction(
            max(0.0, min(0.99, 1.0 - (MAX_RENDER_TRIANGLES_PER_MESH / float(triangle_count))))
        )
        volume_preservation = getattr(decimator, "VolumePreservationOn", None)
        if callable(volume_preservation):
            volume_preservation()
        decimator.Update()
        current.ShallowCopy(decimator.GetOutput())

        retriangulate = vtk.vtkTriangleFilter()
        retriangulate.SetInputData(current)
        retriangulate.Update()
        current.ShallowCopy(retriangulate.GetOutput())

    return current


def _triangle_indices(polydata: object) -> np.ndarray:
    _vtk, vtk_to_numpy = _vtk_modules()

    polys = polydata.GetPolys()
    if polys is None or polys.GetNumberOfCells() <= 0 or polys.GetData() is None:
        raise RuntimeError("STL mesh does not contain polygon cells")

    raw = np.asarray(vtk_to_numpy(polys.GetData()), dtype=np.int64)
    if raw.size % 4 != 0 or np.any(raw[::4] != 3):
        raise RuntimeError("STL mesh contains non-triangular faces after preprocessing")
    return raw.reshape(-1, 4)[:, 1:]


def _apply_transform(vertices: np.ndarray, transform: object) -> np.ndarray:
    if isinstance(transform, np.ndarray) and transform.shape == (4, 4):
        matrix = transform.astype(np.float64, copy=False)
    elif isinstance(transform, (list, tuple)) and len(transform) == 16:
        matrix = np.asarray([float(value) for value in transform], dtype=np.float64).reshape(4, 4)
    else:
        raise ValueError("manifest transform must be a 16-number array")
    homogeneous = np.concatenate([vertices, np.ones((vertices.shape[0], 1), dtype=np.float64)], axis=1)
    transformed = homogeneous @ matrix.T
    w = transformed[:, 3:4]
    safe_w = np.where(np.abs(w) > 1e-12, w, 1.0)
    return transformed[:, :3] / safe_w


def _instance_has_geometry(instance: MeshInstance) -> bool:
    return instance.vertices.size > 0 and instance.triangles.size > 0


def _project_instances(
    mesh_instances: list[MeshInstance],
    *,
    view: str,
    width: int,
    height: int,
    model_color: tuple[float, float, float],
    include_edges: bool,
) -> tuple[list[ProjectedMeshInstance], np.ndarray, np.ndarray]:
    resolved_view = resolve_view(view)
    right, true_up, view_normal = _camera_basis(resolved_view.direction, resolved_view.up)

    all_vertices = np.concatenate([instance.vertices for instance in mesh_instances], axis=0)
    center = 0.5 * (all_vertices.min(axis=0) + all_vertices.max(axis=0))

    projected_xyz: list[np.ndarray] = []
    x_min = math.inf
    x_max = -math.inf
    y_min = math.inf
    y_max = -math.inf
    for instance in mesh_instances:
        relative = instance.vertices - center
        view_points = np.column_stack(
            (
                relative @ right,
                relative @ true_up,
                relative @ view_normal,
            )
        )
        projected_xyz.append(view_points)
        x_min = min(x_min, float(view_points[:, 0].min()))
        x_max = max(x_max, float(view_points[:, 0].max()))
        y_min = min(y_min, float(view_points[:, 1].min()))
        y_max = max(y_max, float(view_points[:, 1].max()))

    available_width = max(1.0, width - (2.0 * BASE_MARGIN_PX))
    available_height = max(1.0, height - (2.0 * BASE_MARGIN_PX))
    span_x = max(x_max - x_min, 1e-6)
    span_y = max(y_max - y_min, 1e-6)
    scale = min(available_width / span_x, available_height / span_y)
    geometry_width = span_x * scale
    geometry_height = span_y * scale
    offset_x = BASE_MARGIN_PX + ((available_width - geometry_width) * 0.5)
    geometry_bottom = height - (BASE_MARGIN_PX + ((available_height - geometry_height) * 0.5))

    projected_instances: list[ProjectedMeshInstance] = []
    component_count = len(mesh_instances)
    for index, (instance, view_points) in enumerate(zip(mesh_instances, projected_xyz, strict=True)):
        screen_x = offset_x + ((view_points[:, 0] - x_min) * scale)
        screen_y = geometry_bottom - ((view_points[:, 1] - y_min) * scale)
        face_normals, face_brightness = _face_shading(view_points, instance.triangles)
        projected_instances.append(
            ProjectedMeshInstance(
                screen_points=np.column_stack((screen_x, screen_y)),
                view_points=view_points,
                triangles=instance.triangles,
                face_brightness=face_brightness,
                face_normals=face_normals,
                feature_edges=_feature_edges(instance.triangles, face_normals) if include_edges else (),
                color_rgb=_component_color(
                    index,
                    default_color=model_color,
                    count=component_count,
                    explicit_color=instance.color_rgb,
                ),
            )
        )
    return projected_instances, right, true_up


def _camera_basis(
    direction: tuple[float, float, float],
    up: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    view_normal = _normalize(np.asarray(direction, dtype=np.float64))
    up_vector = np.asarray(up, dtype=np.float64)
    projected_up = up_vector - (view_normal * float(np.dot(up_vector, view_normal)))
    if np.linalg.norm(projected_up) <= 1e-9:
        fallback_up = np.asarray((0.0, 1.0, 0.0) if abs(view_normal[1]) < 0.9 else (0.0, 0.0, 1.0))
        projected_up = fallback_up - (view_normal * float(np.dot(fallback_up, view_normal)))
    true_up = _normalize(projected_up)
    right = _normalize(np.cross(true_up, view_normal))
    return right, true_up, view_normal


def _normalize(vector: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(vector))
    if length <= 1e-9:
        raise ValueError(f"Cannot normalize near-zero vector: {vector}")
    return vector / length


def _component_color(
    index: int,
    *,
    default_color: tuple[float, float, float],
    count: int,
    explicit_color: tuple[float, float, float] | None,
) -> tuple[float, float, float]:
    if explicit_color is not None:
        return explicit_color
    if count <= 1:
        return default_color
    return FALLBACK_COMPONENT_COLORS[index % len(FALLBACK_COMPONENT_COLORS)]


def _face_shading(view_points: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tri_points = view_points[triangles]
    normals = np.cross(tri_points[:, 1] - tri_points[:, 0], tri_points[:, 2] - tri_points[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    safe_lengths = np.where(lengths > 1e-9, lengths, 1.0)
    normals = normals / safe_lengths[:, None]

    oriented = normals.copy()
    oriented[oriented[:, 2] < 0.0] *= -1.0
    light_dir = _normalize(np.asarray((-0.30, 0.45, 1.0), dtype=np.float64))
    brightness = 0.38 + (0.58 * np.clip(oriented @ light_dir, 0.0, 1.0)) + (0.08 * np.clip(oriented[:, 2], 0.0, 1.0))
    return normals, np.clip(brightness, 0.25, 1.0)


def _feature_edges(triangles: np.ndarray, face_normals: np.ndarray) -> tuple[tuple[int, int], ...]:
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for face_index, triangle in enumerate(triangles):
        a, b, c = (int(triangle[0]), int(triangle[1]), int(triangle[2]))
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (start, end) if start < end else (end, start)
            edge_faces.setdefault(edge, []).append(face_index)

    cosine_threshold = math.cos(math.radians(FEATURE_EDGE_ANGLE_DEG))
    feature_edges: list[tuple[int, int]] = []
    for edge, incident_faces in edge_faces.items():
        if len(incident_faces) == 1:
            feature_edges.append(edge)
            continue
        if len(incident_faces) > 2:
            feature_edges.append(edge)
            continue
        first, second = incident_faces
        normal_a = face_normals[first]
        normal_b = face_normals[second]
        if float(np.dot(normal_a, normal_b)) <= cosine_threshold:
            feature_edges.append(edge)
            continue
        if (normal_a[2] >= 0.0) != (normal_b[2] >= 0.0):
            feature_edges.append(edge)
    feature_edges.sort()
    return tuple(feature_edges)


def _render_scene(
    mesh_instances: list[ProjectedMeshInstance],
    *,
    width: int,
    height: int,
    background_color: tuple[float, float, float],
    edges: bool,
    axes: bool,
    right: np.ndarray,
    true_up: np.ndarray,
) -> np.ndarray:
    background_rgb = np.asarray(_rgb_u8(background_color), dtype=np.uint8)
    image = np.empty((height, width, 3), dtype=np.uint8)
    image[:, :, :] = background_rgb
    depth_buffer = np.full((height, width), -np.inf, dtype=np.float32)

    for instance in mesh_instances:
        _rasterize_faces(image, depth_buffer, instance)
    if edges:
        for instance in mesh_instances:
            _rasterize_feature_edges(image, depth_buffer, instance)
    cropped = _crop_to_content(image, background_rgb)
    if axes:
        _draw_axes_overlay(cropped, right=right, true_up=true_up, background_rgb=background_rgb)
    return cropped


def _rasterize_faces(image: np.ndarray, depth_buffer: np.ndarray, instance: ProjectedMeshInstance) -> None:
    base_color = np.asarray(_rgb_u8(instance.color_rgb), dtype=np.float32)
    triangle_count = instance.triangles.shape[0]
    for face_index in range(triangle_count):
        triangle = instance.triangles[face_index]
        indices = (int(triangle[0]), int(triangle[1]), int(triangle[2]))
        screen_triangle = instance.screen_points[list(indices)]
        view_triangle = instance.view_points[list(indices)]
        _rasterize_triangle(
            image=image,
            depth_buffer=depth_buffer,
            screen_triangle=screen_triangle,
            view_triangle=view_triangle,
            rgb=np.asarray(np.clip(np.rint(base_color * instance.face_brightness[face_index]), 0, 255), dtype=np.uint8),
        )


def _rasterize_triangle(
    *,
    image: np.ndarray,
    depth_buffer: np.ndarray,
    screen_triangle: np.ndarray,
    view_triangle: np.ndarray,
    rgb: np.ndarray,
) -> None:
    x_coords = screen_triangle[:, 0]
    y_coords = screen_triangle[:, 1]
    min_x = max(int(math.floor(float(x_coords.min()))), 0)
    max_x = min(int(math.ceil(float(x_coords.max()))), image.shape[1] - 1)
    min_y = max(int(math.floor(float(y_coords.min()))), 0)
    max_y = min(int(math.ceil(float(y_coords.max()))), image.shape[0] - 1)
    if min_x > max_x or min_y > max_y:
        return

    p0, p1, p2 = screen_triangle
    denominator = ((p1[1] - p2[1]) * (p0[0] - p2[0])) + ((p2[0] - p1[0]) * (p0[1] - p2[1]))
    if abs(float(denominator)) <= 1e-9:
        return

    x_range = np.arange(min_x, max_x + 1, dtype=np.float32) + 0.5
    y_range = np.arange(min_y, max_y + 1, dtype=np.float32) + 0.5
    grid_x, grid_y = np.meshgrid(x_range, y_range)

    w0 = (((p1[1] - p2[1]) * (grid_x - p2[0])) + ((p2[0] - p1[0]) * (grid_y - p2[1]))) / denominator
    w1 = (((p2[1] - p0[1]) * (grid_x - p2[0])) + ((p0[0] - p2[0]) * (grid_y - p2[1]))) / denominator
    w2 = 1.0 - w0 - w1

    epsilon = 1e-5
    inside = (w0 >= -epsilon) & (w1 >= -epsilon) & (w2 >= -epsilon)
    if not np.any(inside):
        return

    z0, z1, z2 = (float(view_triangle[0, 2]), float(view_triangle[1, 2]), float(view_triangle[2, 2]))
    interpolated_depth = (w0 * z0) + (w1 * z1) + (w2 * z2)
    depth_patch = depth_buffer[min_y : max_y + 1, min_x : max_x + 1]
    update_mask = inside & (interpolated_depth >= (depth_patch - 1e-4))
    if not np.any(update_mask):
        return

    image_patch = image[min_y : max_y + 1, min_x : max_x + 1]
    image_patch[update_mask] = rgb
    depth_patch[update_mask] = interpolated_depth[update_mask]


def _rasterize_feature_edges(
    image: np.ndarray,
    depth_buffer: np.ndarray,
    instance: ProjectedMeshInstance,
) -> None:
    edge_color = np.asarray(_edge_rgb(instance.color_rgb), dtype=np.uint8)
    for start, end in instance.feature_edges:
        screen_start = instance.screen_points[start]
        screen_end = instance.screen_points[end]
        depth_start = float(instance.view_points[start, 2])
        depth_end = float(instance.view_points[end, 2])
        _draw_depth_tested_segment(
            image=image,
            depth_buffer=depth_buffer,
            start=screen_start,
            end=screen_end,
            depth_start=depth_start,
            depth_end=depth_end,
            color=edge_color,
            radius_px=1,
        )


def _draw_depth_tested_segment(
    *,
    image: np.ndarray,
    depth_buffer: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    depth_start: float,
    depth_end: float,
    color: np.ndarray,
    radius_px: int,
) -> None:
    x0 = float(start[0])
    y0 = float(start[1])
    x1 = float(end[0])
    y1 = float(end[1])
    dx = x1 - x0
    dy = y1 - y0
    steps = max(1, int(math.ceil(max(abs(dx), abs(dy)))))
    offsets = _brush_offsets(radius_px)
    for step in range(steps + 1):
        t = step / steps
        xi = int(round(x0 + (dx * t)))
        yi = int(round(y0 + (dy * t)))
        depth = depth_start + ((depth_end - depth_start) * t) + 5e-4
        for ox, oy in offsets:
            px = xi + ox
            py = yi + oy
            if 0 <= px < image.shape[1] and 0 <= py < image.shape[0]:
                if depth >= (float(depth_buffer[py, px]) - 1e-3):
                    image[py, px] = color


def _brush_offsets(radius_px: int) -> tuple[tuple[int, int], ...]:
    offsets: list[tuple[int, int]] = []
    radius_squared = radius_px * radius_px
    for dy in range(-radius_px, radius_px + 1):
        for dx in range(-radius_px, radius_px + 1):
            if (dx * dx) + (dy * dy) <= radius_squared:
                offsets.append((dx, dy))
    return tuple(offsets)


def _draw_axes_overlay(
    image: np.ndarray,
    *,
    right: np.ndarray,
    true_up: np.ndarray,
    background_rgb: np.ndarray,
) -> None:
    box_size = min(AXIS_BOX_SIZE_PX, max(24, min(image.shape[0], image.shape[1]) // 4))
    placement = _best_axis_corner(image, background_rgb, box_size=box_size)
    if placement is None:
        return
    x0, y0 = placement
    x1 = min(x0 + box_size, image.shape[1])
    y1 = min(y0 + box_size, image.shape[0])
    image[y0:y1, x0:x1] = background_rgb
    origin = np.asarray((x0 + 10.0, y1 - 10.0), dtype=np.float64)
    axis_length = float(min(x1 - x0, y1 - y0) - 18)
    if axis_length <= 6.0:
        return
    basis_by_axis = (
        (np.asarray((1.0, 0.0, 0.0)), np.asarray((214, 71, 71), dtype=np.uint8)),
        (np.asarray((0.0, 1.0, 0.0)), np.asarray((62, 165, 83), dtype=np.uint8)),
        (np.asarray((0.0, 0.0, 1.0)), np.asarray((65, 111, 219), dtype=np.uint8)),
    )
    for world_axis, color in basis_by_axis:
        projected = np.asarray((float(np.dot(world_axis, right)), -float(np.dot(world_axis, true_up))))
        magnitude = float(np.linalg.norm(projected))
        if magnitude <= 1e-9:
            continue
        end = origin + ((projected / magnitude) * axis_length)
        _draw_flat_segment(
            image=image,
            start=origin,
            end=end,
            color=color,
            radius_px=1,
        )


def _best_axis_corner(image: np.ndarray, background_rgb: np.ndarray, *, box_size: int) -> tuple[int, int] | None:
    corners = (
        (0, image.shape[0] - box_size),
        (image.shape[1] - box_size, image.shape[0] - box_size),
        (0, 0),
        (image.shape[1] - box_size, 0),
    )
    best_corner: tuple[int, int] | None = None
    best_score = -1
    for x0, y0 in corners:
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(x0 + box_size, image.shape[1])
        y1 = min(y0 + box_size, image.shape[0])
        if x0 >= x1 or y0 >= y1:
            continue
        patch = image[y0:y1, x0:x1]
        background_count = int(np.count_nonzero(np.all(patch == background_rgb, axis=2)))
        if background_count > best_score:
            best_score = background_count
            best_corner = (x0, y0)
    return best_corner


def _draw_flat_segment(
    *,
    image: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    color: np.ndarray,
    radius_px: int,
) -> None:
    x0 = float(start[0])
    y0 = float(start[1])
    x1 = float(end[0])
    y1 = float(end[1])
    dx = x1 - x0
    dy = y1 - y0
    steps = max(1, int(math.ceil(max(abs(dx), abs(dy)))))
    offsets = _brush_offsets(radius_px)
    for step in range(steps + 1):
        t = step / steps
        xi = int(round(x0 + (dx * t)))
        yi = int(round(y0 + (dy * t)))
        for ox, oy in offsets:
            px = xi + ox
            py = yi + oy
            if 0 <= px < image.shape[1] and 0 <= py < image.shape[0]:
                image[py, px] = color


def _crop_to_content(image: np.ndarray, background_rgb: np.ndarray) -> np.ndarray:
    content_mask = np.any(image != background_rgb, axis=2)
    if not np.any(content_mask):
        return image
    ys, xs = np.where(content_mask)
    min_x = max(int(xs.min()) - CROP_PADDING_PX, 0)
    max_x = min(int(xs.max()) + CROP_PADDING_PX + 1, image.shape[1])
    min_y = max(int(ys.min()) - CROP_PADDING_PX, 0)
    max_y = min(int(ys.max()) + CROP_PADDING_PX + 1, image.shape[0])
    return image[min_y:max_y, min_x:max_x].copy()


def _edge_rgb(color_rgb: tuple[float, float, float]) -> tuple[int, int, int]:
    base = np.asarray(_rgb_u8(color_rgb), dtype=np.float32)
    darkened = np.clip(np.rint((base * 0.38) - 6.0), 0, 255).astype(np.uint8)
    return (int(darkened[0]), int(darkened[1]), int(darkened[2]))


def _rgb_u8(rgb: tuple[float, float, float]) -> tuple[int, int, int]:
    return tuple(int(round(max(0.0, min(1.0, float(channel))) * 255.0)) for channel in rgb)


def _write_png(image: np.ndarray, png_path: Path) -> None:
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("PNG image must be an HxWx3 RGB array")
    png_path.parent.mkdir(parents=True, exist_ok=True)

    height, width, _channels = image.shape
    scanlines = bytearray()
    for row in image:
        scanlines.append(0)
        scanlines.extend(row.astype(np.uint8, copy=False).tobytes())

    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return (
            len(data).to_bytes(4, "big")
            + payload
            + zlib.crc32(payload).to_bytes(4, "big")
        )

    png_bytes = bytearray(b"\x89PNG\r\n\x1a\n")
    png_bytes.extend(
        chunk(
            b"IHDR",
            width.to_bytes(4, "big")
            + height.to_bytes(4, "big")
            + bytes((8, 2, 0, 0, 0)),
        )
    )
    png_bytes.extend(chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9)))
    png_bytes.extend(chunk(b"IEND", b""))
    png_path.write_bytes(png_bytes)


if __name__ == "__main__":
    raise SystemExit(main())
