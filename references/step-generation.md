# STEP generation

Read this file when generating or regenerating STEP/STP artifacts from build123d Python source or from direct STEP/STP targets.

## Tool

The launcher lives in the CAD skill directory:

```bash
python scripts/step [--kind {part|assembly}] targets... [flags]
```

Use explicit target paths only. Target paths are resolved from the command cwd unless absolute. When running from a workspace root, prefix the launcher path with the CAD skill directory; when running from the skill directory, pass absolute or correctly relative workspace target paths. Do not rely on directory-wide generation.

## Generated Python source

Generated build123d sources should define:

```python
def gen_step():
    ...
    return shape_or_compound
```

Generated Python targets infer their kind from the source metadata and `gen_step()` envelope; pass the source path directly. When a generator exists, this is the preferred way to run `scripts/step`.

```bash
python scripts/step path/to/part.py
python scripts/inspect refs path/to/part.step --facts --planes --positioning
```

```bash
python scripts/step path/to/assembly.py
python scripts/inspect refs path/to/assembly.step --facts --planes --positioning
```

Passing a generated assembly `.step` directly treats it as imported native STEP. Pass the `.py` assembly source when source-level assembly composition must be preserved.

## Direct STEP/STP targets

Use direct STEP/STP targets only when the generator is unavailable or the user explicitly identifies a STEP/STP file as the target:

```bash
python scripts/step --kind part path/to/imported.step
python scripts/inspect refs path/to/imported.step --facts --planes --positioning
```

Direct targets can use sidecar mesh flags, but generator targets remain preferred when a generator exists. Read `supported-exports.md` for STL and 3MF sidecars.

## Adjacent Explorer artifacts

`scripts/step` generates the explicit STEP target and adjacent hidden Explorer GLB/topology artifacts. These artifacts support Explorer and render workflows. Do not require a separate validation subcommand for them.

Use `rendering-and-explorer.md` for Explorer startup and link formatting.

## Post-generation inspection

Run lightweight inspection after generation with `scripts/inspect`.

Rules:

- Use facts and plane grouping for normal generation.
- Add positioning facts when the model has mating faces, assembly children, datums, or repeated features.
- Add topology only when selector enumeration is needed; it can be expensive on large models.

Recommended inspection:

```bash
python scripts/inspect refs path/to/model.step --facts --planes --positioning
```

For selector-heavy validation:

```bash
python scripts/inspect refs path/to/model.step --topology
```

## Generation checklist

Before running the command:

- Confirm the user request has been converted into a natural-language CAD brief.
- Confirm the source defines `gen_step()`.
- Prefer the Python generator over a generated STEP/STP file when both are available.
- Confirm labels are assigned for exported parts and assembly children.
- Confirm the target path is explicit.
- Confirm expected bbox, labels, and positioning checks are known.

After running the command:

- Confirm the process succeeded.
- Confirm the STEP file exists and is non-empty.
- Run the relevant `scripts/inspect` command and parse its output.
- Return Explorer link(s) using `rendering-and-explorer.md`, or report why they are unavailable.
- Continue with targeted inspection if facts/planes are insufficient.
