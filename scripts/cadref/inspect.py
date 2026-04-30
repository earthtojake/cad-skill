from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common.assembly_spec import REPO_ROOT, find_step_path, resolve_cad_source_path
from common.step_scene import SelectorProfile, extract_selectors

from . import analysis
from . import lookup, syntax


@dataclass
class EntryContext:
    cad_path: str
    kind: str
    source_path: Path
    step_path: Path | None
    manifest: dict[str, object]
    selector_index: lookup.SelectorIndex | None


class CadRefError(RuntimeError):
    pass


def inspect_cad_refs(
    text: str,
    *,
    detail: bool = False,
    include_topology: bool = False,
    facts: bool = False,
) -> dict[str, object]:
    parsed_tokens = syntax.parse_cad_tokens(text)
    if not parsed_tokens:
        raise CadRefError(
            "No @cad[...] token found. Expected @cad[<cad-path>] or @cad[<cad-path>#<selector>] "
            "where selector can be o<path>, o<path>.s<n>, o<path>.f<n>, o<path>.e<n>, o<path>.v<n>, or s<n>/f<n>/e<n>/v<n> for single-occurrence entries."
        )

    contexts: dict[str, EntryContext] = {}
    errors: list[dict[str, object]] = []
    token_results: list[dict[str, object]] = []
    refs_required_by_cad_path: dict[str, bool] = {}

    for parsed in parsed_tokens:
        selectors = parsed.selectors or ()
        refs_required_by_cad_path[parsed.cad_path] = (
            refs_required_by_cad_path.get(parsed.cad_path, False)
            or bool(selectors)
            or include_topology
            or facts
        )

    for parsed in parsed_tokens:
        context = contexts.get(parsed.cad_path)
        if context is None:
            context = _load_entry_context(
                parsed.cad_path,
                profile=SelectorProfile.REFS if refs_required_by_cad_path.get(parsed.cad_path) else SelectorProfile.SUMMARY,
            )
            contexts[parsed.cad_path] = context

        token_result: dict[str, object] = {
            "line": parsed.line,
            "token": parsed.token,
            "cadPath": parsed.cad_path,
            "stepPath": _relative_to_repo(context.step_path) if context.step_path is not None else "",
            "stepHash": context.manifest.get("stepHash"),
            "summary": _entry_summary(context),
            "selections": [],
            "warnings": [],
        }
        if facts:
            token_result["entryFacts"] = _entry_facts(context)

        if parsed.selectors:
            for raw_selector in parsed.selectors:
                selection, selection_error = _inspect_selector(
                    parsed.cad_path,
                    raw_selector,
                    context,
                    detail=detail,
                    facts=facts,
                )
                token_result["selections"].append(selection)
                if selection_error is not None:
                    errors.append(
                        {
                            "line": parsed.line,
                            "cadPath": parsed.cad_path,
                            "selector": raw_selector,
                            **selection_error,
                        }
                    )
        elif include_topology:
            if context.selector_index is not None:
                token_result["topology"] = lookup.topology_payload(context.selector_index)

        token_results.append(token_result)

    return {
        "ok": not errors,
        "tokens": token_results,
        "errors": errors,
    }


def _relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _load_entry_context(cad_path: str, *, profile: SelectorProfile) -> EntryContext:
    lookup_cad_path = _lookup_cad_path(cad_path)
    resolved = resolve_cad_source_path(lookup_cad_path)
    if resolved is None:
        raise CadRefError(f"CAD STEP ref not found for '{cad_path}'.")
    kind, source_path = resolved
    if kind in {"part", "assembly"}:
        step_path = find_step_path(lookup_cad_path)
        if step_path is None:
            raise CadRefError(f"STEP file not found for ref '{cad_path}'.")
        bundle = extract_selectors(step_path, cad_ref=cad_path, profile=profile)
        selector_index = lookup.build_selector_index(bundle.manifest)
        return EntryContext(
            cad_path=cad_path,
            kind=kind,
            source_path=source_path,
            step_path=step_path,
            manifest=bundle.manifest,
            selector_index=selector_index,
        )

    raise CadRefError(f"CAD ref '{cad_path}' is not STEP-backed.")


def _cad_path_lookup_candidates(cad_path: str) -> tuple[str, ...]:
    return (cad_path,) if cad_path else ()


def _lookup_cad_path(cad_path: str) -> str:
    for candidate in _cad_path_lookup_candidates(cad_path):
        if resolve_cad_source_path(candidate) is not None:
            return candidate
    return cad_path


def _entry_summary(context: EntryContext) -> dict[str, object]:
    if context.selector_index is not None:
        summary = lookup.entry_summary(context.selector_index)
        summary["kind"] = context.kind
        return summary
    return {"kind": context.kind, "bounds": context.manifest.get("bbox")}


def _selection_label(selector_type: str, display_selector: str) -> str:
    noun = {
        "occurrence": "Occurrence",
        "shape": "Shape",
        "face": "Face",
        "edge": "Edge",
        "vertex": "Corner",
    }.get(selector_type, "Reference")
    return f"{noun} {display_selector}"


def _selection_summary(selector_type: str, row: dict[str, object]) -> str:
    if selector_type == "occurrence":
        name = str(row.get("name") or row.get("sourceName") or "").strip()
        return name or str(row.get("id") or "")
    if selector_type == "shape":
        kind = str(row.get("kind") or "shape")
        volume = row.get("volume")
        area = row.get("area")
        if volume not in {None, ""}:
            return f"{kind} volume={volume}"
        if area not in {None, ""}:
            return f"{kind} area={area}"
        return kind
    if selector_type == "face":
        return f"{row.get('surfaceType')} area={row.get('area')}"
    if selector_type == "edge":
        return f"{row.get('curveType')} length={row.get('length')}"
    return f"corner edges={row.get('edgeCount')}"


def _occurrence_detail(row: dict[str, object], selector_index: lookup.SelectorIndex) -> dict[str, object]:
    occurrence_id = str(row.get("id") or "").strip()
    child_rows = [
        child
        for child in selector_index.occurrences
        if str(child.get("parentId") or "").strip() == occurrence_id
    ]
    descendant_ids: list[str] = []
    stack = list(reversed(child_rows))
    while stack:
        child = stack.pop()
        child_id = str(child.get("id") or "").strip()
        if child_id:
            descendant_ids.append(lookup.display_selector(child_id, selector_index))
            stack.extend(
                grandchild
                for grandchild in reversed(selector_index.occurrences)
                if str(grandchild.get("parentId") or "").strip() == child_id
            )
    return {
        "path": row.get("path"),
        "name": row.get("name"),
        "sourceName": row.get("sourceName"),
        "parentId": lookup.display_selector(str(row.get("parentId") or ""), selector_index),
        "childCount": len(child_rows),
        "descendantOccurrenceIds": descendant_ids,
        "transform": row.get("transform"),
        "bbox": row.get("bbox"),
        "shapeCount": row.get("shapeCount"),
        "faceCount": row.get("faceCount"),
        "edgeCount": row.get("edgeCount"),
        "vertexCount": row.get("vertexCount"),
    }


def _shape_detail(row: dict[str, object], selector_index: lookup.SelectorIndex) -> dict[str, object]:
    return {
        "occurrenceId": lookup.display_selector(str(row.get("occurrenceId") or ""), selector_index),
        "kind": row.get("kind"),
        "bbox": row.get("bbox"),
        "center": row.get("center"),
        "area": row.get("area"),
        "volume": row.get("volume"),
        "faceCount": row.get("faceCount"),
        "edgeCount": row.get("edgeCount"),
        "vertexCount": row.get("vertexCount"),
    }


def _face_detail(row: dict[str, object], selector_index: lookup.SelectorIndex) -> dict[str, object]:
    adjacent_edges = [
        lookup.display_selector(selector, selector_index)
        for selector in lookup.face_adjacent_edge_selectors(row, selector_index)
    ]
    return {
        "occurrenceId": lookup.display_selector(str(row.get("occurrenceId") or ""), selector_index),
        "shapeId": lookup.display_selector(str(row.get("shapeId") or ""), selector_index),
        "surfaceType": row.get("surfaceType"),
        "area": row.get("area"),
        "center": row.get("center"),
        "normal": row.get("normal"),
        "bbox": row.get("bbox"),
        "params": row.get("params"),
        "adjacentEdgeSelectors": adjacent_edges,
    }


def _edge_detail(row: dict[str, object], selector_index: lookup.SelectorIndex) -> dict[str, object]:
    adjacent_faces = [
        lookup.display_selector(selector, selector_index)
        for selector in lookup.edge_adjacent_face_selectors(row, selector_index)
    ]
    adjacent_vertices = [
        lookup.display_selector(selector, selector_index)
        for selector in lookup.edge_adjacent_vertex_selectors(row, selector_index)
    ]
    return {
        "occurrenceId": lookup.display_selector(str(row.get("occurrenceId") or ""), selector_index),
        "shapeId": lookup.display_selector(str(row.get("shapeId") or ""), selector_index),
        "curveType": row.get("curveType"),
        "length": row.get("length"),
        "center": row.get("center"),
        "bbox": row.get("bbox"),
        "params": row.get("params"),
        "adjacentFaceSelectors": adjacent_faces,
        "adjacentVertexSelectors": adjacent_vertices,
    }


def _vertex_detail(row: dict[str, object], selector_index: lookup.SelectorIndex) -> dict[str, object]:
    adjacent_edges = [
        lookup.display_selector(selector, selector_index)
        for selector in lookup.vertex_adjacent_edge_selectors(row, selector_index)
    ]
    adjacent_faces = [
        lookup.display_selector(selector, selector_index)
        for selector in lookup.vertex_adjacent_face_selectors(row, selector_index)
    ]
    return {
        "occurrenceId": lookup.display_selector(str(row.get("occurrenceId") or ""), selector_index),
        "shapeId": lookup.display_selector(str(row.get("shapeId") or ""), selector_index),
        "center": row.get("center"),
        "bbox": row.get("bbox"),
        "adjacentEdgeSelectors": adjacent_edges,
        "adjacentFaceSelectors": adjacent_faces,
    }


def _inspect_selector(
    cad_path: str,
    raw_selector: str,
    context: EntryContext,
    *,
    detail: bool,
    facts: bool,
) -> tuple[dict[str, object], dict[str, object] | None]:
    parsed_selector = syntax.parse_selector(raw_selector)
    if parsed_selector is None:
        return (
            {
                "status": "error",
                "selectorType": "unknown",
                "normalizedSelector": raw_selector,
                "displaySelector": raw_selector,
            },
            {
                "kind": "selector",
                "message": f"Unsupported selector '{raw_selector}'.",
            },
        )

    if context.selector_index is None:
        raise CadRefError(f"Selector index unavailable for {cad_path}")

    lookup_result = lookup.lookup_selector(raw_selector, context.selector_index)
    normalized_selector = lookup.canonicalize_selector(raw_selector, context.selector_index) or parsed_selector.canonical
    display_selector = lookup.display_selector(normalized_selector, context.selector_index)
    if lookup_result is None:
        return (
            {
                "status": "error",
                "selectorType": parsed_selector.selector_type,
                "normalizedSelector": normalized_selector,
                "displaySelector": display_selector,
            },
            {
                "kind": "selector",
                "message": f"Selector '{raw_selector}' did not resolve against {cad_path}.",
            },
        )

    selector_type, row = lookup_result
    selection: dict[str, object] = {
        "status": "resolved",
        "selectorType": selector_type,
        "normalizedSelector": normalized_selector,
        "displaySelector": display_selector,
        "copyText": syntax.build_cad_token(cad_path, display_selector),
        "label": _selection_label(selector_type, display_selector),
        "summary": _selection_summary(selector_type, row),
    }
    if detail:
        if selector_type == "occurrence":
            selection["detail"] = _occurrence_detail(row, context.selector_index)
        elif selector_type == "shape":
            selection["detail"] = _shape_detail(row, context.selector_index)
        elif selector_type == "face":
            selection["detail"] = _face_detail(row, context.selector_index)
        elif selector_type == "edge":
            selection["detail"] = _edge_detail(row, context.selector_index)
        elif selector_type == "vertex":
            selection["detail"] = _vertex_detail(row, context.selector_index)
    if facts:
        selection["geometryFacts"] = analysis.geometry_facts_for_row(selector_type, row, context.selector_index)
    return selection, None


def _entry_facts(context: EntryContext) -> dict[str, object]:
    bbox = context.manifest.get("bbox")
    facts = analysis.bbox_facts(bbox)
    facts["kind"] = context.kind
    if context.selector_index is None:
        return facts
    facts["majorPlanes"] = analysis.major_planar_face_groups(context.selector_index)
    return facts


def cad_path_from_target(target: str) -> str:
    parsed_tokens = syntax.parse_cad_tokens(target)
    if parsed_tokens:
        if len(parsed_tokens) != 1:
            raise CadRefError("Expected exactly one @cad[...] token.")
        return parsed_tokens[0].cad_path
    normalized = syntax.normalize_cad_path(target)
    if normalized is None:
        raise CadRefError(f"Invalid CAD entry target: {target}")
    return normalized


def load_entry_context_for_target(target: str, *, profile: SelectorProfile = SelectorProfile.REFS) -> EntryContext:
    return _load_entry_context(cad_path_from_target(target), profile=profile)


def inspect_entry_planes(
    target: str,
    *,
    coordinate_tolerance: float = 1e-3,
    min_area_ratio: float = 0.05,
    limit: int = 12,
) -> dict[str, object]:
    context = load_entry_context_for_target(target, profile=SelectorProfile.REFS)
    if context.selector_index is None:
        raise CadRefError("Plane grouping is only supported for STEP-backed entries.")
    return {
        "ok": True,
        "cadPath": context.cad_path,
        "stepPath": _relative_to_repo(context.step_path) if context.step_path is not None else "",
        "summary": _entry_summary(context),
        "planes": analysis.major_planar_face_groups(
            context.selector_index,
            coordinate_tolerance=coordinate_tolerance,
            min_area_ratio=min_area_ratio,
            limit=limit,
        ),
    }


def diff_entry_targets(
    left_target: str,
    right_target: str,
    *,
    detail: bool = False,
) -> dict[str, object]:
    left_context = load_entry_context_for_target(left_target, profile=SelectorProfile.REFS)
    right_context = load_entry_context_for_target(right_target, profile=SelectorProfile.REFS)

    diff_payload = analysis.selector_manifest_diff(left_context.manifest, right_context.manifest)
    bbox_left = left_context.manifest.get("bbox")
    bbox_right = right_context.manifest.get("bbox")
    size_left = analysis.bbox_size(bbox_left)
    size_right = analysis.bbox_size(bbox_right)
    center_left = analysis.bbox_center(bbox_left)
    center_right = analysis.bbox_center(bbox_right)

    result: dict[str, object] = {
        "ok": True,
        "left": {
            "cadPath": left_context.cad_path,
            "kind": left_context.kind,
            "stepPath": _relative_to_repo(left_context.step_path) if left_context.step_path is not None else "",
            "summary": _entry_summary(left_context),
            "entryFacts": _entry_facts(left_context),
        },
        "right": {
            "cadPath": right_context.cad_path,
            "kind": right_context.kind,
            "stepPath": _relative_to_repo(right_context.step_path) if right_context.step_path is not None else "",
            "summary": _entry_summary(right_context),
            "entryFacts": _entry_facts(right_context),
        },
        "diff": {
            "kindChanged": left_context.kind != right_context.kind,
            **diff_payload,
            "sizeDelta": (
                [float(size_right[index] - size_left[index]) for index in range(3)]
                if size_left is not None and size_right is not None
                else None
            ),
            "centerDelta": (
                [float(center_right[index] - center_left[index]) for index in range(3)]
                if center_left is not None and center_right is not None
                else None
            ),
        },
    }

    if detail and left_context.selector_index is not None and right_context.selector_index is not None:
        result["diff"]["leftMajorPlanes"] = analysis.major_planar_face_groups(left_context.selector_index)
        result["diff"]["rightMajorPlanes"] = analysis.major_planar_face_groups(right_context.selector_index)
    return result
