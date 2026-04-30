# gen_step_assembly

Regenerates explicit assembly STEP targets and their package-local explorer artifacts.

```bash
python <cad-skill>/scripts/gen_step_assembly/cli.py path/to/assembly.py
python <cad-skill>/scripts/gen_step_assembly/cli.py path/to/assembly.py --summary
python <cad-skill>/scripts/gen_step_assembly/cli.py path/to/imported-assembly.step --glb-tolerance 1.0
```

Targets must be explicit file paths:

- generated Python assembly sources
- direct STEP/STP files

Relative targets resolve from the current working directory; `path/to/assembly.py` works only when that path exists from the current directory.

Generated Python assembly sources must expose `gen_step()` returning an envelope with either flat `instances` or recursive `children`, plus `step_output`; see `references/generator-contract.md`.

Direct STEP/STP targets may use:

- mesh tolerance flags
- `--color`
- STL and 3MF sidecar flags

`--skip-topology` is rejected for assemblies.

This tool does not generate directories and does not run `gen_dxf()` or `gen_urdf()`.
