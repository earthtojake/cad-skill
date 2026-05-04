import assert from "node:assert/strict";
import { test } from "node:test";

import { buildMeshDataFromGlbBuffer } from "./glbMeshData.js";

function pad4(buffer, padByte = 0) {
  const padding = (4 - (buffer.length % 4)) % 4;
  return padding ? Buffer.concat([buffer, Buffer.alloc(padding, padByte)]) : buffer;
}

function floatBuffer(values) {
  const buffer = Buffer.alloc(values.length * 4);
  values.forEach((value, index) => buffer.writeFloatLE(value, index * 4));
  return buffer;
}

function uint32Buffer(values) {
  const buffer = Buffer.alloc(values.length * 4);
  values.forEach((value, index) => buffer.writeUInt32LE(value, index * 4));
  return buffer;
}

function makeOccurrenceGlb() {
  const positions = floatBuffer([
    0, 0, 0,
    0.001, 0, 0,
    0, 0.001, 0
  ]);
  const indices = uint32Buffer([0, 1, 2]);
  const binary = pad4(Buffer.concat([positions, indices]));
  const gltf = {
    asset: {
      version: "2.0"
    },
    scenes: [
      {
        nodes: [0]
      }
    ],
    nodes: [
      {
        name: "leaf",
        mesh: 0,
        extras: {
          cadOccurrenceId: "o1.2"
        }
      }
    ],
    meshes: [
      {
        primitives: [
          {
            attributes: {
              POSITION: 0
            },
            indices: 1,
            mode: 4
          }
        ]
      }
    ],
    buffers: [
      {
        byteLength: binary.length
      }
    ],
    bufferViews: [
      {
        buffer: 0,
        byteOffset: 0,
        byteLength: positions.length,
        target: 34962
      },
      {
        buffer: 0,
        byteOffset: positions.length,
        byteLength: indices.length,
        target: 34963
      }
    ],
    accessors: [
      {
        bufferView: 0,
        byteOffset: 0,
        componentType: 5126,
        count: 3,
        type: "VEC3",
        min: [0, 0, 0],
        max: [0.001, 0.001, 0]
      },
      {
        bufferView: 1,
        byteOffset: 0,
        componentType: 5125,
        count: 3,
        type: "SCALAR",
        min: [0],
        max: [2]
      }
    ]
  };
  const json = pad4(Buffer.from(JSON.stringify(gltf), "utf8"), 0x20);
  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + json.length + 8 + binary.length, 8);
  const jsonHeader = Buffer.alloc(8);
  jsonHeader.writeUInt32LE(json.length, 0);
  jsonHeader.writeUInt32LE(0x4e4f534a, 4);
  const binHeader = Buffer.alloc(8);
  binHeader.writeUInt32LE(binary.length, 0);
  binHeader.writeUInt32LE(0x004e4942, 4);
  const glb = Buffer.concat([header, jsonHeader, json, binHeader, binary]);
  return glb.buffer.slice(glb.byteOffset, glb.byteOffset + glb.byteLength);
}

function makeTwoPrimitiveOccurrenceGlb() {
  const positions = floatBuffer([
    0, 0, 0,
    0.001, 0, 0,
    0, 0.001, 0,
    0.002, 0, 0,
    0.003, 0, 0,
    0.002, 0.001, 0
  ]);
  const firstIndices = uint32Buffer([0, 1, 2]);
  const secondIndices = uint32Buffer([3, 4, 5]);
  const binary = pad4(Buffer.concat([positions, firstIndices, secondIndices]));
  const secondIndexOffset = positions.length + firstIndices.length;
  const gltf = {
    asset: {
      version: "2.0"
    },
    scenes: [
      {
        nodes: [0]
      }
    ],
    nodes: [
      {
        name: "leaf",
        mesh: 0,
        extras: {
          cadOccurrenceId: "o1.2"
        }
      }
    ],
    meshes: [
      {
        primitives: [
          {
            attributes: {
              POSITION: 0
            },
            indices: 1,
            material: 0,
            mode: 4
          },
          {
            attributes: {
              POSITION: 0
            },
            indices: 2,
            material: 1,
            mode: 4
          }
        ]
      }
    ],
    materials: [
      {
        pbrMetallicRoughness: {
          baseColorFactor: [1, 0, 0, 1]
        }
      },
      {
        pbrMetallicRoughness: {
          baseColorFactor: [0, 0, 1, 1]
        }
      }
    ],
    buffers: [
      {
        byteLength: binary.length
      }
    ],
    bufferViews: [
      {
        buffer: 0,
        byteOffset: 0,
        byteLength: positions.length,
        target: 34962
      },
      {
        buffer: 0,
        byteOffset: positions.length,
        byteLength: firstIndices.length,
        target: 34963
      },
      {
        buffer: 0,
        byteOffset: secondIndexOffset,
        byteLength: secondIndices.length,
        target: 34963
      }
    ],
    accessors: [
      {
        bufferView: 0,
        byteOffset: 0,
        componentType: 5126,
        count: 6,
        type: "VEC3",
        min: [0, 0, 0],
        max: [0.003, 0.001, 0]
      },
      {
        bufferView: 1,
        byteOffset: 0,
        componentType: 5125,
        count: 3,
        type: "SCALAR",
        min: [0],
        max: [2]
      },
      {
        bufferView: 2,
        byteOffset: 0,
        componentType: 5125,
        count: 3,
        type: "SCALAR",
        min: [3],
        max: [5]
      }
    ]
  };
  const json = pad4(Buffer.from(JSON.stringify(gltf), "utf8"), 0x20);
  const header = Buffer.alloc(12);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + json.length + 8 + binary.length, 8);
  const jsonHeader = Buffer.alloc(8);
  jsonHeader.writeUInt32LE(json.length, 0);
  jsonHeader.writeUInt32LE(0x4e4f534a, 4);
  const binHeader = Buffer.alloc(8);
  binHeader.writeUInt32LE(binary.length, 0);
  binHeader.writeUInt32LE(0x004e4942, 4);
  const glb = Buffer.concat([header, jsonHeader, json, binHeader, binary]);
  return glb.buffer.slice(glb.byteOffset, glb.byteOffset + glb.byteLength);
}

test("GLB mesh data preserves cadOccurrenceId node extras", async () => {
  const meshData = await buildMeshDataFromGlbBuffer(makeOccurrenceGlb());

  assert.equal(meshData.parts.length, 1);
  assert.equal(meshData.parts[0].id, "o1.2");
  assert.equal(meshData.parts[0].occurrenceId, "o1.2");
  assert.equal(meshData.parts[0].primitiveIndex, 0);
  assert.deepEqual(Array.from(meshData.vertices), [
    0, 0, 0,
    1, 0, 0,
    0, 1, 0
  ]);
});

test("GLB mesh data assigns stable primitive indexes per occurrence", async () => {
  const meshData = await buildMeshDataFromGlbBuffer(makeTwoPrimitiveOccurrenceGlb());

  assert.equal(meshData.parts.length, 2);
  assert.deepEqual(meshData.parts.map((part) => part.occurrenceId), ["o1.2", "o1.2"]);
  assert.deepEqual(meshData.parts.map((part) => part.primitiveIndex), [0, 1]);
  assert.deepEqual(meshData.parts.map((part) => part.triangleCount), [1, 1]);
});
