# DXF secondary workflow

Read this file only when the user requests DXF or 2D drawing output from CAD geometry.

DXF is secondary. Generate and validate the STEP envelope first when the geometry originates from a CAD source. Do not treat DXF layers as STEP part/assembly structure.

## Tool

```bash
python scripts/dxf targets...
```

Only standard help flags are expected.

## Source requirements

A DXF target must be a Python source defining:

```python
def gen_dxf():
    ...
    return document, dxf_output
```

The same file must also define a valid `gen_step()` envelope because discovery uses the CAD source catalog.

```python
def gen_step():
    ...
    return shape_or_compound
```

## Workflow

1. Convert the user's prose into a natural-language CAD brief.
2. Build or validate the `gen_step()` envelope.
3. Generate STEP with lightweight facts/planes/positioning inspection.
4. Start CAD Explorer and return the STEP Explorer link.
5. Add or update `gen_dxf()` for the requested projection, layout, or drawing output.
6. Run `scripts/dxf` on explicit Python source targets.
7. Report the DXF output plus the primary STEP and Explorer link.

## Command

```bash
python scripts/dxf path/to/source.py
```

## Reporting

```text
Files:
- STEP: path/to/source.step
- DXF: path/to/output.dxf

CAD Explorer:
- http://127.0.0.1:4178/?file=path/to/source.step

Validation:
- STEP geometry: checked with facts/planes/positioning
- DXF: generated from gen_dxf(); drawing-layer content reported if available
```
