# CAD Ref Tool

`scripts/cadref/cli.py` resolves prompt-ready `@cad[...]` refs directly from STEP entries.

Run commands from the project or workspace directory that makes your target paths resolve.

## Canonical Command

```bash
python <cad-skill>/scripts/cadref/cli.py --help
```

## Command Surface

```bash
python <cad-skill>/scripts/cadref/cli.py inspect '<text containing @cad[...] refs>' --json

python <cad-skill>/scripts/cadref/cli.py planes path/to/entry --json

python <cad-skill>/scripts/cadref/cli.py diff path/to/before path/to/after --json
```

Whole-entry refs default to a cheap summary so large STEP files do not dump every
selector list. Use `--topology` only when you explicitly need full selector lists:

```bash
python <cad-skill>/scripts/cadref/cli.py inspect '@cad[path/to/entry]' --json

python <cad-skill>/scripts/cadref/cli.py inspect '@cad[path/to/entry#f10]' --detail --facts --json

python <cad-skill>/scripts/cadref/cli.py inspect --refs '@cad[path/to/assembly#o1.1.1.f10]' '@cad[path/to/assembly#o1.1.1.e20]' --detail --facts --json

python <cad-skill>/scripts/cadref/cli.py planes '@cad[path/to/entry]' --json

python <cad-skill>/scripts/cadref/cli.py diff path/to/before path/to/after --json
```

You can also read text from a file or stdin:

```bash
python <cad-skill>/scripts/cadref/cli.py inspect --input-file /tmp/prompt.txt --json

cat /tmp/prompt.txt | python <cad-skill>/scripts/cadref/cli.py inspect --json
```

## Ref Rules

See `references/prompt-refs.md` for token shapes, selector semantics, stale-ref handling, and prompt interpretation workflow.

## Output Contract

`inspect --json` returns:

- per-token STEP context: `cadPath`, source STEP path, STEP hash, and occurrence-aware summary counts
- per-selection resolution status (`resolved` or `error`)
- cheap STEP-derived summary payload for whole-entry refs, including bounds, occurrence count, shape count, face count, edge count, and vertex count
- full occurrence/shape/face/edge/vertex selector lists for whole-entry refs only when `--topology` is passed
- selected occurrence/shape/face/edge/vertex geometry facts when `--detail` is passed, including bbox, center, surface or curve params, and adjacency selectors when available
- compact `entryFacts` and per-selection `geometryFacts` when `--facts` is passed
- top-level `ok` plus structured `errors`

`planes --json` returns:

- `cadPath`, STEP path, and normal entry summary
- grouped major planar-face bands under `planes`, keyed by dominant axis and plane coordinate
- total area, face count, merged bbox, and contributing selectors for each group

Use this when you need to identify the main plates or walls of a part instead of guessing from screenshots.

`diff --json` returns:

- left/right entry summaries plus compact entry facts
- selector-level `topologyChanged`, `geometryChanged`, and `bboxChanged` flags
- face/edge/shape count deltas
- bbox center/size deltas

Use this for before/after checks when a change may have invalidated old prompt refs or moved important planes.

If a selector no longer resolves against the current STEP topology, `inspect` returns a structured error and exits non-zero.

## Source Of Truth

- `scripts/cadref/cli.py` resolves STEP refs from STEP files and generated selector artifacts.
- Assembly refs resolve from generated assembly STEP files, not from reconstructed Python instance summaries.
- It does not read package-local explorer runtime assets to interpret refs.
