from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from cadref.analysis import selector_manifest_diff
from common.assembly_composition import (
    AssemblyCompositionError,
    build_linked_assembly_composition,
    build_native_assembly_composition,
)
from common.assembly_export import build_assembly_compound
from common.assembly_spec import REPO_ROOT, read_assembly_spec
from common.catalog import (
    CAD_ROOT,
    CadSource,
    CadSourceError,
    StepImportOptions,
    find_source_by_path,
    iter_cad_sources,
    normalize_step_color,
    normalize_cad_ref,
    normalize_source_ref,
    source_from_path,
)
from common.dxf import build_dxf_render_payload
from common.glb import export_part_glb_from_step, export_shape_glb, write_empty_glb
from common.metadata import (
    DEFAULT_3MF_ANGULAR_TOLERANCE,
    DEFAULT_3MF_TOLERANCE,
    DEFAULT_GLB_ANGULAR_TOLERANCE,
    DEFAULT_GLB_TOLERANCE,
    DEFAULT_STL_ANGULAR_TOLERANCE,
    DEFAULT_STL_TOLERANCE,
    GeneratorMetadata,
    normalize_mesh_numeric,
    resolve_3mf_settings,
    resolve_glb_settings,
    resolve_stl_settings,
)
from common.render import (
    native_component_glb_dir,
    part_glb_path,
    part_selector_binary_path,
    part_selector_manifest_path,
    relative_to_repo,
)
from common.stl import export_part_stl_from_scene
from common.threemf import export_part_3mf_from_scene
from common.validators import geometry_summary_from_manifest
from common.step_scene import (
    ColorRGBA,
    LoadedStepScene,
    SelectorOptions,
    SelectorProfile,
    extract_selectors_from_scene,
    load_step_scene,
    mesh_step_scene,
    occurrence_selector_id,
    scene_leaf_occurrences,
    scene_occurrence_prototype_shape,
    write_selector_artifacts,
)

GIT_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


@dataclass(frozen=True)
class EntrySpec:
    source_ref: str
    cad_ref: str
    kind: str
    source_path: Path
    display_name: str
    source: str
    step_path: Path | None = None
    script_path: Path | None = None
    generator_metadata: GeneratorMetadata | None = None
    dxf_path: Path | None = None
    urdf_path: Path | None = None
    stl_path: Path | None = None
    three_mf_path: Path | None = None
    export_stl: bool = False
    export_3mf: bool = False
    stl_tolerance: float = DEFAULT_STL_TOLERANCE
    stl_angular_tolerance: float = DEFAULT_STL_ANGULAR_TOLERANCE
    three_mf_tolerance: float = DEFAULT_3MF_TOLERANCE
    three_mf_angular_tolerance: float = DEFAULT_3MF_ANGULAR_TOLERANCE
    glb_tolerance: float = DEFAULT_GLB_TOLERANCE
    glb_angular_tolerance: float = DEFAULT_GLB_ANGULAR_TOLERANCE
    color: tuple[float, float, float, float] | None = None
    skip_topology: bool = False


class InlineStatusBoard:
    def __init__(self, labels: Sequence[str], *, initial_status: str) -> None:
        self._is_tty = sys.stdout.isatty()
        self._labels = list(labels)
        self._statuses = {label: initial_status for label in self._labels}
        self._rendered_rows = 0
        if self._labels and self._is_tty:
            self._render()
        else:
            for label in self._labels:
                print(self._row(label))

    def set(self, label: str, status: str) -> None:
        previous = self._statuses.get(label)
        if previous == status:
            return
        if label not in self._statuses:
            self._labels.append(label)
        self._statuses[label] = status
        if self._is_tty:
            self._render()
        else:
            print(self._row(label))

    def _row(self, label: str) -> str:
        width = max(len(item) for item in self._labels)
        return f"{label:<{width}} : {self._statuses.get(label, '')}"

    def _render(self) -> None:
        if not self._labels:
            return
        rows = [self._row(label) for label in self._labels]
        if self._rendered_rows:
            print(f"\x1b[{self._rendered_rows}F", end="")
        for row in rows:
            print(f"\x1b[2K{row}")
        if self._rendered_rows > len(rows):
            for _ in range(self._rendered_rows - len(rows)):
                print("\x1b[2K")
        self._rendered_rows = len(rows)
        sys.stdout.flush()


def _display_name_for_path(path: Path) -> str:
    return path.stem


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_discovery_root(root: Path | str) -> Path:
    candidate = Path(root)
    resolved = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"CAD discovery directory does not exist: {relative_to_repo(resolved)}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"CAD discovery path is not a directory: {relative_to_repo(resolved)}")
    return resolved


def list_entry_specs(root: Path | None = None, *, validate: bool = True) -> list[EntrySpec]:
    root = CAD_ROOT if root is None else root
    specs = [_entry_spec_from_source(source) for source in iter_cad_sources(_resolve_discovery_root(root))]
    if validate:
        _validate_part_render_output_paths(specs)
    return sorted(specs, key=lambda spec: spec.source_ref)


def _entry_spec_from_source(source: CadSource) -> EntrySpec:
    generator_metadata = source.generator_metadata
    script_path = source.script_path
    kind = source.kind
    step_path = source.step_path
    stl_settings = resolve_stl_settings(
        cad_ref=source.cad_ref,
        generator_metadata=generator_metadata,
        stl_tolerance=source.stl_tolerance,
        stl_angular_tolerance=source.stl_angular_tolerance,
    )
    three_mf_settings = resolve_3mf_settings(
        cad_ref=source.cad_ref,
        generator_metadata=generator_metadata,
        three_mf_tolerance=source.three_mf_tolerance,
        three_mf_angular_tolerance=source.three_mf_angular_tolerance,
    )
    glb_settings = resolve_glb_settings(
        cad_ref=source.cad_ref,
        generator_metadata=generator_metadata,
        glb_tolerance=source.glb_tolerance,
        glb_angular_tolerance=source.glb_angular_tolerance,
    )
    display_path = step_path if step_path is not None else source.source_path
    urdf_path = source.urdf_path

    return EntrySpec(
        source_ref=source.source_ref,
        cad_ref=source.cad_ref,
        kind=kind,
        source_path=source.source_path,
        display_name=(
            generator_metadata.display_name
            if generator_metadata is not None and generator_metadata.display_name
            else _display_name_for_path(display_path)
        ),
        source=source.source,
        step_path=step_path,
        script_path=script_path,
        generator_metadata=generator_metadata,
        dxf_path=source.dxf_path,
        urdf_path=urdf_path,
        stl_path=source.stl_path,
        three_mf_path=source.three_mf_path,
        export_stl=source.export_stl,
        export_3mf=source.export_3mf,
        stl_tolerance=stl_settings.tolerance,
        stl_angular_tolerance=stl_settings.angular_tolerance,
        three_mf_tolerance=three_mf_settings.tolerance,
        three_mf_angular_tolerance=three_mf_settings.angular_tolerance,
        glb_tolerance=glb_settings.tolerance,
        glb_angular_tolerance=glb_settings.angular_tolerance,
        color=source.color,
        skip_topology=source.skip_topology,
    )


def _read_optional_urdf_source(urdf_path: Path) -> object | None:
    if not urdf_path.exists():
        return None
    from urdf_source import UrdfSourceError, read_urdf_source

    try:
        return read_urdf_source(urdf_path)
    except (UrdfSourceError, ValueError):
        return None


def _validate_part_render_output_paths(specs: Sequence[EntrySpec]) -> None:
    sources_by_stl_path: dict[Path, str] = {}
    sources_by_3mf_path: dict[Path, str] = {}
    for spec in specs:
        if spec.kind not in {"part", "assembly"} or spec.step_path is None:
            continue
        if spec.export_stl:
            if spec.stl_path is None:
                raise ValueError(f"{spec.source_ref} export_stl is enabled but stl_path is missing")
            stl_path = spec.stl_path.resolve()
            existing_source_ref = sources_by_stl_path.get(stl_path)
            if existing_source_ref is not None and existing_source_ref != spec.source_ref:
                raise ValueError(
                    "STL output collision between "
                    f"{existing_source_ref} and {spec.source_ref}: {stl_path.relative_to(REPO_ROOT)}"
                )
            sources_by_stl_path[stl_path] = spec.source_ref
        if spec.export_3mf:
            if spec.three_mf_path is None:
                raise ValueError(f"{spec.source_ref} export_3mf is enabled but three_mf_path is missing")
            three_mf_path = spec.three_mf_path.resolve()
            existing_source_ref = sources_by_3mf_path.get(three_mf_path)
            if existing_source_ref is not None and existing_source_ref != spec.source_ref:
                raise ValueError(
                    "3MF output collision between "
                    f"{existing_source_ref} and {spec.source_ref}: {three_mf_path.relative_to(REPO_ROOT)}"
                )
            sources_by_3mf_path[three_mf_path] = spec.source_ref


def selected_entry_specs(all_specs: Sequence[EntrySpec], source_refs: Sequence[str]) -> list[EntrySpec]:
    if not source_refs:
        raise ValueError("At least one CAD target is required")
    by_source = {spec.source_ref: spec for spec in all_specs}
    by_cad_ref = {spec.cad_ref: spec for spec in all_specs}
    by_step_path = {
        spec.step_path.resolve(): spec
        for spec in all_specs
        if spec.step_path is not None
    }
    selected: list[EntrySpec] = []
    for source_ref in source_refs:
        spec = _spec_for_source_ref(source_ref, by_source=by_source, by_cad_ref=by_cad_ref, by_step_path=by_step_path)
        if spec is None:
            raise FileNotFoundError(f"CAD source not found: {source_ref}")
        selected.append(spec)
    return selected


def _spec_for_source_ref(
    raw_ref: str,
    *,
    by_source: dict[str, EntrySpec],
    by_cad_ref: dict[str, EntrySpec],
    by_step_path: dict[Path, EntrySpec],
) -> EntrySpec | None:
    source_ref = normalize_source_ref(raw_ref)
    if source_ref and source_ref in by_source:
        return by_source[source_ref]
    cad_ref = normalize_cad_ref(raw_ref)
    if cad_ref and cad_ref in by_cad_ref:
        return by_cad_ref[cad_ref]
    candidate = Path(str(raw_ref or "").strip())
    if candidate:
        resolved = candidate.resolve() if candidate.is_absolute() else (
            Path.cwd() / candidate
        )
        resolved = resolved.resolve()
        if resolved in by_step_path:
            return by_step_path[resolved]
        source = find_source_by_path(resolved)
        if source is not None:
            return by_source.get(source.source_ref)
    return None


def _selector_options_for_part(spec: EntrySpec) -> SelectorOptions:
    defaults = SelectorOptions()
    return SelectorOptions(
        linear_deflection=min(defaults.linear_deflection, spec.glb_tolerance),
        angular_deflection=min(defaults.angular_deflection, spec.glb_angular_tolerance),
        relative=defaults.relative,
        edge_deflection=defaults.edge_deflection,
        edge_deflection_ratio=defaults.edge_deflection_ratio,
        max_edge_points=defaults.max_edge_points,
        digits=defaults.digits,
    )


def _load_generator_module(script_path: Path) -> object:
    resolved_script_path = script_path.resolve()
    module_name = (
        "_cad_tool_"
        + _display_path(resolved_script_path).replace("/", "_").replace("\\", "_").replace("-", "_").replace(".", "_")
    )
    module_spec = importlib.util.spec_from_file_location(module_name, resolved_script_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Failed to load generator module from {_display_path(resolved_script_path)}")

    module = importlib.util.module_from_spec(module_spec)
    original_sys_path = list(sys.path)
    search_paths = [
        str(REPO_ROOT),
        str(CAD_ROOT),
        str(resolved_script_path.parent),
    ]
    for candidate in reversed(search_paths):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    try:
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path

    return module


def _require_envelope(
    result: object,
    *,
    script_path: Path,
    generator_name: str,
) -> dict[str, object]:
    if not isinstance(result, dict):
        raise TypeError(
            f"{_display_path(script_path)} {generator_name}() must return a generator envelope dict"
        )
    return result


def _assert_runtime_output_matches_metadata(
    envelope: dict[str, object],
    *,
    script_path: Path,
    generator_name: str,
    field_name: str,
    expected: str | None,
) -> None:
    if expected is None:
        return
    actual = envelope.get(field_name)
    if actual != expected:
        raise RuntimeError(
            f"{_display_path(script_path)} {generator_name}() envelope {field_name}={actual!r} "
            f"does not match static metadata {expected!r}"
        )


def _write_part_step_payload(envelope: dict[str, object], *, output_path: Path, script_path: Path) -> None:
    shape = envelope.get("shape")
    from build123d import Shape as Build123dShape
    from build123d import export_step as build123d_export_step

    if not isinstance(shape, Build123dShape):
        raise TypeError(
            f"{_display_path(script_path)} gen_step() envelope field 'shape' must be a build123d Shape, "
            f"got {type(shape).__name__}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not build123d_export_step(shape, output_path):
        raise RuntimeError(f"Failed to write STEP file: {output_path}")
    print(f"Wrote STEP: {output_path}")


def _write_assembly_step_payload(envelope: dict[str, object], *, output_path: Path, script_path: Path) -> None:
    from .assembly_export import export_assembly_step_from_payload

    if "instances" not in envelope and "children" not in envelope:
        raise TypeError(
            f"{_display_path(script_path)} gen_step() envelope must define 'instances' or 'children'"
        )
    export_assembly_step_from_payload(
        {key: envelope[key] for key in ("instances", "children") if key in envelope},
        assembly_path=script_path,
        output_path=output_path,
    )


def _write_dxf_payload(envelope: dict[str, object], *, output_path: Path, script_path: Path) -> None:
    document = envelope.get("document")
    saveas = getattr(document, "saveas", None)
    if not callable(saveas):
        raise TypeError(
            f"{_display_path(script_path)} gen_dxf() envelope field 'document' must be a DXF document, "
            f"got {type(document).__name__}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    saveas(str(output_path))
    print(f"Wrote DXF: {output_path}")


def _write_urdf_payload(envelope: dict[str, object], *, output_path: Path, script_path: Path) -> None:
    xml = envelope.get("xml")
    if not isinstance(xml, str):
        raise TypeError(
            f"{_display_path(script_path)} gen_urdf() envelope field 'xml' must be a string, "
            f"got {type(xml).__name__}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = xml if xml.endswith("\n") else xml + "\n"
    output_path.write_text(text, encoding="utf-8")
    print(f"Wrote URDF: {output_path}")
    _write_urdf_explorer_metadata_payload(envelope, output_path=output_path, script_path=script_path)


def _write_urdf_explorer_metadata_payload(envelope: dict[str, object], *, output_path: Path, script_path: Path) -> None:
    if "explorer_metadata" not in envelope or envelope.get("explorer_metadata") is None:
        return
    explorer_metadata = envelope.get("explorer_metadata")
    if not isinstance(explorer_metadata, dict):
        raise TypeError(
            f"{_display_path(script_path)} gen_urdf() envelope field 'explorer_metadata' must be an object, "
            f"got {type(explorer_metadata).__name__}"
        )
    explorer_dir = output_path.parent / f".{output_path.name}"
    explorer_dir.mkdir(parents=True, exist_ok=True)
    explorer_metadata_path = explorer_dir / "explorer.json"
    explorer_metadata_path.write_text(json.dumps(explorer_metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote URDF explorer metadata: {explorer_metadata_path}")


def run_script_generator(spec: EntrySpec, generator_name: str) -> None:
    if spec.script_path is None or spec.generator_metadata is None:
        raise ValueError(f"{spec.source_ref} is not a generated Python CAD source")
    module = _load_generator_module(spec.script_path)
    generator = getattr(module, generator_name, None)
    if not callable(generator):
        raise RuntimeError(f"{_display_path(spec.script_path)} does not define callable {generator_name}()")
    envelope = _require_envelope(
        generator(),
        script_path=spec.script_path,
        generator_name=generator_name,
    )

    if generator_name == "gen_step":
        _assert_runtime_output_matches_metadata(
            envelope,
            script_path=spec.script_path,
            generator_name=generator_name,
            field_name="step_output",
            expected=spec.generator_metadata.step_output,
        )
        if spec.step_path is None:
            raise RuntimeError(f"{spec.source_ref} has no configured STEP output")
        if spec.kind == "part":
            _write_part_step_payload(envelope, output_path=spec.step_path, script_path=spec.script_path)
        elif spec.kind == "assembly":
            _write_assembly_step_payload(envelope, output_path=spec.step_path, script_path=spec.script_path)
        else:
            raise RuntimeError(f"{spec.source_ref} has unsupported generated kind: {spec.kind}")
    elif generator_name == "gen_dxf":
        _assert_runtime_output_matches_metadata(
            envelope,
            script_path=spec.script_path,
            generator_name=generator_name,
            field_name="dxf_output",
            expected=spec.generator_metadata.dxf_output,
        )
        if spec.dxf_path is None:
            raise RuntimeError(f"{spec.source_ref} has no configured DXF output")
        _write_dxf_payload(envelope, output_path=spec.dxf_path, script_path=spec.script_path)
    elif generator_name == "gen_urdf":
        _assert_runtime_output_matches_metadata(
            envelope,
            script_path=spec.script_path,
            generator_name=generator_name,
            field_name="urdf_output",
            expected=spec.generator_metadata.urdf_output,
        )
        if spec.urdf_path is None:
            raise RuntimeError(f"{spec.source_ref} has no configured URDF output")
        _write_urdf_payload(envelope, output_path=spec.urdf_path, script_path=spec.script_path)
    else:
        raise RuntimeError(f"Unsupported generator: {generator_name}")

    if generator_name == "gen_step" and spec.step_path is not None and not spec.step_path.exists():
        raise RuntimeError(
            f"{_display_path(spec.script_path)} did not write {_display_path(spec.step_path)}"
        )
    if generator_name == "gen_dxf" and spec.dxf_path is not None and not spec.dxf_path.exists():
        raise RuntimeError(
            f"{_display_path(spec.script_path)} did not write {_display_path(spec.dxf_path)}"
        )
    if generator_name == "gen_urdf" and spec.urdf_path is not None and not spec.urdf_path.exists():
        raise RuntimeError(
            f"{_display_path(spec.script_path)} did not write {_display_path(spec.urdf_path)}"
        )


def run_generator(spec: EntrySpec) -> None:
    run_script_generator(spec, "gen_step")


def _is_git_lfs_pointer(step_path: Path) -> bool:
    try:
        with step_path.open("rb") as handle:
            return handle.read(len(GIT_LFS_POINTER_PREFIX)) == GIT_LFS_POINTER_PREFIX
    except OSError:
        return False


def _ensure_step_ready(step_path: Path) -> None:
    if not step_path.exists():
        raise FileNotFoundError(f"STEP file is missing: {_display_path(step_path)}")
    if _is_git_lfs_pointer(step_path):
        raise RuntimeError(
            f"{_display_path(step_path)} is a Git LFS pointer, not the real STEP file.\n"
            "Fetch Git LFS objects before generating CAD artifacts.\n"
            "For Vercel Git deployments, enable Git LFS in Project Settings > Git and redeploy."
        )


def _read_json_payload(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _report_selector_manifest_change(
    spec: EntrySpec,
    previous_manifest: dict[str, object] | None,
    next_manifest: dict[str, object],
) -> None:
    change = selector_manifest_diff(previous_manifest, next_manifest)
    if not bool(change.get("hasPrevious")):
        return
    if bool(change.get("topologyChanged")):
        print(
            f"Warning: {spec.cad_ref} selector topology changed; re-resolve @cad refs before using old face or edge selectors."
        )
        return
    if bool(change.get("geometryChanged")):
        print(
            f"Notice: {spec.cad_ref} selector geometry changed; re-check any cached geometry facts that came from older refs."
        )


def _assembly_composition_for_spec(
    spec: EntrySpec,
    *,
    entries_by_step_path: dict[Path, EntrySpec],
    topology_manifest: dict[str, object],
    scene: LoadedStepScene,
) -> dict[str, object] | None:
    if spec.kind != "assembly" or spec.step_path is None:
        return None
    if spec.source == "imported":
        return build_native_assembly_composition(
            cad_ref=spec.cad_ref,
            topology_path=part_selector_manifest_path(spec.step_path),
            topology_manifest=topology_manifest,
            component_mesh_paths=_native_component_mesh_paths(spec, scene),
        )
    if spec.source_path is None:
        return None
    assembly_spec = read_assembly_spec(spec.source_path)
    return build_linked_assembly_composition(
        cad_ref=spec.cad_ref,
        topology_path=part_selector_manifest_path(spec.step_path),
        topology_manifest=topology_manifest,
        assembly_spec=assembly_spec,
        entries_by_step_path=entries_by_step_path,
        read_assembly_spec=read_assembly_spec,
    )


def _script_step_material_colors(spec: EntrySpec) -> dict[str, ColorRGBA]:
    if spec.script_path is None:
        return {}
    try:
        module = _load_generator_module(spec.script_path)
    except Exception:
        return {}
    raw_materials = getattr(module, "URDF_MATERIALS", {})
    raw_step_materials = getattr(module, "URDF_STEP_MATERIALS", {})
    if not isinstance(raw_materials, Mapping) or not isinstance(raw_step_materials, Mapping):
        return {}
    colors: dict[str, ColorRGBA] = {}
    for raw_step_path, raw_material_name in raw_step_materials.items():
        if not isinstance(raw_step_path, str) or not isinstance(raw_material_name, str):
            continue
        raw_color = raw_materials.get(raw_material_name)
        try:
            color = normalize_step_color(raw_color, base_path=spec.source_path, field_name=f"URDF_MATERIALS.{raw_material_name}")
        except Exception:
            color = None
        if color is not None:
            colors[Path(raw_step_path).as_posix()] = color
    return colors


def _color_key(color: ColorRGBA) -> tuple[int, int, int, int]:
    return tuple(max(0, min(255, int(round(float(channel) * 255)))) for channel in color)


def _uniform_source_step_color(step_path: Path) -> ColorRGBA | None:
    try:
        scene = load_step_scene(step_path)
    except Exception:
        return None
    colors: list[ColorRGBA] = []
    colors.extend(tuple(float(value) for value in color) for color in scene.prototype_colors.values())
    for face_colors in scene.prototype_face_colors.values():
        colors.extend(tuple(float(value) for value in color) for color in face_colors.values())
    colors.extend(
        tuple(float(value) for value in node.color)
        for node in scene_leaf_occurrences(scene)
        if node.color is not None
    )
    by_key = {_color_key(color): color for color in colors}
    if len(by_key) == 1:
        return next(iter(by_key.values()))
    return None


def _assembly_3mf_occurrence_colors(
    spec: EntrySpec,
    assembly_composition: dict[str, object] | None,
) -> dict[str, ColorRGBA]:
    if spec.step_path is None or not assembly_composition:
        return {}
    root = assembly_composition.get("root")
    if not isinstance(root, Mapping):
        return {}
    topology_dir = part_selector_manifest_path(spec.step_path).parent
    step_root = spec.step_path.parent.resolve()
    script_step_colors = _script_step_material_colors(spec)
    source_color_cache: dict[Path, ColorRGBA | None] = {}
    occurrence_colors: dict[str, ColorRGBA] = {}

    def color_for_source(raw_source_path: object, *, use_source_colors: bool) -> ColorRGBA | None:
        if not use_source_colors:
            return None
        if not isinstance(raw_source_path, str) or not raw_source_path.strip():
            return None
        source_path = (topology_dir / raw_source_path).resolve()
        try:
            step_key = source_path.relative_to(step_root).as_posix()
        except ValueError:
            step_key = source_path.as_posix()
        material_color = script_step_colors.get(step_key)
        if material_color is not None:
            return material_color
        if source_path not in source_color_cache:
            source_color_cache[source_path] = _uniform_source_step_color(source_path)
        return source_color_cache[source_path]

    def collect(node: Mapping[str, object]) -> None:
        children = node.get("children")
        if isinstance(children, list) and children:
            for child in children:
                if isinstance(child, Mapping):
                    collect(child)
            return
        occurrence_id = str(node.get("occurrenceId") or node.get("id") or "").strip()
        color = color_for_source(
            node.get("sourcePath"),
            use_source_colors=node.get("useSourceColors") is not False,
        )
        if occurrence_id and color is not None:
            occurrence_colors[occurrence_id] = color

    collect(root)
    return occurrence_colors


def _generate_part_outputs(spec: EntrySpec, *, entries_by_step_path: dict[Path, EntrySpec]) -> LoadedStepScene | None:
    if spec.kind not in {"part", "assembly"} or spec.step_path is None:
        return None
    _ensure_step_ready(spec.step_path)
    manifest_path = part_selector_manifest_path(spec.step_path)
    scene = load_step_scene(spec.step_path)
    selector_options = _selector_options_for_part(spec)
    three_mf_options: SelectorOptions | None = None
    defer_3mf_export = spec.export_3mf and spec.kind == "assembly" and spec.source == "generated"
    if spec.export_stl:
        stl_options = SelectorOptions(
            linear_deflection=spec.stl_tolerance,
            angular_deflection=spec.stl_angular_tolerance,
            relative=selector_options.relative,
        )
        mesh_step_scene(
            scene,
            linear_deflection=stl_options.linear_deflection,
            angular_deflection=stl_options.angular_deflection,
            relative=stl_options.relative,
        )
        if spec.stl_path is None:
            raise RuntimeError(f"{spec.source_ref} export_stl is enabled but stl_path is missing")
        export_part_stl_from_scene(spec.step_path, scene, target_path=spec.stl_path)
    if spec.export_3mf:
        three_mf_options = SelectorOptions(
            linear_deflection=spec.three_mf_tolerance,
            angular_deflection=spec.three_mf_angular_tolerance,
            relative=selector_options.relative,
        )
        mesh_step_scene(
            scene,
            linear_deflection=three_mf_options.linear_deflection,
            angular_deflection=three_mf_options.angular_deflection,
            relative=three_mf_options.relative,
        )
        if spec.three_mf_path is None:
            raise RuntimeError(f"{spec.source_ref} export_3mf is enabled but three_mf_path is missing")
        if not defer_3mf_export:
            export_part_3mf_from_scene(spec.step_path, scene, target_path=spec.three_mf_path, color=spec.color)
    mesh_step_scene(
        scene,
        linear_deflection=selector_options.linear_deflection,
        angular_deflection=selector_options.angular_deflection,
        relative=selector_options.relative,
    )
    if spec.kind == "assembly" and spec.source == "generated" and spec.source_path is not None:
        export_shape_glb(
            build_assembly_compound(read_assembly_spec(spec.source_path), label=spec.step_path.stem),
            part_glb_path(spec.step_path),
            linear_deflection=spec.glb_tolerance,
            angular_deflection=spec.glb_angular_tolerance,
        )
    else:
        export_part_glb_from_step(
            spec.step_path,
            linear_deflection=spec.glb_tolerance,
            angular_deflection=spec.glb_angular_tolerance,
            color=spec.color,
        )
    if spec.skip_topology:
        if defer_3mf_export:
            export_part_3mf_from_scene(spec.step_path, scene, target_path=spec.three_mf_path, color=spec.color)
        return scene
    previous_manifest = _read_json_payload(manifest_path) if manifest_path.exists() else None
    bundle = extract_selectors_from_scene(
        scene,
        cad_ref=spec.cad_ref,
        profile=SelectorProfile.ARTIFACT,
        options=selector_options,
    )
    assembly_composition: dict[str, object] | None = None
    if spec.kind == "assembly":
        try:
            assembly_composition = _assembly_composition_for_spec(
                spec,
                entries_by_step_path=entries_by_step_path,
                topology_manifest=bundle.manifest,
                scene=scene,
            )
        except AssemblyCompositionError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to build assembly composition for {spec.source_ref}") from exc
        if assembly_composition is not None:
            bundle.manifest["assembly"] = assembly_composition
    if defer_3mf_export:
        if three_mf_options is None:
            raise RuntimeError(f"{spec.source_ref} export_3mf is enabled but 3MF settings are missing")
        mesh_step_scene(
            scene,
            linear_deflection=three_mf_options.linear_deflection,
            angular_deflection=three_mf_options.angular_deflection,
            relative=three_mf_options.relative,
        )
        export_part_3mf_from_scene(
            spec.step_path,
            scene,
            target_path=spec.three_mf_path,
            color=spec.color,
            occurrence_colors=_assembly_3mf_occurrence_colors(spec, assembly_composition),
        )
    write_selector_artifacts(bundle, manifest_path)
    _report_selector_manifest_change(spec, previous_manifest, bundle.manifest)
    return scene


def _native_component_mesh_paths(spec: EntrySpec, scene: LoadedStepScene) -> dict[str, Path]:
    if spec.step_path is None:
        return {}
    component_dir = native_component_glb_dir(spec.step_path)
    component_paths: dict[str, Path] = {}
    for node in scene_leaf_occurrences(scene):
        occurrence_id = occurrence_selector_id(node)
        target_path = component_dir / f"{occurrence_id}.glb"
        try:
            export_shape_glb(
                scene_occurrence_prototype_shape(scene, node),
                target_path,
                linear_deflection=spec.glb_tolerance,
                angular_deflection=spec.glb_angular_tolerance,
            )
        except RuntimeError:
            write_empty_glb(target_path)
        component_paths[occurrence_id] = target_path
    return component_paths


def _generate_step_outputs(spec: EntrySpec, *, entries_by_step_path: dict[Path, EntrySpec]) -> None:
    if spec.source == "generated":
        run_script_generator(spec, "gen_step")
    _generate_part_outputs(spec, entries_by_step_path=entries_by_step_path)


def _print_step_summaries(specs: Sequence[EntrySpec]) -> None:
    for spec in specs:
        if spec.kind in {"part", "assembly"} and spec.step_path is not None:
            manifest_path = part_selector_manifest_path(spec.step_path)
            manifest = _read_json_payload(manifest_path)
            if manifest is None:
                print(f"summary {spec.source_ref}: unavailable (missing topology manifest)")
                continue
            summary = geometry_summary_from_manifest(manifest)
            print(
                "summary "
                f"{spec.source_ref}: bbox={summary.get('bbox')} size={summary.get('size')} "
                f"faces={summary.get('faceCount')} edges={summary.get('edgeCount')}"
            )
            major_planes = summary.get("majorPlanes")
            if isinstance(major_planes, list) and major_planes:
                print(f"  majorPlanes={major_planes[:4]}")


def _print_dxf_summaries(specs: Sequence[EntrySpec]) -> None:
    for spec in specs:
        if spec.dxf_path is not None and spec.dxf_path.exists():
            try:
                payload = build_dxf_render_payload(spec.dxf_path, file_ref=_display_path(spec.dxf_path))
            except Exception:
                print(f"summary {spec.source_ref}.dxf: unavailable (invalid dxf)")
                continue
            counts = payload.get("counts") if isinstance(payload, dict) else {}
            print(
                "summary "
                f"{_display_path(spec.dxf_path)}: bounds={payload.get('bounds')} "
                f"paths={counts.get('paths')} circles={counts.get('circles')}"
            )


def _print_urdf_summaries(specs: Sequence[EntrySpec]) -> None:
    for spec in specs:
        if spec.urdf_path is not None and spec.urdf_path.exists():
            urdf_source = _read_optional_urdf_source(spec.urdf_path)
            if urdf_source is None:
                print(f"summary {spec.source_ref}.urdf: unavailable (invalid urdf)")
                continue
            print(
                "summary "
                f"{_display_path(spec.urdf_path)}: robot={urdf_source.robot_name} "
                f"links={len(urdf_source.links)} joints={len(urdf_source.joints)}"
            )


def _selected_specs_for_targets(
    targets: Sequence[str],
    *,
    direct_step_kind: str = "part",
    step_options: StepImportOptions | None = None,
) -> tuple[list[EntrySpec], list[EntrySpec]]:
    step_options = step_options or StepImportOptions()
    explicit_specs: list[EntrySpec] = []
    unresolved_targets: list[str] = []
    for target in targets:
        target_text = str(target or "").strip()
        target_path = Path(target_text)
        resolved = target_path.resolve() if target_path.is_absolute() else (Path.cwd() / target_path).resolve()
        source = (
            source_from_path(
                resolved,
                step_kind=direct_step_kind,
                step_options=step_options,
            )
            if resolved.exists()
            else None
        )
        if source is None:
            unresolved_targets.append(target)
            continue
        explicit_specs.append(_entry_spec_from_source(source))

    if step_options.has_metadata and any(spec.source == "generated" for spec in explicit_specs):
        raise ValueError("STEP import metadata flags can only be used with direct STEP/STP targets")

    if not unresolved_targets:
        return _expand_specs_with_file_dependencies(explicit_specs), explicit_specs

    unresolved = ", ".join(unresolved_targets)
    raise FileNotFoundError(
        "CAD target path not found or not a supported source file: "
        f"{unresolved}. Pass a Python generator or STEP/STP file path."
    )


def _expand_specs_with_file_dependencies(specs: Sequence[EntrySpec]) -> list[EntrySpec]:
    expanded: list[EntrySpec] = list(specs)
    seen_step_paths = {
        spec.step_path.resolve()
        for spec in expanded
        if spec.step_path is not None
    }
    seen_source_refs = {spec.source_ref for spec in expanded}
    queue = list(expanded)
    while queue:
        spec = queue.pop(0)
        if spec.kind != "assembly" or spec.source_path is None:
            continue
        try:
            assembly_spec = read_assembly_spec(spec.source_path)
        except Exception:
            continue
        for instance in assembly_spec.instances:
            if instance.source_path.resolve() in seen_step_paths:
                continue
            source = find_source_by_path(instance.source_path) or source_from_path(instance.source_path)
            if source is None:
                continue
            child_spec = _entry_spec_from_source(source)
            if child_spec.source_ref in seen_source_refs:
                continue
            expanded.append(child_spec)
            queue.append(child_spec)
            seen_source_refs.add(child_spec.source_ref)
            if child_spec.step_path is not None:
                seen_step_paths.add(child_spec.step_path.resolve())
    return expanded


def _entries_by_step_path(specs: Sequence[EntrySpec]) -> dict[Path, EntrySpec]:
    return {
        spec.step_path.resolve(): spec
        for spec in specs
        if spec.step_path is not None
    }


def _refreshed_selected_specs(selected_specs: Sequence[EntrySpec]) -> list[EntrySpec]:
    refreshed: list[EntrySpec] = []
    for spec in selected_specs:
        if spec.source == "imported":
            refreshed.append(spec)
            continue
        source_path = spec.script_path or spec.source_path
        source = source_from_path(source_path) if source_path is not None and source_path.exists() else None
        refreshed.append(_entry_spec_from_source(source) if source is not None else spec)
    return refreshed


def _validate_step_target(spec: EntrySpec, *, expected_kind: str, tool_name: str) -> None:
    if spec.kind != expected_kind:
        article = "an" if expected_kind[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
        raise ValueError(f"{tool_name} expected {article} {expected_kind} target, got {spec.kind}: {spec.source_ref}")
    if spec.step_path is None:
        raise ValueError(f"{tool_name} target has no STEP path: {spec.source_ref}")
    if spec.source == "generated":
        metadata = spec.generator_metadata
        if metadata is None or not metadata.has_gen_step:
            raise ValueError(f"{tool_name} target does not define gen_step() envelope: {spec.source_ref}")


def _validate_sidecar_target(spec: EntrySpec, *, generator_name: str, output_name: str, tool_name: str) -> None:
    metadata = spec.generator_metadata
    if spec.source != "generated" or spec.script_path is None or metadata is None:
        raise ValueError(f"{tool_name} expected a generated Python source target: {spec.source_ref}")
    has_generator = {
        "gen_dxf": metadata.has_gen_dxf,
        "gen_urdf": metadata.has_gen_urdf,
    }.get(generator_name, False)
    if not has_generator:
        raise ValueError(f"{tool_name} target does not define {generator_name}() envelope: {spec.source_ref}")
    output_path = spec.dxf_path if generator_name == "gen_dxf" else spec.urdf_path
    if output_path is None:
        raise ValueError(f"{tool_name} target has no configured {output_name}: {spec.source_ref}")


def _run_selected_specs(
    selected_specs: Sequence[EntrySpec],
    *,
    initial_status: str = "Queued",
    action_status: str = "Generating...",
    done_status: str = "Generated",
    action: Callable[[EntrySpec], None],
) -> None:
    status_board = InlineStatusBoard([spec.source_ref for spec in selected_specs], initial_status=initial_status)
    for spec in selected_specs:
        status_board.set(spec.source_ref, action_status)
        action(spec)
        status_board.set(spec.source_ref, done_status)


def generate_step_part_targets(
    targets: Sequence[str],
    *,
    summary: bool = False,
    step_options: StepImportOptions | None = None,
) -> int:
    all_specs, selected_specs = _selected_specs_for_targets(
        targets,
        direct_step_kind="part",
        step_options=step_options,
    )
    for spec in selected_specs:
        _validate_step_target(spec, expected_kind="part", tool_name="gen_step_part")
    entries_by_step_path = _entries_by_step_path(all_specs)
    _run_selected_specs(
        selected_specs,
        action=lambda spec: _generate_step_outputs(spec, entries_by_step_path=entries_by_step_path),
    )
    if summary:
        _print_step_summaries(_refreshed_selected_specs(selected_specs))
    return 0


def generate_step_assembly_targets(
    targets: Sequence[str],
    *,
    summary: bool = False,
    step_options: StepImportOptions | None = None,
) -> int:
    all_specs, selected_specs = _selected_specs_for_targets(
        targets,
        direct_step_kind="assembly",
        step_options=step_options,
    )
    for spec in selected_specs:
        _validate_step_target(spec, expected_kind="assembly", tool_name="gen_step_assembly")
    entries_by_step_path = _entries_by_step_path(all_specs)
    _run_selected_specs(
        selected_specs,
        action=lambda spec: _generate_step_outputs(spec, entries_by_step_path=entries_by_step_path),
    )
    if summary:
        _print_step_summaries(_refreshed_selected_specs(selected_specs))
    return 0


def generate_dxf_targets(targets: Sequence[str], *, summary: bool = False) -> int:
    _, selected_specs = _selected_specs_for_targets(targets)
    for spec in selected_specs:
        _validate_sidecar_target(spec, generator_name="gen_dxf", output_name="DXF output", tool_name="gen_dxf")
    _run_selected_specs(
        selected_specs,
        action=lambda spec: run_script_generator(spec, "gen_dxf"),
    )
    if summary:
        _print_dxf_summaries(_refreshed_selected_specs(selected_specs))
    return 0


def generate_urdf_targets(targets: Sequence[str], *, summary: bool = False) -> int:
    _, selected_specs = _selected_specs_for_targets(targets)
    for spec in selected_specs:
        _validate_sidecar_target(spec, generator_name="gen_urdf", output_name="URDF output", tool_name="gen_urdf")
    _run_selected_specs(
        selected_specs,
        action=lambda spec: run_script_generator(spec, "gen_urdf"),
    )
    if summary:
        _print_urdf_summaries(_refreshed_selected_specs(selected_specs))
    return 0


def _parse_color_arg(raw_value: str) -> tuple[float, float, float, float]:
    value = str(raw_value or "").strip()
    if not value:
        raise argparse.ArgumentTypeError("color must be a non-empty RGB/RGBA array or hex string")
    if "," in value:
        raw_color: object = [component.strip() for component in value.split(",")]
    else:
        raw_color = value
    try:
        color = normalize_step_color(raw_color, base_path=Path.cwd(), field_name="color")
    except CadSourceError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if color is None:
        raise argparse.ArgumentTypeError("color must be a non-empty RGB/RGBA array or hex string")
    return color


def _normalize_cli_numeric(value: object, *, field_name: str, parser: argparse.ArgumentParser) -> float | None:
    try:
        return normalize_mesh_numeric(value, field_name=field_name)
    except ValueError as exc:
        parser.error(str(exc))
    return None


def _add_step_import_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--export-stl",
        action="store_true",
        help="Export an STL sidecar for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--stl-output",
        help="Relative .stl output path for direct STEP/STP targets when --export-stl is set.",
    )
    parser.add_argument(
        "--stl-tolerance",
        type=float,
        help="Positive STL linear deflection for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--stl-angular-tolerance",
        type=float,
        help="Positive STL angular deflection for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--export-3mf",
        action="store_true",
        dest="export_3mf",
        help="Export a 3MF sidecar for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--3mf-output",
        dest="three_mf_output",
        help="Relative .3mf output path for direct STEP/STP targets when --export-3mf is set.",
    )
    parser.add_argument(
        "--3mf-tolerance",
        type=float,
        dest="three_mf_tolerance",
        help="Positive 3MF linear deflection for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--3mf-angular-tolerance",
        type=float,
        dest="three_mf_angular_tolerance",
        help="Positive 3MF angular deflection for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--glb-tolerance",
        type=float,
        help="Positive GLB linear deflection for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--glb-angular-tolerance",
        type=float,
        help="Positive GLB angular deflection for direct STEP/STP targets.",
    )
    parser.add_argument(
        "--color",
        type=_parse_color_arg,
        help="RGB/RGBA color as comma-separated 0..1 components or #RRGGBB/#RRGGBBAA.",
    )
    parser.add_argument(
        "--skip-topology",
        action="store_true",
        help="Emit GLB without selector topology sidecars for direct STEP/STP part targets.",
    )


def _step_import_options_from_args(
    args: argparse.Namespace,
    *,
    parser: argparse.ArgumentParser,
) -> StepImportOptions:
    return StepImportOptions(
        export_stl=bool(args.export_stl),
        stl_output=args.stl_output,
        stl_tolerance=_normalize_cli_numeric(
            args.stl_tolerance,
            field_name="stl_tolerance",
            parser=parser,
        ),
        stl_angular_tolerance=_normalize_cli_numeric(
            args.stl_angular_tolerance,
            field_name="stl_angular_tolerance",
            parser=parser,
        ),
        export_3mf=bool(args.export_3mf),
        three_mf_output=args.three_mf_output,
        three_mf_tolerance=_normalize_cli_numeric(
            args.three_mf_tolerance,
            field_name="3mf_tolerance",
            parser=parser,
        ),
        three_mf_angular_tolerance=_normalize_cli_numeric(
            args.three_mf_angular_tolerance,
            field_name="3mf_angular_tolerance",
            parser=parser,
        ),
        glb_tolerance=_normalize_cli_numeric(
            args.glb_tolerance,
            field_name="glb_tolerance",
            parser=parser,
        ),
        glb_angular_tolerance=_normalize_cli_numeric(
            args.glb_angular_tolerance,
            field_name="glb_angular_tolerance",
            parser=parser,
        ),
        color=args.color,
        skip_topology=bool(args.skip_topology),
    )


def run_tool_cli(
    argv: Sequence[str] | None,
    *,
    prog: str,
    description: str,
    action: Callable[..., int],
    step_kind: str | None = None,
    target_help: str | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument(
        "targets",
        nargs="+",
        help=target_help or "Explicit Python generator or STEP/STP file path to generate.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a compact summary for generated outputs.",
    )
    if step_kind is not None:
        _add_step_import_arguments(parser)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if step_kind is None:
        return action(args.targets, summary=args.summary)
    step_options = _step_import_options_from_args(args, parser=parser)
    if step_kind == "assembly" and step_options.skip_topology:
        parser.error("skip_topology is not supported for assembly entries")
    return action(args.targets, summary=args.summary, step_options=step_options)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "The shared generator entrypoint has been removed. Use gen_step_part, "
            "gen_step_assembly, gen_dxf, or gen_urdf with explicit targets."
        )
    )
    parser.parse_args(list(argv) if argv is not None else None)
    parser.error(
        "common is a library, not a generator CLI. "
        "Run gen_step_part, gen_step_assembly, gen_dxf, or gen_urdf."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
