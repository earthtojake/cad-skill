# CAD Geometry Workflow

Use this reference before making nontrivial CAD edits.

## Geometry Contract

Convert the prompt into a short geometry contract:

1. Resolve relevant `@cad[...]` refs into geometry facts when the prompt depends on specific faces, edges, bodies, corners, or occurrences.
2. Separate refs into target refs that should move, extend, align, or be removed and protected refs that must remain unchanged.
3. Record concrete invariants to validate after the edit:
   - exact plane alignment targets
   - expected clearances or offsets
   - spans or extents that must remain continuous
   - connectivity expectations such as solid count or preserved rails/walls
4. Decide whether the change is fundamentally a 2D profile/sketch edit or a 3D volumetric edit.

## Implementation Bias

- Prefer sketch/profile edits when the requested change is planar or profile-like.
- Use late 3D booleans only when the request is truly volumetric.
- Do not silently keep the largest solid after a boolean unless the design explicitly expects multiple solids and you are intentionally choosing one.
- After topology-changing operations such as boolean splits, large cuts, same-domain unifies, fillets, or chamfers, rebuild and re-resolve refs before using old face or edge ordinals again.
- After the user accepts a design-direction change, clean out dead helpers, constants, and workaround branches that only served the discarded approach.

## Edit Loop

1. Start with the narrowest source-only search that can identify directly affected files.
2. Exclude generated artifacts, binary CAD files, caches, and build outputs from default searches unless the task explicitly targets them.
3. Edit the owning generator or imported STEP source first.
4. Regenerate explicit targets only. Name every source you want to regenerate.
5. Run validation appropriate to the change before finishing.

Run a generator script directly only for focused debugging when you explicitly do not need the split generation tools to refresh render artifacts.

Do not run generation tools, `cadref`, and `snapshot` in parallel against geometry that is still changing in the same edit loop. Rebuild first, then inspect, then render.

## Validation Depth

Match validation depth to risk:

- Simple part edits: generator assertions, key dimensions or bounds, solid count, and targeted `@cad[...]` resolution when relevant.
- Fit or assembly edits: placement assertions plus interference or clearance checks.
- Complex topology, broad shape edits, or orientation-dependent changes: add visual review with `snapshot`.
- Before/after selector or topology checks: use `cadref diff`.
- Major plane identification: use `cadref planes`.

Use the cheapest check that can prove correctness, then escalate only if that check fails or the change affects shared behavior, geometry, or public interfaces.
