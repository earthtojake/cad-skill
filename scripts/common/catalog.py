from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from .metadata import GeneratorMetadata, normalize_mesh_numeric, parse_generator_metadata


REPO_ROOT = Path.cwd().resolve()
CAD_ROOT = REPO_ROOT
STEP_SUFFIXES = (".step", ".stp")
EXPLORER_ARTIFACT_FILENAMES = {
    ".glb": "model.glb",
    ".topology.json": "topology.json",
    ".topology.bin": "topology.bin",
}
IGNORED_DISCOVERY_DIR_NAMES = {
    "__pycache__",
    ".cache",
    ".eggs",
    ".env",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "build",
    "dist",
    "env",
    "node_modules",
    "site-packages",
    "venv",
}
GENERATOR_NAME_MARKERS = (b"gen_step",)


class CadSourceError(ValueError):
    pass


@dataclass(frozen=True)
class StepImportOptions:
    export_stl: bool = False
    stl_output: str | None = None
    stl_tolerance: float | None = None
    stl_angular_tolerance: float | None = None
    export_3mf: bool = False
    three_mf_output: str | None = None
    three_mf_tolerance: float | None = None
    three_mf_angular_tolerance: float | None = None
    glb_tolerance: float | None = None
    glb_angular_tolerance: float | None = None
    color: tuple[float, float, float, float] | None = None
    skip_topology: bool = False

    @property
    def has_metadata(self) -> bool:
        return any(
            (
                self.export_stl,
                self.stl_output is not None,
                self.stl_tolerance is not None,
                self.stl_angular_tolerance is not None,
                self.export_3mf,
                self.three_mf_output is not None,
                self.three_mf_tolerance is not None,
                self.three_mf_angular_tolerance is not None,
                self.glb_tolerance is not None,
                self.glb_angular_tolerance is not None,
                self.color is not None,
                self.skip_topology,
            )
        )


@dataclass(frozen=True)
class CadSource:
    source_ref: str
    cad_ref: str
    kind: str
    source_path: Path
    source: str
    origin_path: Path
    script_path: Path | None = None
    generator_metadata: GeneratorMetadata | None = None
    step_path: Path | None = None
    stl_path: Path | None = None
    three_mf_path: Path | None = None
    dxf_path: Path | None = None
    urdf_path: Path | None = None
    export_stl: bool = False
    export_3mf: bool = False
    stl_tolerance: float | None = None
    stl_angular_tolerance: float | None = None
    three_mf_tolerance: float | None = None
    three_mf_angular_tolerance: float | None = None
    glb_tolerance: float | None = None
    glb_angular_tolerance: float | None = None
    color: tuple[float, float, float, float] | None = None
    skip_topology: bool = False

    @property
    def selector_manifest_path(self) -> Path | None:
        return (
            explorer_artifact_path_for_step_path(self.step_path, ".topology.json")
            if self.step_path is not None and not self.skip_topology
            else None
        )

    @property
    def selector_binary_path(self) -> Path | None:
        return (
            explorer_artifact_path_for_step_path(self.step_path, ".topology.bin")
            if self.step_path is not None and not self.skip_topology
            else None
        )

    @property
    def glb_path(self) -> Path | None:
        return explorer_artifact_path_for_step_path(self.step_path, ".glb") if self.step_path is not None else None

    @property
    def generated_paths(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        if self.source == "generated":
            if self.step_path is not None:
                paths.append(self.step_path)
            if self.dxf_path is not None:
                paths.append(self.dxf_path)
            if self.urdf_path is not None:
                paths.append(self.urdf_path)
        if self.export_stl and self.stl_path is not None:
            paths.append(self.stl_path)
        if self.export_3mf and self.three_mf_path is not None:
            paths.append(self.three_mf_path)
        if self.glb_path is not None:
            paths.append(self.glb_path)
        if self.selector_manifest_path is not None:
            paths.append(self.selector_manifest_path)
        if self.selector_binary_path is not None:
            paths.append(self.selector_binary_path)
        return tuple(path.resolve() for path in paths)


def iter_cad_sources(root: Path | None = None) -> tuple[CadSource, ...]:
    root = CAD_ROOT if root is None else root
    resolved_root = root.resolve()
    python_sources = _iter_python_sources(resolved_root)
    generated_step_paths = {
        source.step_path.resolve()
        for source in python_sources
        if source.step_path is not None
    }
    sources = [
        *python_sources,
        *_iter_step_sources(resolved_root, excluded_step_paths=generated_step_paths),
    ]
    by_cad_ref: dict[str, CadSource] = {}
    by_source_ref: dict[str, CadSource] = {}
    by_step_path: dict[Path, CadSource] = {}
    by_generated_path: dict[Path, CadSource] = {}
    for source in sources:
        existing = by_cad_ref.get(source.cad_ref)
        if existing is not None:
            raise CadSourceError(
                "Duplicate CAD STEP ref "
                f"{source.cad_ref!r}: {_source_label(existing)} and {_source_label(source)}"
            )
        by_cad_ref[source.cad_ref] = source
        existing_source = by_source_ref.get(source.source_ref)
        if existing_source is not None:
            raise CadSourceError(
                "Duplicate CAD source ref "
                f"{source.source_ref!r}: {_source_label(existing_source)} and {_source_label(source)}"
            )
        by_source_ref[source.source_ref] = source
        if source.step_path is not None:
            existing_step = by_step_path.get(source.step_path.resolve())
            if existing_step is not None:
                raise CadSourceError(
                    "Duplicate CAD STEP source "
                    f"{_relative_to_repo(source.step_path)}: {_source_label(existing_step)} and {_source_label(source)}"
            )
            by_step_path[source.step_path.resolve()] = source
        for generated_path in source.generated_paths:
            resolved_generated_path = generated_path.resolve()
            existing_generated = by_generated_path.get(resolved_generated_path)
            if existing_generated is not None and existing_generated.source_ref != source.source_ref:
                raise CadSourceError(
                    "Duplicate CAD generated output "
                    f"{_relative_to_repo(generated_path)}: "
                    f"{_source_label(existing_generated)} and {_source_label(source)}"
                )
            by_generated_path[resolved_generated_path] = source
    return tuple(sorted(by_cad_ref.values(), key=lambda source: source.source_ref))


def source_from_path(
    path: Path,
    *,
    step_kind: str = "part",
    step_options: StepImportOptions | None = None,
) -> CadSource | None:
    resolved = path.resolve()
    if resolved.suffix.lower() == ".py":
        return _read_python_source(resolved)
    if resolved.suffix.lower() in STEP_SUFFIXES:
        return _read_step_source(resolved, kind=step_kind, options=step_options)
    return None


def source_by_cad_ref(root: Path | None = None) -> dict[str, CadSource]:
    return {source.cad_ref: source for source in iter_cad_sources(root)}


def find_source_by_cad_ref(cad_ref: str, root: Path | None = None) -> CadSource | None:
    normalized = normalize_cad_ref(cad_ref)
    return source_by_cad_ref(root).get(normalized or "")


def find_source_by_source_ref(source_ref: str, root: Path | None = None) -> CadSource | None:
    normalized = normalize_source_ref(source_ref)
    if not normalized:
        return None
    for source in iter_cad_sources(root):
        if source.source_ref == normalized:
            return source
    return None


def find_source_by_path(path: Path, root: Path | None = None) -> CadSource | None:
    resolved_path = path.resolve()
    for source in iter_cad_sources(root):
        paths = [
            source.source_path,
            source.step_path,
            source.script_path,
            source.dxf_path,
            source.urdf_path,
            *source.generated_paths,
        ]
        if any(candidate is not None and candidate.resolve() == resolved_path for candidate in paths):
            return source
    return None


def source_ref_from_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(CAD_ROOT.resolve())
    except ValueError:
        return resolved.as_posix()
    return relative.as_posix()


def cad_ref_from_step_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(CAD_ROOT.resolve())
    except ValueError:
        relative = PurePosixPath(resolved.as_posix())
    name = relative.name
    suffix = relative.suffix.lower()
    if suffix in STEP_SUFFIXES:
        return relative.with_suffix("").as_posix()
    raise CadSourceError(f"{_relative_to_repo(path)} is not a CAD STEP source")


def normalize_source_ref(raw_ref: str) -> str | None:
    normalized = str(raw_ref or "").replace("\\", "/").strip().strip("/")
    if not normalized:
        return None
    parts = normalized.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        return None
    return "/".join(parts)


def normalize_cad_ref(raw_ref: str) -> str | None:
    normalized = normalize_source_ref(raw_ref)
    if not normalized:
        return None
    suffix = PurePosixPath(normalized).suffix.lower()
    if suffix in {".py", *STEP_SUFFIXES}:
        normalized = str(PurePosixPath(normalized).with_suffix(""))
    return normalized


def artifact_path_for_step_path(step_path: Path, suffix: str) -> Path:
    return step_path.resolve().with_suffix(suffix)


def hidden_artifact_path_for_step_path(step_path: Path, suffix: str) -> Path:
    base = step_path.resolve()
    return base.with_name(f".{base.stem}{suffix}").resolve()


def explorer_directory_for_step_path(step_path: Path) -> Path:
    base = step_path.resolve()
    return (base.parent / f".{base.name}").resolve()


def explorer_artifact_path_for_step_path(step_path: Path, suffix: str) -> Path:
    base = step_path.resolve()
    artifact_name = EXPLORER_ARTIFACT_FILENAMES.get(suffix)
    if artifact_name is None:
        raise ValueError(f"Unsupported STEP explorer artifact suffix: {suffix}")
    return (explorer_directory_for_step_path(base) / artifact_name).resolve()


def _iter_python_sources(root: Path) -> tuple[CadSource, ...]:
    sources: list[CadSource] = []
    for script_path in _iter_paths(root, "*.py"):
        if not _looks_like_generator_script(script_path):
            continue
        source = _read_python_source(script_path)
        if source is not None:
            sources.append(source)
    return tuple(sources)


def _read_python_source(script_path: Path) -> CadSource | None:
    resolved_script_path = script_path.resolve()
    metadata = parse_generator_metadata(resolved_script_path)
    if metadata is None:
        return None
    if metadata.kind not in {"part", "assembly"}:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_script_path)} must define a part or assembly gen_step() entry"
        )
    if metadata.kind == "assembly" and metadata.skip_topology:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_script_path)} skip_topology is not supported for assembly entries"
        )
    if metadata.step_output is None:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_script_path)} step_output is required"
        )
    step_path = _resolve_configured_artifact_path(
        metadata.step_output,
        base_path=resolved_script_path,
        default_path=None,
        expected_suffixes=(".step",),
        field_name="step_output",
    )
    if metadata.stl_output is not None and not metadata.export_stl:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_script_path)} stl_output requires export_stl = True"
        )
    if metadata.three_mf_output is not None and not metadata.export_3mf:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_script_path)} 3mf_output requires export_3mf = True"
        )
    dxf_path = (
        _resolve_configured_artifact_path(
            _required_output(metadata.dxf_output, script_path=resolved_script_path, field_name="dxf_output"),
            base_path=resolved_script_path,
            default_path=None,
            expected_suffixes=(".dxf",),
            field_name="dxf_output",
        )
        if metadata.has_gen_dxf
        else None
    )
    urdf_path = (
        _resolve_configured_artifact_path(
            _required_output(metadata.urdf_output, script_path=resolved_script_path, field_name="urdf_output"),
            base_path=resolved_script_path,
            default_path=None,
            expected_suffixes=(".urdf",),
            field_name="urdf_output",
        )
        if metadata.has_gen_urdf
        else None
    )
    stl_path = (
        _resolve_configured_artifact_path(
            _required_output(metadata.stl_output, script_path=resolved_script_path, field_name="stl_output"),
            base_path=resolved_script_path,
            default_path=None,
            expected_suffixes=(".stl",),
            field_name="stl_output",
        )
        if metadata.export_stl
        else None
    )
    three_mf_path = (
        _resolve_configured_artifact_path(
            _required_output(metadata.three_mf_output, script_path=resolved_script_path, field_name="3mf_output"),
            base_path=resolved_script_path,
            default_path=None,
            expected_suffixes=(".3mf",),
            field_name="3mf_output",
        )
        if metadata.export_3mf
        else None
    )
    return CadSource(
        source_ref=source_ref_from_path(resolved_script_path),
        cad_ref=cad_ref_from_step_path(step_path),
        kind=metadata.kind,
        source_path=resolved_script_path,
        source="generated",
        origin_path=resolved_script_path,
        script_path=resolved_script_path,
        generator_metadata=metadata,
        step_path=step_path,
        stl_path=stl_path,
        three_mf_path=three_mf_path,
        dxf_path=dxf_path,
        urdf_path=urdf_path,
        export_stl=metadata.export_stl,
        export_3mf=metadata.export_3mf,
        stl_tolerance=metadata.stl_tolerance,
        stl_angular_tolerance=metadata.stl_angular_tolerance,
        three_mf_tolerance=metadata.three_mf_tolerance,
        three_mf_angular_tolerance=metadata.three_mf_angular_tolerance,
        glb_tolerance=metadata.glb_tolerance,
        glb_angular_tolerance=metadata.glb_angular_tolerance,
        skip_topology=metadata.skip_topology,
    )


def _iter_step_sources(root: Path, *, excluded_step_paths: set[Path]) -> tuple[CadSource, ...]:
    sources: list[CadSource] = []
    for pattern in ("*.step", "*.stp"):
        for step_path in _iter_paths(root, pattern):
            if step_path.resolve() in excluded_step_paths:
                continue
            sources.append(_read_step_source(step_path, kind="part"))
    return tuple(sorted(sources, key=lambda source: source.source_ref))


def _read_step_source(
    step_path: Path,
    *,
    kind: str,
    options: StepImportOptions | None = None,
) -> CadSource:
    resolved_step_path = step_path.resolve()
    options = options or StepImportOptions()
    if kind not in {"part", "assembly"}:
        raise CadSourceError(f"{_relative_to_repo(resolved_step_path)} kind must be 'part' or 'assembly'")
    if kind == "assembly" and options.skip_topology:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_step_path)} skip_topology is not supported for assembly entries"
        )
    if resolved_step_path.suffix.lower() not in STEP_SUFFIXES:
        raise CadSourceError(f"{_relative_to_repo(resolved_step_path)} source must end in .step or .stp")
    if not resolved_step_path.is_file():
        raise CadSourceError(
            f"{_relative_to_repo(resolved_step_path)} source does not exist"
        )
    if options.stl_output is not None and not options.export_stl:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_step_path)} stl_output requires export_stl = true"
        )
    if options.export_stl and options.stl_output is None:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_step_path)} stl_output is required when export_stl = true"
        )
    if options.three_mf_output is not None and not options.export_3mf:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_step_path)} 3mf_output requires export_3mf = true"
        )
    if options.export_3mf and options.three_mf_output is None:
        raise CadSourceError(
            f"{_relative_to_repo(resolved_step_path)} 3mf_output is required when export_3mf = true"
        )
    stl_path = (
        _resolve_configured_artifact_path(
            options.stl_output,
            base_path=resolved_step_path,
            default_path=None,
            expected_suffixes=(".stl",),
            field_name="stl_output",
        )
        if options.export_stl
        else None
    )
    three_mf_path = (
        _resolve_configured_artifact_path(
            options.three_mf_output,
            base_path=resolved_step_path,
            default_path=None,
            expected_suffixes=(".3mf",),
            field_name="3mf_output",
        )
        if options.export_3mf
        else None
    )

    cad_ref = cad_ref_from_step_path(resolved_step_path)

    return CadSource(
        source_ref=source_ref_from_path(resolved_step_path),
        cad_ref=cad_ref,
        kind=str(kind),
        source_path=resolved_step_path,
        source="imported",
        origin_path=resolved_step_path,
        step_path=resolved_step_path,
        stl_path=stl_path,
        three_mf_path=three_mf_path,
        export_stl=options.export_stl,
        export_3mf=options.export_3mf,
        stl_tolerance=normalize_step_numeric(
            options.stl_tolerance,
            base_path=resolved_step_path,
            field_name="stl_tolerance",
        ),
        stl_angular_tolerance=normalize_step_numeric(
            options.stl_angular_tolerance,
            base_path=resolved_step_path,
            field_name="stl_angular_tolerance",
        ),
        three_mf_tolerance=normalize_step_numeric(
            options.three_mf_tolerance,
            base_path=resolved_step_path,
            field_name="3mf_tolerance",
        ),
        three_mf_angular_tolerance=normalize_step_numeric(
            options.three_mf_angular_tolerance,
            base_path=resolved_step_path,
            field_name="3mf_angular_tolerance",
        ),
        glb_tolerance=normalize_step_numeric(
            options.glb_tolerance,
            base_path=resolved_step_path,
            field_name="glb_tolerance",
        ),
        glb_angular_tolerance=normalize_step_numeric(
            options.glb_angular_tolerance,
            base_path=resolved_step_path,
            field_name="glb_angular_tolerance",
        ),
        color=options.color,
        skip_topology=options.skip_topology,
    )


def _iter_paths(root: Path, pattern: str) -> tuple[Path, ...]:
    paths: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_DISCOVERY_DIR_NAMES
        )
        for filename in sorted(filenames):
            if not fnmatch(filename, pattern):
                continue
            path = (Path(current_root) / filename).resolve()
            if path.is_file():
                paths.append(path)
    return tuple(paths)


def _looks_like_generator_script(script_path: Path) -> bool:
    try:
        source_bytes = script_path.read_bytes()
    except OSError:
        return False
    return any(marker in source_bytes for marker in GENERATOR_NAME_MARKERS)


def normalize_step_numeric(raw_value: object, *, base_path: Path, field_name: str) -> float | None:
    try:
        return normalize_mesh_numeric(raw_value, field_name=field_name)
    except ValueError as exc:
        raise CadSourceError(f"{_relative_to_repo(base_path)} {exc}") from exc


def normalize_step_color(
    raw_value: object,
    *,
    base_path: Path,
    field_name: str,
) -> tuple[float, float, float, float] | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        value = raw_value.strip()
        if value.startswith("#"):
            value = value[1:]
        if len(value) not in {6, 8}:
            raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must be #RRGGBB or #RRGGBBAA")
        try:
            components = [int(value[index : index + 2], 16) / 255.0 for index in range(0, len(value), 2)]
        except ValueError as exc:
            raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must be valid hex") from exc
    elif (
        isinstance(raw_value, Sequence)
        and not isinstance(raw_value, (bytes, bytearray))
        and len(raw_value) in {3, 4}
    ):
        components = []
        for component in raw_value:
            try:
                number = float(component)
            except (TypeError, ValueError) as exc:
                raise CadSourceError(
                    f"{_relative_to_repo(base_path)} {field_name} components must be numeric"
                ) from exc
            if not 0.0 <= number <= 1.0:
                raise CadSourceError(
                    f"{_relative_to_repo(base_path)} {field_name} components must be between 0 and 1"
                )
            components.append(number)
    else:
        raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must be an RGB/RGBA array or hex string")
    if len(components) == 3:
        components.append(1.0)
    return (float(components[0]), float(components[1]), float(components[2]), float(components[3]))


def _resolve_configured_artifact_path(
    raw_value: object,
    *,
    base_path: Path,
    default_path: Path | None,
    expected_suffixes: tuple[str, ...],
    field_name: str,
) -> Path:
    if raw_value is None:
        if default_path is None:
            raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} is required")
        resolved = default_path.resolve()
    else:
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must be a non-empty string")
        value = raw_value.strip()
        if "\\" in value:
            raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must use POSIX '/' separators")
        pure = PurePosixPath(value)
        if pure.is_absolute() or any(part in {"", "."} for part in pure.parts):
            raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must be relative")
        resolved = (base_path.parent.resolve() / Path(*pure.parts)).resolve()
    suffix = resolved.suffix.lower()
    if suffix not in expected_suffixes:
        joined = " or ".join(expected_suffixes)
        raise CadSourceError(f"{_relative_to_repo(base_path)} {field_name} must end in {joined}")
    return resolved


def _required_output(raw_value: str | None, *, script_path: Path, field_name: str) -> str:
    if raw_value is None:
        raise CadSourceError(f"{_relative_to_repo(script_path)} {field_name} is required")
    return raw_value


def _source_label(source: CadSource) -> str:
    if source.script_path is not None:
        return _relative_to_repo(source.script_path)
    return _relative_to_repo(source.source_path)


def _relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()
