from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from common.catalog import (
    cad_ref_from_step_path as fallback_cad_ref_from_step_path,
    find_source_by_cad_ref,
    find_source_by_path,
    explorer_artifact_path_for_step_path,
    explorer_directory_for_step_path,
)


REPO_ROOT = Path.cwd().resolve()
CAD_ROOT = REPO_ROOT


def _source_for_cad_ref(cad_ref: str):
    source = find_source_by_cad_ref(cad_ref)
    if source is None:
        raise ValueError(f"CAD STEP ref not found: {cad_ref}")
    return source


def cad_ref_from_step_path(step_path: Path) -> str:
    source = find_source_by_path(step_path)
    if source is not None:
        return source.cad_ref
    return fallback_cad_ref_from_step_path(step_path)


def part_stl_path_for_cad_ref(cad_ref: str) -> Path:
    source = _source_for_cad_ref(cad_ref)
    if source.stl_path is None:
        raise ValueError(f"CAD STEP ref has no configured STL output: {cad_ref}")
    return source.stl_path


def part_3mf_path_for_cad_ref(cad_ref: str) -> Path:
    source = _source_for_cad_ref(cad_ref)
    if source.three_mf_path is None:
        raise ValueError(f"CAD STEP ref has no configured 3MF output: {cad_ref}")
    return source.three_mf_path


def explorer_dir_for_cad_ref(cad_ref: str) -> Path:
    source = _source_for_cad_ref(cad_ref)
    if source.step_path is None:
        raise ValueError(f"CAD STEP ref has no STEP path: {cad_ref}")
    return explorer_directory_for_step_path(source.step_path)


def explorer_artifact_path(cad_ref: str, suffix: str) -> Path:
    source = _source_for_cad_ref(cad_ref)
    if source.step_path is None:
        raise ValueError(f"CAD STEP ref has no STEP path: {cad_ref}")
    return explorer_artifact_path_for_step_path(source.step_path, suffix)


def part_glb_path_for_cad_ref(cad_ref: str) -> Path:
    return explorer_artifact_path(cad_ref, ".glb")


def part_selector_manifest_path_for_cad_ref(cad_ref: str) -> Path:
    return explorer_artifact_path(cad_ref, ".topology.json")


def part_selector_binary_path_for_cad_ref(cad_ref: str) -> Path:
    return explorer_artifact_path(cad_ref, ".topology.bin")


def native_component_glb_dir(step_path: Path) -> Path:
    return explorer_directory_for_step_path(step_path) / "components"


def part_stl_path(step_path: Path) -> Path:
    return part_stl_path_for_cad_ref(cad_ref_from_step_path(step_path))


def part_3mf_path(step_path: Path) -> Path:
    return part_3mf_path_for_cad_ref(cad_ref_from_step_path(step_path))


def part_glb_path(step_path: Path) -> Path:
    return explorer_artifact_path_for_step_path(step_path, ".glb")


def part_selector_manifest_path(step_path: Path) -> Path:
    return explorer_artifact_path_for_step_path(step_path, ".topology.json")


def part_selector_binary_path(step_path: Path) -> Path:
    return explorer_artifact_path_for_step_path(step_path, ".topology.bin")


def render_artifact_paths_for_cad_ref(cad_ref: str) -> tuple[Path, Path, Path, Path]:
    return (
        part_stl_path_for_cad_ref(cad_ref),
        part_glb_path_for_cad_ref(cad_ref),
        part_selector_manifest_path_for_cad_ref(cad_ref),
        part_selector_binary_path_for_cad_ref(cad_ref),
    )


def render_artifact_paths(step_path: Path) -> tuple[Path, Path, Path, Path]:
    return render_artifact_paths_for_cad_ref(cad_ref_from_step_path(step_path))


def relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def versioned_repo_url(path: Path, content_hash: str) -> str:
    resolved = path.resolve()
    try:
        relative_path = resolved.relative_to(CAD_ROOT.resolve()).as_posix()
    except ValueError:
        relative_path = resolved.as_posix().lstrip("/")
    suffix = f"?v={content_hash}" if content_hash else ""
    return f"/{relative_path}{suffix}"


def atomic_write_json(output_path: Path, payload: object) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as handle:
        json.dump(payload, handle, separators=(",", ":"), ensure_ascii=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(output_path)
    return output_path
