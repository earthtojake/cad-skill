import assert from "node:assert/strict";
import { test } from "node:test";

import { buildSelectorRuntime } from "./runtime.js";

test("buildSelectorRuntime remaps source part rows onto an assembly occurrence", () => {
  const bundle = {
    manifest: {
      cadRef: "parts/source",
      tables: {
        occurrenceColumns: ["id", "path", "name", "sourceName", "parentId", "transform", "bbox", "shapeStart", "shapeCount", "faceStart", "faceCount", "edgeStart", "edgeCount", "vertexStart", "vertexCount"],
        shapeColumns: ["id", "occurrenceId", "ordinal", "kind", "bbox", "center", "area", "volume", "faceStart", "faceCount", "edgeStart", "edgeCount", "vertexStart", "vertexCount"],
        faceColumns: ["id", "occurrenceId", "shapeId", "ordinal", "surfaceType", "area", "center", "normal", "bbox", "edgeStart", "edgeCount", "relevance", "flags", "params", "triangleStart", "triangleCount"],
        edgeColumns: ["id", "occurrenceId", "shapeId", "ordinal", "curveType", "length", "center", "bbox", "faceStart", "faceCount", "vertexStart", "vertexCount", "relevance", "flags", "params", "segmentStart", "segmentCount"],
        vertexColumns: ["id", "occurrenceId", "shapeId", "ordinal", "center", "bbox", "edgeStart", "edgeCount", "relevance", "flags"]
      },
      occurrences: [
        ["o1", "1", null, null, null, null, null, 0, 2, 0, 2, 0, 0, 0, 0],
        ["o1.1", "1.1", null, null, "o1", null, null, 0, 1, 0, 1, 0, 0, 0, 0],
        ["o1.2", "1.2", null, null, "o1", null, null, 1, 1, 1, 1, 0, 0, 0, 0]
      ],
      shapes: [
        ["o1.1.s1", "o1.1", 1, "solid", null, null, 1, 1, 0, 1, 0, 0, 0, 0],
        ["o1.2.s1", "o1.2", 1, "solid", null, null, 1, 1, 1, 1, 0, 0, 0, 0]
      ],
      faces: [
        ["o1.1.f1", "o1.1", "o1.1.s1", 1, "plane", 1, [0, 0, 0], [0, 0, 1], null, 0, 0, 0, 0, {}, 0, 0],
        ["o1.2.f1", "o1.2", "o1.2.s1", 1, "plane", 1, [1, 0, 0], [0, 0, 1], null, 0, 0, 0, 0, {}, 0, 0]
      ],
      edges: [],
      vertices: []
    },
    buffers: {}
  };

  const runtime = buildSelectorRuntime(bundle, {
    copyCadPath: "parts/root",
    partId: "o1.5",
    remapOccurrenceId: "o1.5"
  });
  const faces = runtime.references.filter((reference) => reference.selectorType === "face");

  assert.deepEqual(faces.map((reference) => reference.displaySelector), ["o1.5.f1", "o1.5.f2"]);
  assert.equal(faces[1].copyText, "@cad[parts/root#o1.5.f2] plane area=1");
});
