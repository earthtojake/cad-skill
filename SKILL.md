---
name: cad
description: Create, modify, inspect, validate, and review STEP-first build123d/Python CAD parts and assemblies. Use for natural-language CAD specs, STEP/STP generation, build123d source, build123d source-level joints, @cad references, geometry facts, measurements, mating deltas, CAD Explorer links, conditional review renders, and secondary DXF/STL/3MF outputs.
---

# CAD generation, inspection, and validation

## Purpose

Create or modify parametric CAD models from natural-language requirements, generate validated STEP/STP artifacts, inspect geometry references, and return checked outputs plus CAD Explorer links. Treat STEP as the primary CAD artifact. Treat DXF, STL, and 3MF as secondary workflows that branch from, or accompany, a STEP-first process. For assemblies, prefer source-level build123d joints and named mating datums when the parts have functional assembly relationships.

## Use this skill when

Use this skill when the user asks for CAD files, STEP/STP files, build123d source, `@cad[...]` references, mechanical parts, assemblies, enclosures, brackets, fixtures, holes, counterbores, countersinks, slots, pockets, bosses, standoffs, ribs, fillets, chamfers, shells, source-level joints, mating, measurements, or CAD Explorer review links.

Also use it when the user asks for DXF, STL, or 3MF output from CAD geometry. Keep those workflows secondary and load `dxf.md` or `supported-exports.md` for details.

Do not use this skill for render-only concept art, CAM toolpaths, engineering certification, FEA conclusions, architectural BIM, or freehand illustration unless the user also needs CAD geometry.

## Default assumptions

Use these defaults unless the user specifies otherwise:

- Units: millimeters.
- Origin: center of the main part or assembly unless a mating interface or fixed root component suggests a better origin.
- Base plane: XY.
- Up/extrusion axis: positive Z.
- Output geometry: closed, positive-volume solids unless the user requests surfaces or construction geometry.
- STEP structure: one valid solid, a compound of solids, or a labeled assembly compound.
- Assembly structure: fixed root part, part-local frames, named mating datums, build123d joints where applicable, and explicit generated placements.
- Small plastic enclosure wall: 2.0-3.0 mm when unspecified.
- Cosmetic fillet: 1.0-3.0 mm when safe for local geometry.
- M3/M4/M5 normal clearance holes: 3.4/4.5/5.5 mm unless another standard is requested.

Ask one focused clarification question only when missing information makes the model impossible, fit-critical, safety-critical, or compliance-bound. Otherwise proceed with explicit assumptions.

## Natural-language specs only

Do not ask the user to provide a JSON specification and do not make JSON the user-facing workflow. Convert the user's prose into an internal CAD brief with dimensions, features, assumptions, output paths, and validation criteria. Use `references/natural-language-specs.md` for brief-writing patterns.

## Root model

Keep these roots separate:

- **CAD skill directory**: this folder. Tool launchers live here as `scripts/step`, `scripts/inspect`, `scripts/render`, and `scripts/dxf`.
- **Tool process cwd**: relative CAD targets are resolved from the command's current working directory. Use absolute target paths when running from the skill directory, or run from the workspace root and invoke the launchers with a path to this skill directory.
- **Explorer scan root**: CAD Explorer scans `EXPLORER_ROOT_DIR` when set; otherwise it scans the workspace root inferred by Vite from `EXPLORER_WORKSPACE_ROOT`, npm `INIT_CWD`, or the Vite process cwd. Explorer `file=` links must be relative to the active scan root.

Short command examples in this skill use launcher paths relative to the CAD skill directory. Adapt the launcher path or target path so project CAD files resolve from the intended workspace, not accidentally under the skill directory.

Prefer keeping a STEP output and its Python generator in the same directory so the source stays easy to discover. Unless the user explicitly requests otherwise, keep the STEP basename and generator basename the same even when they cannot live side by side.

## Available tools

From the CAD skill directory, the launcher shape is:

```bash
python scripts/step ...
python scripts/inspect ...
python scripts/render ...
python scripts/dxf ...
npm --prefix explorer run dev
npm --prefix explorer run dev:ensure -- --file path/to/model.step
```

Use the active project Python interpreter. If only the repo-local virtualenv is available, invoke that interpreter while keeping the root model above explicit.

Use `python scripts/<tool> --help` for the complete current command interface; reference docs show recommended workflows, not every flag.

## Required workflow

1. **Classify the task.** Identify whether this is a new part, new assembly, source modification, direct STEP/STP inspection, reference selection, measurement/mating check, render review, or secondary output request.
2. **Load only the needed references.** Use the triggers below instead of reading the whole reference set.
3. **Create a natural-language CAD brief.** Extract dimensions, units, coordinate convention, feature intent, output paths, assumptions, and validation targets.
4. **Plan before coding.** Define parameters, labels, source paths, expected bounding boxes, and any mating/positioning datums before editing.
5. **Edit source, not generated artifacts.** Prefer build123d Python with `gen_step()` for STEP generation.
6. **Generate explicit targets.** Use `scripts/step` for STEP/STP generation and sidecars. Use `--kind part` or `--kind assembly` only for direct STEP/STP imports. Do not run directory-wide generation.
7. **Validate geometrically.** Use `scripts/inspect refs --facts --planes --positioning`, then targeted `measure`, `mate`, `frame`, or `diff` when needed.
8. **Return Explorer links.** Use `references/rendering-and-explorer.md` for Explorer startup, scan-root, and link rules.
9. **Render conditionally.** Use `scripts/render` only when requested, Explorer is unavailable, visual ambiguity remains, or section/wireframe review answers a real validation question.
10. **Repair and rerun.** If a check fails, change the smallest responsible source section, regenerate, and rerun the failed validation.

## Non-negotiables

- Treat generated STEP/STP, STL, 3MF, GLB/topology, DXF outputs, and Explorer sidecars as derived artifacts.
- Keep STEP as the primary validated CAD artifact; DXF/STL/3MF are secondary unless the user explicitly says otherwise.
- When a Python generator exists, run `scripts/step` on the generator. Use a direct STEP/STP target only when the generator is unavailable or the user explicitly identifies that STEP/STP file as the target.
- Use named parameters, closed solids, explicit labels, and source-controlled geometry intent.
- Author assembly positioning in source with part-local datums, explicit `Location` transforms, or build123d joints. Treat CLI `inspect mate` as read-only validation, not as a source-editing API.
- Do not use `git status`, `git diff`, or file-size churn as CAD comparison for large exported STEP/STP, GLB/topology, STL, 3MF, or DXF artifacts. Compare source changes, `scripts/inspect` summaries, targeted renders, or CAD Explorer output instead; use path-limited git status only for bookkeeping.
- Report only checks that actually ran or are directly supported by tool output.
- If Explorer fails, say so and rely on CLI inspection for validation.

## Progressive references

Load these files only when their trigger applies:

- `references/natural-language-specs.md` — converting prose requirements into a CAD brief without requiring user JSON.
- `references/step-generation.md` — STEP generation, direct STEP/STP targets, part-vs-assembly behavior, and post-generation inspection.
- `references/inspection-and-validation.md` — validation gates, `@cad[...]` refs, facts, planes, topology, measurements, mating, diff, frame, and final validation reporting.
- `references/positioning.md` — part-local datums, assembly transforms, build123d joints, CLI mate validation, and positioning reports.
- `references/rendering-and-explorer.md` — CAD Explorer links and conditional render view/wireframe/section/list.
- `references/dxf.md` — secondary DXF workflow.
- `references/supported-exports.md` — secondary STL/3MF sidecar workflows.
- `references/build123d-modeling.md` — build123d modeling patterns, topology, selectors, features, assemblies.
- `references/repair-loop.md` — diagnosis and repair procedures.

Final responses should include generated files, CAD Explorer links, validation actually run, assumptions, and caveats. Use `references/inspection-and-validation.md` for report structure.
