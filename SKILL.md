---
name: cad
description: CAD workflows to programatically generate STEP/STL/3MF/DXF/GLB files; regenerate, inspect, validate, snapshot, resolve @cad refs, and hand off CAD Explorer links.
---

# CAD Workflows

## Workflow

1. Read project-local documentation only when project inventory, dependency notes, or preferred rebuild roots matter.
2. Treat generator scripts and imported STEP files as source of truth. Do not hand-edit generated STEP, STL, 3MF, GLB, topology, DXF render payloads, or explorer-derived artifacts. Do not use git to track or compare changes between exported files; review source changes, deterministic summaries, snapshots, or CAD Explorer output instead.
3. For generator and imported STEP/STP contracts, read `references/generator-contract.md`.
4. If the prompt includes `@cad[...]` refs, read `references/prompt-refs.md` and resolve refs before editing with `cadref`; use `--detail --facts` for face, edge, corner, or occurrence-specific edits.
5. For nontrivial geometry edits, read `references/geometry-workflow.md` and write a short geometry contract before editing.
6. Edit only the owning generator or imported STEP source needed for the requested change.
7. Regenerate explicit targets only. Do not run directory-wide generation.
8. Validate with the cheapest proof that is strong enough. For validation and review images, read `references/validation-and-snapshots.md`.
9. For displayable outputs, follow CAD Explorer Handoff unless browser handoff is explicitly unnecessary.

## Prompt Artifacts

CAD Explorer may provide annotated screenshots and `@cad[...]` references. Treat screenshots as supporting context and `@cad[...]` refs as stable handles. If they disagree, trust the ref and source geometry, then use the screenshot to understand intent.

For ref grammar, selector semantics, stale-ref handling, and geometry-fact workflows, read `references/prompt-refs.md` and use `scripts/cadref/cli.py`. Do not inspect explorer-derived runtime assets to interpret prompt refs; resolve refs from source STEP data and deterministic selector artifacts.

## CAD Explorer Handoff

After editing or regenerating any CAD Explorer-displayable `.step`, `.stp`, `.stl`, `.3mf`, `.dxf`, or `.urdf` entry, make CAD Explorer available and include links for the affected entries in the final response.

Ensure the CAD Explorer server first:

```bash
npm --prefix .agents/skills/cad/explorer run dev:ensure
```

Explorer link format:

```text
http://127.0.0.1:4178/?file=<path-relative-to-explorer-root-with-extension>
```

CAD Explorer scans `EXPLORER_ROOT_DIR`, which defaults to the command's current working directory when unset or empty. Run the server from the workspace you want to inspect, or set `EXPLORER_ROOT_DIR` to a directory inside that workspace. Keep a single reusable Explorer root for the dev server and make `file` relative to the active scan root, even when the changed entry is nested several directories below. Do not add `dir` query parameters or narrow the running server root merely because only one file changed; fix or report startup/catalog issues instead so the running dev server can be reused by other threads to inspect other entries under the same root.

The `file` parameter must include the displayed file extension and should always be present for entry links.

For CAD prompt refs, keep the entry `file=` and append URL-encoded `refs=` parameters. Python generators are not Explorer entries; link their generated outputs. If only CAD Explorer app code changed, link the base CAD Explorer URL.

Let generation tools own CAD Explorer-consumed render, topology, metadata, and sidecar artifacts. Do not hand-edit or build separate Explorer cache files unless the task is explicitly about the Explorer implementation itself.

## Commands

Run with the Python environment for the project or workspace. If the environment lacks the CAD runtime packages, install this skill's script dependencies from `requirements.txt`. Invoke tools as filesystem scripts, for example `python <cad-skill>/scripts/gen_step_part/cli.py ...`. Relative target paths are resolved from the current working directory; the tools do not prepend a harness root.

- Part STEP/render/topology: `scripts/gen_step_part/cli.py`
- Assembly STEP/render/topology: `scripts/gen_step_assembly/cli.py`
- DXF sidecars: `scripts/gen_dxf/cli.py`
- Prompt refs and STEP facts: `scripts/cadref/cli.py`
- Verification PNGs: `scripts/snapshot/cli.py`

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
