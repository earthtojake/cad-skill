# gen_step_part

Regenerates explicit part STEP targets and their package-local explorer artifacts.

```bash
python <cad-skill>/scripts/gen_step_part/cli.py path/to/part.py
python <cad-skill>/scripts/gen_step_part/cli.py path/to/imported.step --summary
python <cad-skill>/scripts/gen_step_part/cli.py path/to/imported.step --export-stl --stl-output ../meshes/imported.stl
python <cad-skill>/scripts/gen_step_part/cli.py path/to/imported.step --export-3mf --3mf-output ../meshes/imported.3mf
```

Targets must be explicit file paths:

- generated Python part sources
- direct STEP/STP files

Relative targets resolve from the current working directory.

Generated Python part sources must expose `gen_step()` returning an envelope with `shape` and `step_output`; see `references/generator-contract.md`.

Direct STEP/STP targets may use:

- `--export-stl`
- `--stl-output`
- `--export-3mf`
- `--3mf-output`
- mesh tolerance flags
- `--color`
- `--skip-topology`

This tool does not generate directories and does not run `gen_dxf()` or `gen_urdf()`.
