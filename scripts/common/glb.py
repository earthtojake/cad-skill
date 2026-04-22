from __future__ import annotations

from pathlib import Path

import build123d

from common.render import REPO_ROOT, part_glb_path
from common.step_scene import LoadedStepScene, scene_export_shape


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def export_part_glb_from_step(
    step_path: Path,
    *,
    linear_deflection: float,
    angular_deflection: float,
    color: tuple[float, float, float, float] | None = None,
) -> Path:
    target_path = part_glb_path(step_path)
    shape = build123d.import_step(step_path)
    if color is not None:
        shape.color = build123d.Color(*color)
    return export_shape_glb(
        shape,
        target_path,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
    )


def export_part_glb_from_scene(
    step_path: Path,
    scene: LoadedStepScene,
    *,
    linear_deflection: float,
    angular_deflection: float,
    color: tuple[float, float, float, float] | None = None,
) -> Path:
    target_path = part_glb_path(step_path)
    shape = scene_export_shape(scene)
    if color is not None:
        shape = build123d.Shape(obj=shape)
        shape.color = build123d.Color(*color)
    return export_shape_glb(
        shape,
        target_path,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
    )


def export_shape_glb(
    shape: object,
    target_path: Path,
    *,
    linear_deflection: float,
    angular_deflection: float,
) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    export_shape = shape if isinstance(shape, build123d.Shape) else build123d.Shape(obj=shape)
    ok = build123d.export_gltf(
        export_shape,
        target_path,
        binary=True,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
    )
    if not ok:
        raise RuntimeError(f"Failed to write GLB output: {_display_path(target_path)}")
    return target_path


def write_empty_glb(target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    json_chunk = b'{"asset":{"version":"2.0"},"scenes":[{"nodes":[]}],"scene":0,"nodes":[]}'
    json_chunk += b" " * ((4 - (len(json_chunk) % 4)) % 4)
    chunk_header = len(json_chunk).to_bytes(4, "little") + b"JSON"
    payload = b"glTF" + (2).to_bytes(4, "little") + (12 + len(chunk_header) + len(json_chunk)).to_bytes(4, "little")
    target_path.write_bytes(payload + chunk_header + json_chunk)
    return target_path
