# CAD Validation And Snapshots

Use this reference when deciding how to prove a CAD change is correct.

## Validation Policy

Do not rely on arbitrary perspective screenshots as the primary evidence of correctness.

Prefer non-visual checks first when they can prove the result:

- generator assertions such as validity, solid count, bounds, expected dimensions, or expected feature positions
- interference or clearance checks for mating parts and assemblies
- placement or transform assertions for derived part locations
- `cadref inspect` when the task depends on stable part, occurrence, body, face, edge, or corner refs
- `cadref planes` for major coplanar plane groups
- `cadref diff` for before/after selector-level geometry or topology changes

Add visual review for complex geometry, orientation-dependent changes, broad shape edits across multiple faces, or whenever numeric checks do not make the result obvious.

## Snapshot Defaults

Use `scripts/snapshot/cli.py` when an image is the cheapest way to answer the review question.

- Start with one targeted PNG view.
- Send an isometric PNG plus a targeted PNG when orientation matters.
- Use `--views ... --out-dir ...` when multiple fixed views are actually needed.
- Use `--align-ref @cad[...]` when the review target is a specific planar face or edge and you want the view to lock to that geometry automatically.
- Prefer GLB-backed part inputs and generated assembly GLB inputs.
- For generated assembly review PNGs, render the generated assembly GLB, such as `path/to/.assembly.step/model.glb`. If that GLB is missing or stale, first run the explicit `gen_step_assembly path/to/assembly.py` target to create it, then snapshot the generated GLB.
- `snapshot` does not support Python assembly source inputs. If you need an assembly review image, regenerate the explicit assembly target and render its generated GLB.
- For very large meshes or assemblies, skip image generation and rely on non-visual checks unless the user specifically needs a render.

## Output Handling

- For snapshot output paths and CLI examples, read `snapshot.md`.
- When the agent generates PNG review artifacts during its own workflow, send those artifacts to the user in the thread as soon as they are available so the user can confirm direction or stop incorrect work early.
- Include final review images in the final response unless the same final result was already shown earlier in the thread.
- Do not send only a narrowly cropped or ambiguous face view when an isometric view would materially improve orientation.
- If review artifacts are skipped because required GLB/STL assets are missing or the mesh is too large to render cheaply, say so clearly and fall back to non-visual checks.
- Treat snapshot renders as verification artifacts, not source of truth.
