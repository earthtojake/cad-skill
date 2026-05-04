# Supported exports

Read this file when the user requests STL or 3MF output from CAD geometry. Read `dxf.md` for DXF output, because DXF uses a separate `gen_dxf()` source contract.

## Policy

STL and 3MF are mesh sidecars, not substitutes for STEP. Generate and validate STEP first, then export requested sidecars from the same `scripts/step` run. Do not render STL or 3MF directly; render or inspect the STEP when visual review is needed.

## Tool

Use `scripts/step` with a generated Python source:

```bash
python scripts/step path/to/model.py \
  --stl meshes/model.stl \
  --3mf meshes/model.3mf
```

When a generator exists, use the generator form. Use direct STEP/STP targets only when the generator is unavailable or the user explicitly identifies that file as the target:

```bash
python scripts/step --kind part path/to/model.step \
  --stl meshes/model.stl \
  --3mf meshes/model.3mf
```

Sidecar paths must be relative `.stl` or `.3mf` paths and are resolved beside the STEP output.

## Mesh tolerance

Use these flags when the default mesh density is wrong for the part:

```bash
--mesh-tolerance FLOAT
--mesh-angular-tolerance FLOAT
```

Use tighter tolerances for small curved parts or visual fidelity. Use looser tolerances for large simple geometry when file size matters.

## Workflow

1. Generate STEP from `gen_step()` with the requested sidecar flag(s).
2. Run facts/planes/positioning inspection on the STEP.
3. Return the STEP, requested sidecar files, and CAD Explorer link.

Example:

```bash
python scripts/step models/bracket.py \
  --stl meshes/bracket.stl \
  --mesh-tolerance 0.2 \
  --mesh-angular-tolerance 0.2

python scripts/inspect refs models/bracket.step --facts --planes --positioning
```

## Reporting

```text
Files:
- STEP: models/bracket.step
- STL: meshes/bracket.stl

CAD Explorer:
- http://127.0.0.1:4178/?file=models/bracket.step

Validation:
- STEP geometry validated; STL/3MF generated as requested sidecars.
- Render not run unless requested or needed.
```
