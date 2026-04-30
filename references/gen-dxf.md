# gen_dxf

Regenerates explicit DXF outputs from Python sources with envelope-returning `gen_dxf()` functions.

```bash
python <cad-skill>/scripts/gen_dxf/cli.py path/to/part.py
python <cad-skill>/scripts/gen_dxf/cli.py path/to/part.py --summary
```

Targets must be explicit generated Python source files whose `gen_dxf()` returns an envelope with `document` and `dxf_output`; see `references/generator-contract.md`. Relative targets resolve from the current working directory. This tool runs only `gen_dxf()` and does not regenerate STEP, GLB/topology, STL, or URDF outputs.
