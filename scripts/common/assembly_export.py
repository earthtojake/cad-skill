from __future__ import annotations

from pathlib import Path

from common.assembly_flatten import CatalogEntry, flatten_entry, filesystem_entry
from common.assembly_spec import (
    REPO_ROOT,
    AssemblySpec,
    assembly_spec_from_payload,
)
from common.catalog import find_source_by_cad_ref


GIT_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


def _relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_git_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(GIT_LFS_POINTER_PREFIX)) == GIT_LFS_POINTER_PREFIX
    except OSError:
        return False


def _location_from_transform(transform: tuple[float, ...]):
    import build123d
    from OCP.gp import gp_Trsf

    trsf = gp_Trsf()
    trsf.SetValues(
        transform[0],
        transform[1],
        transform[2],
        transform[3],
        transform[4],
        transform[5],
        transform[6],
        transform[7],
        transform[8],
        transform[9],
        transform[10],
        transform[11],
    )
    return build123d.Location(trsf)


def _component_name(instance_path: tuple[str, ...]) -> str:
    return "__".join(instance_path) or "root"


def _load_step_shape(step_path: Path):
    if not step_path.exists():
        raise FileNotFoundError(f"Referenced STEP file is missing: {_relative_to_repo(step_path)}")
    if _is_git_lfs_pointer(step_path):
        raise RuntimeError(f"Referenced STEP file is a Git LFS pointer: {_relative_to_repo(step_path)}")

    import build123d

    try:
        return build123d.import_step(step_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to load referenced STEP file: {_relative_to_repo(step_path)}") from exc


def _source_color_for_cad_ref(cad_ref: str):
    try:
        source = find_source_by_cad_ref(cad_ref)
    except Exception:
        source = None
    return source.color if source is not None else None


def build_assembly_compound(assembly_spec: AssemblySpec, *, label: str | None = None):
    import build123d

    root_source = filesystem_entry(assembly_spec.assembly_path)
    root_cad_ref = root_source.cad_ref if root_source is not None else assembly_spec.assembly_path.stem
    root_source_ref = root_source.source_ref if root_source is not None else _relative_to_repo(assembly_spec.assembly_path)
    root_entry = CatalogEntry(
        cad_ref=root_cad_ref,
        source_ref=root_source_ref,
        kind="assembly",
        source_path=assembly_spec.assembly_path,
        assembly_spec=assembly_spec,
    )
    resolved_parts = flatten_entry(root_entry, resolve_entry=filesystem_entry)
    if not resolved_parts:
        raise RuntimeError(f"{_relative_to_repo(assembly_spec.assembly_path)} has no resolved STEP instances")

    children: list[build123d.Shape] = []
    for resolved_part in resolved_parts:
        step_path = resolved_part.step_path.resolve()
        shape = _load_step_shape(step_path)
        source_color = _source_color_for_cad_ref(resolved_part.cad_ref)
        if source_color is not None:
            shape.color = build123d.Color(*source_color)
        child = shape.moved(_location_from_transform(resolved_part.transform))
        if source_color is not None:
            child.color = build123d.Color(*source_color)
        child.label = _component_name(resolved_part.instance_path)
        children.append(child)

    return build123d.Compound(
        obj=children,
        children=children,
        label=label or Path(assembly_spec.assembly_path).stem,
    )


def export_assembly_step(assembly_spec: AssemblySpec, output_path: Path) -> Path:
    import build123d

    assembly = build_assembly_compound(assembly_spec, label=output_path.stem)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        success = build123d.export_step(assembly, output_path)
    except Exception as exc:
        raise RuntimeError(f"Failed to write assembly STEP file: {_relative_to_repo(output_path)}") from exc
    if not success:
        raise RuntimeError(f"Failed to write assembly STEP file: {_relative_to_repo(output_path)}")
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"Assembly STEP export did not create {_relative_to_repo(output_path)}")
    print(f"Wrote STEP: {output_path}")
    return output_path


def export_assembly_step_from_payload(
    payload: object,
    *,
    assembly_path: Path,
    output_path: Path,
) -> Path:
    return export_assembly_step(
        assembly_spec_from_payload(assembly_path, payload),
        output_path,
    )
