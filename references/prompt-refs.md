# CAD Prompt References

Use this reference when prompts include `@cad[...]` handles, annotated screenshots, or both.

## Prompt Artifacts

Prompts may contain:

1. Annotated images
2. `@cad[...]` references

Treat them as complementary. Annotated images provide intent, orientation, and region of interest; they are not source of truth. `@cad[...]` references are stable prompt handles. If an image and a ref disagree, trust the ref and source STEP data, then use the image to understand intent.

## Token Rules

- Parse the leading `@cad[...]` token on each line as the reference. Descriptive prose after the token is not part of the identifier.
- Whole STEP file: `@cad[<cad-path>]`
- Occurrence: `@cad[<cad-path>#o1.2]`
- Body/shape selector: `@cad[<cad-path>#o1.2.s3]`
- Face, edge, and corner selectors: `@cad[<cad-path>#o1.2.f12]`, `@cad[<cad-path>#o1.2.e7]`, `@cad[<cad-path>#o1.2.v4]`
- Compact single-occurrence aliases: `@cad[<cad-path>#s3]`, `@cad[<cad-path>#f12]`, `@cad[<cad-path>#e7]`, `@cad[<cad-path>#v4]`
- Grouped same-occurrence selectors: `@cad[<cad-path>#o1.2.f12,f13,e7,v4]`

Supported selectors are `o<path>`, `o<path>.s<n>`, `o<path>.f<n>`, `o<path>.e<n>`, `o<path>.v<n>`, plus compact single-occurrence aliases `s<n>`, `f<n>`, `e<n>`, and `v<n>`.

`<cad-path>` is a path without the `.step` or `.stp` suffix, relative to the active CAD workspace root, for example `@cad[path/to/example]`.

## Resolution Workflow

- Resolve refs with `scripts/cadref/cli.py inspect`.
- For complex edits, resolve selected face/edge/corner refs into geometry facts before editing with `--detail --facts`.
- Treat topology ordinals as handles, not semantic feature definitions.
- Use `cadref planes <cad-path or @cad[...]> --json` to find major coplanar plane groups instead of inferring plate or wall faces from screenshots.
- Use `cadref diff <left-entry-or-ref> <right-entry-or-ref> --json` for before/after comparison instead of manually eyeballing topology sidecars.

Do not inspect explorer-derived runtime assets to figure out what a ref means. Resolve refs from STEP source data and deterministic generated selector artifacts.

## Stale Refs

In a normal agent workflow, assume one thread is focused on one CAD entry at a time and humans are not manually editing geometry out of band.

If the thread changes referenced geometry, regenerate the affected CAD output and any needed derived reference data before relying on old refs again.

After topology-changing steps, rebuild and re-resolve old face or edge ordinals before using them again.

Unknown selectors may be treated as opaque explorer-generated handles unless the task is to change the reference system itself.

If you need to change how refs are generated, expanded, copied, or rendered, read the explorer documentation for the host project.
