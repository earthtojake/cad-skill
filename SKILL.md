---
name: cad
description: Script-driven CAD generation, inspection, and validation. Use when the agent needs to create, edit, regenerate, inspect, or validate STEP, STL, DXF, GLB/topology render artifacts, `@cad[...]` prompt references, CAD snapshots, part generators, assembly generators, imported STEP/STP files, or CAD-side model workflows. Use the `urdf` skill instead for URDF-specific robot XML, links, joints, and `gen_urdf()` work.
---

# CAD

Use this skill for file-targeted CAD tools that operate on STEP, STL, DXF, GLB/topology, and prompt-reference artifacts.

## Workflow

1. Read project-local documentation only when project inventory, dependency notes, or preferred rebuild roots matter.
2. Treat generator scripts and imported STEP files as source of truth. Do not hand-edit generated STEP, STL, GLB, topology, DXF render payloads, or viewer-derived artifacts.
3. For generator and imported STEP/STP contracts, read `references/generator-contract.md`.
4. If the prompt includes `@cad[...]` refs, read `references/prompt-refs.md` and resolve refs before editing with `cadref`; use `--detail --facts` for face, edge, corner, or occurrence-specific edits.
5. For nontrivial geometry edits, read `references/geometry-workflow.md` and write a short geometry contract before editing.
6. Edit only the owning generator or imported STEP source needed for the requested change.
7. Regenerate explicit targets only. Do not run directory-wide generation.
8. Validate with the cheapest proof that is strong enough. For validation and review images, read `references/validation-and-snapshots.md`.
9. Use the `urdf` skill when the requested output is `.urdf`, robot links/joints, joint limits, mesh references inside URDF XML, or `gen_urdf()`.

## Commands

Run with the Python environment for the project or workspace. If the environment lacks the CAD runtime packages, install this skill's script dependencies from `requirements.txt`. Invoke tools as filesystem scripts, for example `python <cad-skill>/scripts/gen_step_part ...`. Relative target paths are resolved from the current working directory; the tools do not prepend a harness root such as `models/`.

- Part STEP/render/topology: `scripts/gen_step_part`
- Assembly STEP/render/topology: `scripts/gen_step_assembly`
- DXF sidecars: `scripts/gen_dxf`
- Prompt refs and STEP facts: `scripts/cadref`
- Verification PNGs: `scripts/snapshot`

The command interfaces are target-explicit. The STEP tools accept generated Python sources or direct STEP/STP files. `gen_dxf` accepts Python sources that define `gen_dxf()`. `cadref` and `snapshot` use the input shapes described in their references. Use `--summary` where supported. Direct STEP/STP targets can receive import metadata as CLI flags on `gen_step_part` and `gen_step_assembly`.

## References

- STEP part generation: `references/gen-step-part.md`
- STEP assembly generation: `references/gen-step-assembly.md`
- DXF generation: `references/gen-dxf.md`
- Generator and imported STEP/STP contracts: `references/generator-contract.md`
- Geometry edit workflow: `references/geometry-workflow.md`
- Prompt references: `references/prompt-refs.md`
- Validation and snapshots: `references/validation-and-snapshots.md`
- `@cad[...]` inspection: `references/cadref.md`
- Snapshot rendering: `references/snapshot.md`
- Shared implementation notes: `references/common-library.md`
