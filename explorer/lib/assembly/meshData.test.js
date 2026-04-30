import assert from "node:assert/strict";
import { test } from "node:test";

import {
  assemblyBreadcrumb,
  assemblyCompositionMeshRequests,
  buildAssemblyLeafToNodePickMap,
  buildAssemblyMeshData,
  descendantLeafPartIds,
  findAssemblyNode,
  flattenAssemblyNodes,
  flattenAssemblyLeafParts,
  leafPartIdsForAssemblySelection,
  representativeAssemblyLeafPartId
} from "./meshData.js";

test("buildAssemblyMeshData composes source meshes with assembly transforms", () => {
  const sourceMesh = {
    vertices: new Float32Array([
      0, 0, 0,
      1, 0, 0,
      0, 1, 0
    ]),
    normals: new Float32Array([
      0, 0, 1,
      0, 0, 1,
      0, 0, 1
    ]),
    indices: new Uint32Array([0, 1, 2]),
    bounds: {
      min: [0, 0, 0],
      max: [1, 1, 0]
    }
  };
  const topology = {
    assembly: {
      root: {
        id: "root",
        nodeType: "assembly",
        children: [
          {
            id: "o1.2",
            occurrenceId: "o1.2",
            nodeType: "part",
            displayName: "sample_part",
            sourcePath: "parts/sample_part.step",
            worldTransform: [
              1, 0, 0, 10,
              0, 1, 0, 20,
              0, 0, 1, 30,
              0, 0, 0, 1
            ],
            children: []
          }
        ]
      }
    }
  };

  const meshData = buildAssemblyMeshData(
    topology,
    new Map([["parts/sample_part.step", sourceMesh]])
  );

  assert.deepEqual(Array.from(meshData.vertices), [
    10, 20, 30,
    11, 20, 30,
    10, 21, 30
  ]);
  assert.deepEqual(Array.from(meshData.indices), [0, 1, 2]);
  assert.equal(meshData.parts.length, 1);
  assert.equal(meshData.parts[0].id, "o1.2");
  assert.equal(meshData.parts[0].partSourcePath, "parts/sample_part.step");
  assert.deepEqual(meshData.parts[0].bounds, {
    min: [10, 20, 30],
    max: [11, 21, 30]
  });
});

test("buildAssemblyMeshData can suppress source colors per assembly part", () => {
  const coloredMesh = {
    vertices: new Float32Array([
      0, 0, 0,
      1, 0, 0,
      0, 1, 0
    ]),
    normals: new Float32Array([
      0, 0, 1,
      0, 0, 1,
      0, 0, 1
    ]),
    colors: new Float32Array([
      0.25, 0.5, 0.75,
      0.25, 0.5, 0.75,
      0.25, 0.5, 0.75
    ]),
    indices: new Uint32Array([0, 1, 2]),
    bounds: {
      min: [0, 0, 0],
      max: [1, 1, 0]
    },
    has_source_colors: true
  };
  const topology = {
    assembly: {
      root: {
        id: "root",
        nodeType: "assembly",
        children: [
          {
            id: "default_part",
            occurrenceId: "default_part",
            nodeType: "part",
            sourcePath: "parts/default.step",
            useSourceColors: false,
            children: []
          },
          {
            id: "colored_part",
            occurrenceId: "colored_part",
            nodeType: "part",
            sourcePath: "parts/colored.step",
            children: []
          }
        ]
      }
    }
  };

  const meshData = buildAssemblyMeshData(
    topology,
    new Map([
      ["parts/default.step", coloredMesh],
      ["parts/colored.step", coloredMesh]
    ])
  );

  assert.equal(meshData.has_source_colors, true);
  assert.equal(meshData.parts[0].hasSourceColors, false);
  assert.equal(meshData.parts[1].hasSourceColors, true);
  assert.deepEqual(Array.from(meshData.colors.slice(0, 9)), [1, 1, 1, 1, 1, 1, 1, 1, 1]);
  assert.deepEqual(Array.from(meshData.colors.slice(9, 18)), [0.25, 0.5, 0.75, 0.25, 0.5, 0.75, 0.25, 0.5, 0.75]);
});

test("assemblyCompositionMeshRequests supports native component meshes", () => {
  const topology = {
    assembly: {
      root: {
        id: "root",
        nodeType: "assembly",
        children: [
          {
            id: "o1.1",
            occurrenceId: "o1.1",
            nodeType: "part",
            assets: {
              glb: {
                url: "/workspace/imports/.assembly.step/components/o1.1.glb?v=abc",
                hash: "abc"
              }
            },
            children: []
          },
          {
            id: "o1.2",
            nodeType: "part",
            sourcePath: "parts/sample_part.step",
            children: []
          }
        ]
      }
    }
  };

  assert.deepEqual(assemblyCompositionMeshRequests(topology), [
    {
      key: "o1.1",
      sourcePath: "",
      meshUrl: "/workspace/imports/.assembly.step/components/o1.1.glb?v=abc"
    },
    {
      key: "parts/sample_part.step",
      sourcePath: "parts/sample_part.step",
      meshUrl: ""
    }
  ]);
});

test("assemblyCompositionMeshRequests de-duplicates repeated source meshes", () => {
  const topology = {
    assembly: {
      root: {
        id: "root",
        nodeType: "assembly",
        children: [
          {
            id: "o1.1",
            nodeType: "part",
            sourcePath: "parts/reused.step",
            children: []
          },
          {
            id: "o1.2",
            nodeType: "part",
            sourcePath: "parts/reused.step",
            assets: {
              glb: {
                url: "components/reused.glb?v=abc"
              }
            },
            children: []
          }
        ]
      }
    }
  };

  assert.deepEqual(assemblyCompositionMeshRequests(topology), [
    {
      key: "parts/reused.step",
      sourcePath: "parts/reused.step",
      meshUrl: "components/reused.glb?v=abc"
    }
  ]);
});

test("buildAssemblyMeshData composes native component meshes by occurrence id", () => {
  const sourceMesh = {
    vertices: new Float32Array([
      0, 0, 0,
      2, 0, 0,
      0, 2, 0
    ]),
    normals: new Float32Array([
      0, 0, 1,
      0, 0, 1,
      0, 0, 1
    ]),
    indices: new Uint32Array([0, 1, 2]),
    bounds: {
      min: [0, 0, 0],
      max: [2, 2, 0]
    }
  };
  const topology = {
    assembly: {
      mode: "native",
      root: {
        id: "root",
        nodeType: "assembly",
        children: [
          {
            id: "o1.1",
            occurrenceId: "o1.1",
            nodeType: "part",
            displayName: "sample_component",
            worldTransform: [
              1, 0, 0, 3,
              0, 1, 0, 4,
              0, 0, 1, 5,
              0, 0, 0, 1
            ],
            children: []
          }
        ]
      }
    }
  };

  const meshData = buildAssemblyMeshData(
    topology,
    new Map([["o1.1", sourceMesh]])
  );

  assert.deepEqual(Array.from(meshData.vertices), [
    3, 4, 5,
    5, 4, 5,
    3, 6, 5
  ]);
  assert.equal(meshData.parts[0].partSourcePath, "");
  assert.equal(meshData.parts[0].label, "sample_component");
});

test("assembly helpers navigate nested assemblies down to leaf parts", () => {
  const root = {
    id: "root",
    nodeType: "assembly",
    displayName: "sample_root",
    children: [
      {
        id: "sample_module",
        nodeType: "assembly",
        displayName: "sample_module",
        children: [
          {
            id: "sample_part",
            nodeType: "part",
            displayName: "sample_part",
            children: []
          }
        ]
      }
    ]
  };

  assert.deepEqual(flattenAssemblyLeafParts(root).map((part) => part.id), ["sample_part"]);
  assert.deepEqual(flattenAssemblyNodes(root).map((node) => node.id), ["root", "sample_module", "sample_part"]);
  assert.equal(findAssemblyNode(root, "sample_module")?.displayName, "sample_module");
  assert.deepEqual(assemblyBreadcrumb(root, "sample_part").map((node) => node.id), ["root", "sample_module", "sample_part"]);
  assert.deepEqual(descendantLeafPartIds(root.children[0]), ["sample_part"]);
  assert.equal(representativeAssemblyLeafPartId(root.children[0]), "sample_part");
});

test("assembly mesh requests and picking maps use only descendant leaves", () => {
  const root = {
    id: "root",
    nodeType: "assembly",
    children: [
      {
        id: "module",
        occurrenceId: "o1.1",
        nodeType: "assembly",
        leafPartIds: ["leaf_a", "leaf_b"],
        children: [
          {
            id: "leaf_a",
            occurrenceId: "o1.1.1",
            nodeType: "part",
            sourcePath: "parts/a.step",
            children: []
          },
          {
            id: "leaf_b",
            occurrenceId: "o1.1.2",
            nodeType: "part",
            assets: {
              glb: {
                url: "components/o1.1.2.glb?v=abc"
              }
            },
            children: []
          }
        ]
      }
    ]
  };
  const topology = {
    assembly: {
      root
    }
  };

  assert.deepEqual(assemblyCompositionMeshRequests(topology), [
    {
      key: "parts/a.step",
      sourcePath: "parts/a.step",
      meshUrl: ""
    },
    {
      key: "leaf_b",
      sourcePath: "",
      meshUrl: "components/o1.1.2.glb?v=abc"
    }
  ]);
  assert.deepEqual(
    [...buildAssemblyLeafToNodePickMap(root.children).entries()],
    [
      ["leaf_a", "module"],
      ["leaf_b", "module"]
    ]
  );
  const assemblyPartMap = new Map(flattenAssemblyNodes(root).map((node) => [node.id, node]));
  assert.deepEqual(
    leafPartIdsForAssemblySelection("module", {
      assemblyPartMap,
      fallbackPartId: "leaf_a",
      validLeafPartIds: ["leaf_a", "leaf_b"]
    }),
    ["leaf_a", "leaf_b"]
  );
  assert.deepEqual(
    leafPartIdsForAssemblySelection("leaf_a", {
      assemblyPartMap,
      validLeafPartIds: ["leaf_a", "leaf_b"]
    }),
    ["leaf_a"]
  );
  assert.deepEqual(
    leafPartIdsForAssemblySelection("missing", {
      assemblyPartMap,
      fallbackPartId: "leaf_b",
      validLeafPartIds: ["leaf_a", "leaf_b"]
    }),
    ["leaf_b"]
  );
  assert.equal(representativeAssemblyLeafPartId(root.children[0]), "leaf_a");
});
