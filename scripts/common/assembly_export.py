from __future__ import annotations

from pathlib import Path
from typing import Sequence

from common.assembly_flatten import CatalogEntry, filesystem_entry
from common.assembly_spec import (
    REPO_ROOT,
    AssemblySpec,
    AssemblyNodeSpec,
    assembly_spec_from_payload,
    assembly_spec_children,
)
from common.catalog import find_source_by_cad_ref
from common.render import part_selector_manifest_path


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


def _step_has_assembly_artifact(step_path: Path) -> bool:
    import json

    topology_path = part_selector_manifest_path(step_path)
    try:
        payload = json.loads(topology_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    root = payload.get("assembly", {}).get("root") if isinstance(payload.get("assembly"), dict) else None
    return isinstance(root, dict) and bool(root.get("children"))


def _load_step_assembly_shape(step_path: Path, *, label: str):
    import build123d

    from common.step_scene import load_step_scene, occurrence_selector_id, scene_occurrence_shape

    scene = load_step_scene(step_path)

    def node_label(node: object) -> str:
        return str(getattr(node, "name", None) or getattr(node, "source_name", None) or occurrence_selector_id(node)).strip()

    def build_node(node: object):
        children = list(getattr(node, "children", []) or [])
        if children:
            child_shapes = [build_node(child) for child in children]
            return build123d.Compound(
                obj=child_shapes,
                children=child_shapes,
                label=node_label(node),
            )
        shape = build123d.Shape(obj=scene_occurrence_shape(scene, node))
        shape.label = node_label(node)
        return shape

    roots = [build_node(root) for root in scene.roots]
    if not roots:
        return _load_step_shape(step_path)
    return build123d.Compound(obj=roots, children=roots, label=label)


def _source_color_for_cad_ref(cad_ref: str):
    try:
        source = find_source_by_cad_ref(cad_ref)
    except Exception:
        source = None
    return source.color if source is not None else None


def _clear_shape_colors(shape: object) -> None:
    if hasattr(shape, "color"):
        shape.color = None
    for child in getattr(shape, "children", []) or []:
        _clear_shape_colors(child)


def _apply_source_color(shape: object, cad_ref: str, *, use_source_colors: bool) -> None:
    import build123d

    source_color = _source_color_for_cad_ref(cad_ref)
    if not use_source_colors:
        _clear_shape_colors(shape)
    elif source_color is not None:
        shape.color = build123d.Color(*source_color)


def _shape_for_part_entry(entry: CatalogEntry, *, label: str, use_source_colors: bool):
    step_path = entry.step_path.resolve() if entry.step_path is not None else None
    if step_path is None:
        raise RuntimeError(f"Part source {entry.source_ref} is missing STEP source path")
    shape = (
        _load_step_assembly_shape(step_path, label=label)
        if _step_has_assembly_artifact(step_path)
        else _load_step_shape(step_path)
    )
    _apply_source_color(shape, entry.cad_ref, use_source_colors=use_source_colors)
    shape.label = label
    return shape


def _build_node_shape(
    node: AssemblyNodeSpec,
    *,
    resolve_entry,
    instance_path: tuple[str, ...],
    parent_use_source_colors: bool,
    stack: tuple[str, ...],
):
    import build123d

    component_path = (*instance_path, node.instance_id) if instance_path else (node.instance_id,)
    label = _component_name(component_path)
    use_source_colors = parent_use_source_colors and node.use_source_colors

    if node.children:
        child_shapes = [
            _build_node_shape(
                child,
                resolve_entry=resolve_entry,
                instance_path=component_path,
                parent_use_source_colors=use_source_colors,
                stack=stack,
            )
            for child in node.children
        ]
        shape = build123d.Compound(obj=child_shapes, children=child_shapes, label=label)
    else:
        if node.source_path is None or node.path is None:
            raise RuntimeError(f"Assembly node {label} is missing a STEP source path")
        child_entry = resolve_entry(node.source_path)
        if child_entry is None:
            raise RuntimeError(f"Assembly node {label} references missing CAD source {node.path}")
        if child_entry.kind == "assembly":
            if child_entry.assembly_spec is None:
                raise RuntimeError(f"Assembly source {child_entry.source_ref} is missing assembly spec data")
            stack_key = child_entry.source_ref
            if stack_key in stack:
                cycle = " -> ".join((*stack, stack_key))
                raise RuntimeError(f"Assembly cycle detected: {cycle}")
            shape = _compound_from_nodes(
                assembly_spec_children(child_entry.assembly_spec),
                label=label,
                resolve_entry=resolve_entry,
                instance_path=component_path,
                parent_use_source_colors=use_source_colors,
                stack=(*stack, stack_key),
            )
        elif child_entry.kind == "part":
            shape = _shape_for_part_entry(child_entry, label=label, use_source_colors=use_source_colors)
        else:
            raise RuntimeError(f"Assembly node {label} resolved to unsupported CAD source kind: {child_entry.kind}")

    moved = shape.moved(_location_from_transform(node.transform))
    moved.label = label
    if not use_source_colors:
        _clear_shape_colors(moved)
    return moved


def _compound_from_nodes(
    nodes: Sequence[AssemblyNodeSpec],
    *,
    label: str,
    resolve_entry,
    instance_path: tuple[str, ...] = (),
    parent_use_source_colors: bool,
    stack: tuple[str, ...],
):
    import build123d

    children = [
        _build_node_shape(
            node,
            resolve_entry=resolve_entry,
            instance_path=instance_path,
            parent_use_source_colors=parent_use_source_colors,
            stack=stack,
        )
        for node in nodes
    ]
    if not children:
        raise RuntimeError(f"Assembly {label} has no resolved STEP instances")
    return build123d.Compound(
        obj=children,
        children=children,
        label=label,
    )


def build_assembly_compound(assembly_spec: AssemblySpec, *, label: str | None = None):
    root_source = filesystem_entry(assembly_spec.assembly_path)
    root_source_ref = root_source.source_ref if root_source is not None else _relative_to_repo(assembly_spec.assembly_path)
    return _compound_from_nodes(
        assembly_spec_children(assembly_spec),
        label=label or Path(assembly_spec.assembly_path).stem,
        resolve_entry=filesystem_entry,
        parent_use_source_colors=True,
        stack=(root_source_ref,),
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
