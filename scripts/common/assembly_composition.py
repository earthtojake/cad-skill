from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from common.assembly_spec import (
    IDENTITY_TRANSFORM,
    AssemblySpec,
    multiply_transforms,
)
from common.render import (
    part_glb_path,
    part_selector_manifest_path,
    relative_to_repo,
    sha256_file,
)


ASSEMBLY_COMPOSITION_SCHEMA_VERSION = 1
TOPOLOGY_COUNT_KEYS = ("shapeCount", "faceCount", "edgeCount", "vertexCount")


class AssemblyCompositionError(ValueError):
    pass


def component_name(instance_path: Sequence[str]) -> str:
    return "__".join(str(part) for part in instance_path if str(part)) or "root"


def _relative_to_topology(topology_path: Path, target_path: Path) -> str:
    return os.path.relpath(target_path.resolve(), start=topology_path.resolve().parent).replace(os.sep, "/")


def _versioned_relative_url(topology_path: Path, target_path: Path, content_hash: str) -> str:
    suffix = f"?v={content_hash}" if content_hash else ""
    return f"{_relative_to_topology(topology_path, target_path)}{suffix}"


def build_linked_assembly_composition(
    *,
    cad_ref: str,
    topology_path: Path,
    topology_manifest: dict[str, Any],
    assembly_spec: AssemblySpec,
    entries_by_step_path: Mapping[Path, object],
    read_assembly_spec: Callable[[Path], AssemblySpec],
) -> dict[str, Any]:
    occurrences = _rows(topology_manifest, "occurrences", "occurrenceColumns")
    if not occurrences:
        raise AssemblyCompositionError(f"Assembly topology has no occurrences: {cad_ref}")
    component_occurrences = _component_occurrences(topology_manifest)
    root_occurrence = occurrences[0]
    children = [
        _linked_instance_node(
            cad_ref=cad_ref,
            topology_path=topology_path,
            instance=instance,
            instance_path=(instance.instance_id,),
            parent_world_transform=IDENTITY_TRANSFORM,
            component_occurrences=component_occurrences,
            entries_by_step_path=entries_by_step_path,
            read_assembly_spec=read_assembly_spec,
            stack=(assembly_spec.assembly_path.resolve().as_posix(),),
        )
        for instance in assembly_spec.instances
    ]
    if not children:
        raise AssemblyCompositionError(f"Assembly {cad_ref} has no component instances")
    return {
        "schemaVersion": ASSEMBLY_COMPOSITION_SCHEMA_VERSION,
        "mode": "linked",
        "root": _assembly_root_node(cad_ref, root_occurrence, children),
    }


def build_native_assembly_composition(
    *,
    cad_ref: str,
    topology_path: Path,
    topology_manifest: dict[str, Any],
    component_mesh_paths: Mapping[str, Path],
) -> dict[str, Any]:
    occurrences = _rows(topology_manifest, "occurrences", "occurrenceColumns")
    if not occurrences:
        raise AssemblyCompositionError(f"Assembly topology has no occurrences: {cad_ref}")
    by_id = {
        str(row.get("id") or "").strip(): row
        for row in occurrences
        if str(row.get("id") or "").strip()
    }
    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    top_level: list[dict[str, Any]] = []
    for row in occurrences:
        parent_id = str(row.get("parentId") or "").strip()
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(row)
        else:
            top_level.append(row)

    root_occurrence = top_level[0] if len(top_level) == 1 else occurrences[0]
    root_children = top_level
    if len(top_level) == 1 and not children_by_parent.get(str(top_level[0].get("id") or "").strip()):
        root_children = top_level
    elif len(top_level) == 1:
        root_children = children_by_parent.get(str(top_level[0].get("id") or "").strip(), [])

    children = [
        _native_occurrence_node(
            row,
            children_by_parent=children_by_parent,
            component_mesh_paths=component_mesh_paths,
            topology_path=topology_path,
            parent_world_transform=IDENTITY_TRANSFORM,
        )
        for row in root_children
    ]
    if not children:
        row = root_occurrence
        children = [
            _native_part_node(
                row,
                component_mesh_paths=component_mesh_paths,
                topology_path=topology_path,
                parent_world_transform=IDENTITY_TRANSFORM,
            )
        ]
    return {
        "schemaVersion": ASSEMBLY_COMPOSITION_SCHEMA_VERSION,
        "mode": "native",
        "root": _assembly_root_node(cad_ref, root_occurrence, children),
    }


def _linked_instance_node(
    *,
    cad_ref: str,
    topology_path: Path,
    instance: object,
    instance_path: tuple[str, ...],
    parent_world_transform: tuple[float, ...],
    component_occurrences: Sequence[dict[str, Any]],
    entries_by_step_path: Mapping[Path, object],
    read_assembly_spec: Callable[[Path], AssemblySpec],
    stack: tuple[str, ...],
) -> dict[str, Any]:
    instance_source_path = Path(getattr(instance, "source_path")).resolve()
    source_spec = entries_by_step_path.get(instance_source_path)
    if source_spec is None:
        raise AssemblyCompositionError(
            f"{cad_ref} assembly component {component_name(instance_path)} references missing CAD source {instance.path}"
        )
    child_kind = str(getattr(source_spec, "kind", "") or "")
    instance_transform = tuple(float(value) for value in getattr(instance, "transform"))
    world_transform = multiply_transforms(parent_world_transform, instance_transform)
    source_step_path = getattr(source_spec, "step_path", None)
    source_path = _relative_to_topology(topology_path, Path(source_step_path)) if source_step_path is not None else instance.path
    display_name = str(getattr(instance, "name", "") or instance_path[-1] or Path(instance.path).stem).strip()

    if child_kind == "part":
        occurrence = _find_occurrence_by_component_name(
            component_name(instance_path),
            component_occurrences,
            cad_ref,
        )
        if occurrence is None:
            raise AssemblyCompositionError(
                f"{cad_ref} assembly topology is missing occurrence {component_name(instance_path)!r}"
            )
        if source_step_path is None:
            raise AssemblyCompositionError(f"{cad_ref} component {component_name(instance_path)} is missing STEP source")
        source_counts = _source_topology_counts(part_selector_manifest_path(Path(source_step_path)))
        occurrence_counts = _occurrence_topology_counts(occurrence)
        if source_counts != occurrence_counts:
            raise AssemblyCompositionError(
                f"{cad_ref} assembly occurrence {occurrence.get('id')!r} count mismatch for "
                f"{source_path}: source={source_counts} assembly={occurrence_counts}"
            )
        occurrence_id = str(occurrence.get("id") or "").strip()
        glb_path = part_glb_path(Path(source_step_path))
        glb_hash = sha256_file(glb_path) if glb_path.exists() else ""
        return {
            "id": occurrence_id,
            "occurrenceId": occurrence_id,
            "nodeType": "part",
            "displayName": display_name,
            "sourceKind": "catalog",
            "sourcePath": source_path,
            "instancePath": ".".join(instance_path),
            "localTransform": _transform_list(instance_transform),
            "worldTransform": _transform_list(tuple(float(value) for value in occurrence.get("transform") or world_transform)),
            "bbox": occurrence.get("bbox"),
            "topologyCounts": _public_topology_counts(occurrence_counts),
            "assets": {
                "glb": {
                    "url": _versioned_relative_url(topology_path, glb_path, glb_hash) if glb_hash else "",
                    "hash": glb_hash,
                }
            },
            "children": [],
        }

    if child_kind != "assembly":
        raise AssemblyCompositionError(
            f"{cad_ref} component {component_name(instance_path)} must resolve to a STEP part or assembly source"
        )
    stack_key = instance_source_path.as_posix()
    if stack_key in stack:
        cycle = " -> ".join((*stack, stack_key))
        raise AssemblyCompositionError(f"Assembly cycle detected: {cycle}")
    source_path = getattr(source_spec, "source_path", None)
    script_path = getattr(source_spec, "script_path", None)
    if source_path is None or script_path is None:
        raise AssemblyCompositionError(
            f"{cad_ref} nested assembly {instance.path} must be a generated assembly source"
        )
    child_spec = read_assembly_spec(Path(source_path))
    children = [
        _linked_instance_node(
            cad_ref=cad_ref,
            topology_path=topology_path,
            instance=child_instance,
            instance_path=(*instance_path, child_instance.instance_id),
            parent_world_transform=world_transform,
            component_occurrences=component_occurrences,
            entries_by_step_path=entries_by_step_path,
            read_assembly_spec=read_assembly_spec,
            stack=(*stack, stack_key),
        )
        for child_instance in child_spec.instances
    ]
    return {
        "id": component_name(instance_path),
        "occurrenceId": component_name(instance_path),
        "nodeType": "assembly",
        "displayName": display_name,
        "sourceKind": "catalog",
        "sourcePath": _relative_to_topology(topology_path, Path(source_step_path)) if source_step_path is not None else instance.path,
        "instancePath": ".".join(instance_path),
        "localTransform": _transform_list(instance_transform),
        "worldTransform": _transform_list(world_transform),
        "bbox": _merge_bbox([child.get("bbox") for child in children]),
        "topologyCounts": _sum_public_counts(children),
        "children": children,
    }


def _native_occurrence_node(
    row: dict[str, Any],
    *,
    children_by_parent: Mapping[str, list[dict[str, Any]]],
    component_mesh_paths: Mapping[str, Path],
    topology_path: Path,
    parent_world_transform: tuple[float, ...],
) -> dict[str, Any]:
    row_id = str(row.get("id") or "").strip()
    children = children_by_parent.get(row_id, [])
    if not children:
        return _native_part_node(
            row,
            component_mesh_paths=component_mesh_paths,
            topology_path=topology_path,
            parent_world_transform=parent_world_transform,
        )
    world_transform = _row_transform(row)
    child_nodes = [
        _native_occurrence_node(
            child,
            children_by_parent=children_by_parent,
            component_mesh_paths=component_mesh_paths,
            topology_path=topology_path,
            parent_world_transform=world_transform,
        )
        for child in children
    ]
    return {
        "id": row_id,
        "occurrenceId": row_id,
        "nodeType": "assembly",
        "displayName": _occurrence_display_name(row),
        "sourceKind": "native",
        "instancePath": str(row.get("path") or row_id),
        "localTransform": _transform_list(_relative_transform(parent_world_transform, world_transform)),
        "worldTransform": _transform_list(world_transform),
        "bbox": row.get("bbox") or _merge_bbox([child.get("bbox") for child in child_nodes]),
        "topologyCounts": _public_topology_counts(_occurrence_topology_counts(row)),
        "children": child_nodes,
    }


def _native_part_node(
    row: dict[str, Any],
    *,
    component_mesh_paths: Mapping[str, Path],
    topology_path: Path,
    parent_world_transform: tuple[float, ...],
) -> dict[str, Any]:
    occurrence_id = str(row.get("id") or "").strip()
    if not occurrence_id:
        raise AssemblyCompositionError("Native assembly occurrence is missing an id")
    mesh_path = component_mesh_paths.get(occurrence_id)
    if mesh_path is None:
        raise AssemblyCompositionError(f"Native assembly component {occurrence_id} is missing a mesh asset")
    mesh_hash = sha256_file(mesh_path) if mesh_path.exists() else ""
    world_transform = _row_transform(row)
    return {
        "id": occurrence_id,
        "occurrenceId": occurrence_id,
        "nodeType": "part",
        "displayName": _occurrence_display_name(row),
        "sourceKind": "native",
        "instancePath": str(row.get("path") or occurrence_id),
        "localTransform": _transform_list(_relative_transform(parent_world_transform, world_transform)),
        "worldTransform": _transform_list(world_transform),
        "bbox": row.get("bbox"),
        "topologyCounts": _public_topology_counts(_occurrence_topology_counts(row)),
        "assets": {
            "glb": {
                "url": _versioned_relative_url(topology_path, mesh_path, mesh_hash) if mesh_hash else "",
                "hash": mesh_hash,
            }
        },
        "children": [],
    }


def _assembly_root_node(cad_ref: str, root_occurrence: dict[str, Any], children: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts = _sum_public_counts(children) or _public_topology_counts(_occurrence_topology_counts(root_occurrence))
    return {
        "id": "root",
        "occurrenceId": str(root_occurrence.get("id") or "root").strip() or "root",
        "nodeType": "assembly",
        "displayName": _root_display_name(cad_ref, root_occurrence),
        "sourceKind": "catalog",
        "instancePath": "",
        "localTransform": _transform_list(IDENTITY_TRANSFORM),
        "worldTransform": _transform_list(IDENTITY_TRANSFORM),
        "bbox": root_occurrence.get("bbox") or _merge_bbox([child.get("bbox") for child in children]),
        "topologyCounts": counts,
        "children": list(children),
    }


def _root_display_name(cad_ref: str, root_occurrence: Mapping[str, Any]) -> str:
    display_name = str(root_occurrence.get("name") or "").strip()
    if not display_name or display_name.lower() == "root":
        return cad_ref.rsplit("/", 1)[-1]
    return display_name


def _rows(manifest: dict[str, Any], row_key: str, columns_key: str) -> list[dict[str, Any]]:
    columns = manifest.get("tables", {}).get(columns_key)
    rows = manifest.get(row_key)
    if not isinstance(columns, list) or not isinstance(rows, list):
        return []
    output: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, list):
            output.append({str(column): row[index] if index < len(row) else None for index, column in enumerate(columns)})
    return output


def _component_occurrences(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    occurrences = _rows(manifest, "occurrences", "occurrenceColumns")
    parent_ids = {
        str(row.get("parentId") or "").strip()
        for row in occurrences
        if str(row.get("parentId") or "").strip()
    }
    candidate_occurrences = [
        row
        for row in occurrences
        if str(row.get("parentId") or "").strip() and int(row.get("shapeCount") or 0) > 0
    ]
    if candidate_occurrences:
        return candidate_occurrences

    leaf_occurrences = [
        row
        for row in occurrences
        if str(row.get("id") or "").strip() not in parent_ids and int(row.get("shapeCount") or 0) > 0
    ]
    if not leaf_occurrences:
        leaf_occurrences = [
            row
            for row in occurrences
            if int(row.get("shapeCount") or 0) > 0
        ]
    if not leaf_occurrences:
        raise AssemblyCompositionError("Assembly topology has no component occurrences")
    return leaf_occurrences


def _find_occurrence_by_component_name(
    component: str,
    occurrences: Sequence[dict[str, Any]],
    cad_ref: str,
) -> dict[str, Any] | None:
    matches = []
    for occurrence in occurrences:
        names = {
            str(occurrence.get("name") or "").strip(),
            str(occurrence.get("sourceName") or "").strip(),
        }
        if component in names:
            matches.append(occurrence)
    if len(matches) > 1:
        raise AssemblyCompositionError(
            f"Assembly topology has duplicate component occurrence name for {cad_ref}: {component}"
        )
    return matches[0] if matches else None


def _read_json(path: Path) -> dict[str, Any]:
    import json

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssemblyCompositionError(f"Failed to read JSON: {relative_to_repo(path)}") from exc
    if not isinstance(payload, dict):
        raise AssemblyCompositionError(f"Expected JSON object: {relative_to_repo(path)}")
    return payload


def _source_topology_counts(topology_manifest_path: Path) -> dict[str, int]:
    manifest = _read_json(topology_manifest_path)
    stats = manifest.get("stats")
    if not isinstance(stats, dict):
        raise AssemblyCompositionError(
            f"Source topology is missing stats: {relative_to_repo(topology_manifest_path)}"
        )
    counts = {
        "shapes": int(stats.get("shapeCount") or 0),
        "faces": int(stats.get("faceCount") or 0),
        "edges": int(stats.get("edgeCount") or 0),
        "vertices": int(stats.get("vertexCount") or 0),
    }
    if any(value <= 0 for value in counts.values()):
        raise AssemblyCompositionError(
            f"Source topology has invalid counts in {relative_to_repo(topology_manifest_path)}: {counts}"
        )
    return counts


def _occurrence_topology_counts(occurrence: Mapping[str, Any]) -> dict[str, int]:
    return {
        "shapes": int(occurrence.get("shapeCount") or 0),
        "faces": int(occurrence.get("faceCount") or 0),
        "edges": int(occurrence.get("edgeCount") or 0),
        "vertices": int(occurrence.get("vertexCount") or 0),
    }


def _public_topology_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {
        "shapes": int(counts.get("shapes") or 0),
        "faces": int(counts.get("faces") or 0),
        "edges": int(counts.get("edges") or 0),
        "vertices": int(counts.get("vertices") or 0),
    }


def _sum_public_counts(children: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    total = {"shapes": 0, "faces": 0, "edges": 0, "vertices": 0}
    for child in children:
        counts = child.get("topologyCounts")
        if not isinstance(counts, Mapping):
            continue
        for key in total:
            total[key] += int(counts.get(key) or 0)
    return total


def _occurrence_display_name(row: Mapping[str, Any]) -> str:
    return str(row.get("name") or row.get("sourceName") or row.get("path") or row.get("id") or "component").strip()


def _row_transform(row: Mapping[str, Any]) -> tuple[float, ...]:
    raw_transform = row.get("transform")
    if not isinstance(raw_transform, list) or len(raw_transform) != 16:
        return IDENTITY_TRANSFORM
    return tuple(float(value) for value in raw_transform)


def _transform_list(transform: Sequence[float]) -> list[float]:
    return [float(value) for value in transform]


def _merge_bbox(boxes: Sequence[Any]) -> dict[str, Any]:
    valid_boxes = [
        box
        for box in boxes
        if isinstance(box, Mapping) and isinstance(box.get("min"), list) and isinstance(box.get("max"), list)
    ]
    if not valid_boxes:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
    mins = [list(box["min"]) for box in valid_boxes]
    maxs = [list(box["max"]) for box in valid_boxes]
    return {
        "min": [min(float(point[index]) for point in mins) for index in range(3)],
        "max": [max(float(point[index]) for point in maxs) for index in range(3)],
    }


def _relative_transform(parent_world_transform: tuple[float, ...], world_transform: tuple[float, ...]) -> tuple[float, ...]:
    return multiply_transforms(_invert_affine_transform(parent_world_transform), world_transform)


def _invert_affine_transform(transform: tuple[float, ...]) -> tuple[float, ...]:
    a, b, c, tx, d, e, f, ty, g, h, i, tz = transform[:12]
    det = (
        a * (e * i - f * h)
        - b * (d * i - f * g)
        + c * (d * h - e * g)
    )
    if abs(det) <= 1e-12:
        return IDENTITY_TRANSFORM
    inv_det = 1.0 / det
    r00 = (e * i - f * h) * inv_det
    r01 = (c * h - b * i) * inv_det
    r02 = (b * f - c * e) * inv_det
    r10 = (f * g - d * i) * inv_det
    r11 = (a * i - c * g) * inv_det
    r12 = (c * d - a * f) * inv_det
    r20 = (d * h - e * g) * inv_det
    r21 = (b * g - a * h) * inv_det
    r22 = (a * e - b * d) * inv_det
    return (
        r00,
        r01,
        r02,
        -((r00 * tx) + (r01 * ty) + (r02 * tz)),
        r10,
        r11,
        r12,
        -((r10 * tx) + (r11 * ty) + (r12 * tz)),
        r20,
        r21,
        r22,
        -((r20 * tx) + (r21 * ty) + (r22 * tz)),
        0.0,
        0.0,
        0.0,
        1.0,
    )
