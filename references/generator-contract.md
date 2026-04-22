# CAD Generator Contract

Use this reference when creating or editing STEP, DXF, STL, GLB/topology, or imported STEP sources.

## Source Types

- A generated part is a Python file with a top-level zero-argument `gen_step()` returning an envelope with `shape` and `step_output`.
- A generated assembly is a Python file with a top-level zero-argument `gen_step()` returning an envelope with `instances` and `step_output`.
- A generated part may also define `gen_dxf()` returning an envelope with `document` and `dxf_output`.
- Imported STEP/STP entries are targeted directly with `gen_step_part` or `gen_step_assembly`.
- Direct imported parts intentionally have no Python generator; do not create placeholder generators for them.
- Helper modules may live alongside generators as long as they do not implement a generator contract.

## Generator Rules

Each generator script should:

1. Be runnable from the project environment.
2. Not rely on the current working directory. Resolve local filesystem paths from `__file__`.
3. Be idempotent and deterministic. Avoid timestamps, random identifiers, or nondeterministic ordering unless explicitly required by the design.
4. Fail clearly when required inputs are missing. Exit non-zero and identify the missing path and failing generator.
5. Keep generated output locations explicit in generator envelopes or direct STEP/STP CLI flags; do not rely on sibling output naming.

## Part Envelopes

`gen_step()` for parts must return:

- `shape`: a `build123d.Shape`
- `step_output`: relative path to the generated `.step` output

Optional fields include:

- `export_stl`: boolean
- `stl_output`: relative path to generated `.stl` output when STL export is enabled
- `stl_tolerance`, `stl_angular_tolerance`
- `glb_tolerance`, `glb_angular_tolerance`
- `skip_topology`: for parts that should emit GLB without selector topology sidecars

`gen_dxf()` must return:

- `document`: an object with a callable `saveas(...)`
- `dxf_output`: relative path to generated `.dxf` output

## Assembly Envelopes

`gen_step()` for assemblies must return:

- `instances`: list of assembly instances
- `step_output`: relative path to generated `.step` output

Each instance must define:

- `path`: STEP/STP path relative to the assembly generator file
- `name`: selector-safe instance name containing only letters, numbers, `.`, `_`, or `-`
- `transform`: 16-number row-major transform

Assembly STEP generation resolves instance paths relative to the generator file. It does not require a harness root or catalog entry for each instance; the referenced STEP/STP file must exist.

## Imported STEP/STP Targets

Imported STEP/STP files are passed directly to the split STEP tools:

- `gen_step_part path/to/file.step` treats the target as an imported part.
- `gen_step_assembly path/to/file.step` treats the target as an imported assembly.

Optional CLI flags for direct imported targets include:

- `--export-stl`
- `--stl-output`
- `--stl-tolerance`, `--stl-angular-tolerance`
- `--glb-tolerance`, `--glb-angular-tolerance`
- `--color`
- `--skip-topology` for parts

These flags are not persisted. Pass them each time an imported STEP/STP file needs non-default generation settings.

## Output Paths

Envelope output fields and CLI output fields:

- are relative to the owning Python script or direct STEP/STP target
- must use POSIX `/` separators
- must use the correct artifact suffix
- are resolved as file paths, not through a harness root

The host project may impose its own layout policy, such as keeping outputs under a `models/` directory, but the CAD skill runtime does not hardcode that convention.

## Generated Artifacts

STEP generation writes package-local render/reference artifacts for STEP-backed parts and assemblies:

- `.<step-filename>/model.glb`
- `.<step-filename>/topology.json`
- `.<step-filename>/topology.bin`

Assemblies embed composition data in `.<step-filename>/topology.json` under `assembly.root` when linked source information is available. Imported STEP assemblies may also write `.<step-filename>/components/*.glb` native component assets for part-list rendering.

These generated artifacts are not source of truth and must not be hand-edited.

Generation tools write and overwrite current configured outputs. They do not delete stale outputs when paths change.
