import assert from "node:assert/strict";
import test from "node:test";

import { loadRenderJson, loadRenderSelectorBundle, loadRenderTopologyIndex } from "./renderAssetClient.js";

function pad4(buffer, byte = 0) {
  const padding = (4 - (buffer.length % 4)) % 4;
  return padding ? Buffer.concat([buffer, Buffer.alloc(padding, byte)]) : buffer;
}

function topologyGlb(manifest, buffers = {}) {
  const bufferViews = [];
  let binary = Buffer.alloc(0);
  function addBufferView(payload) {
    binary = pad4(binary);
    const byteOffset = binary.length;
    binary = Buffer.concat([binary, payload]);
    const index = bufferViews.length;
    bufferViews.push({ buffer: 0, byteOffset, byteLength: payload.length });
    return index;
  }

  const selectorManifest = JSON.parse(JSON.stringify(manifest));
  selectorManifest.schemaVersion = 1;
  selectorManifest.profile = "selector";
  selectorManifest.buffers = { littleEndian: true, views: {} };
  for (const [name, { dtype, payload, count, itemSize }] of Object.entries(buffers)) {
    selectorManifest.buffers.views[name] = {
      dtype,
      bufferView: addBufferView(payload),
      byteOffset: 0,
      byteLength: payload.length,
      count,
      itemSize,
    };
  }
  const indexManifest = {
    schemaVersion: 1,
    profile: "index",
    entryKind: manifest.entryKind || "part",
    cadRef: manifest.cadRef,
    stats: manifest.stats || {},
    tables: manifest.tables?.occurrenceColumns ? { occurrenceColumns: manifest.tables.occurrenceColumns } : {},
    occurrences: manifest.occurrences || [],
    ...(manifest.assembly ? { assembly: manifest.assembly } : {}),
  };
  const indexView = addBufferView(Buffer.from(JSON.stringify(indexManifest), "utf8"));
  const selectorView = addBufferView(Buffer.from(JSON.stringify(selectorManifest), "utf8"));
  binary = pad4(binary);
  const gltf = {
    asset: { version: "2.0" },
    buffers: [{ byteLength: binary.length }],
    bufferViews,
    extensionsUsed: ["STEP_topology"],
    extensions: {
      STEP_topology: {
        schemaVersion: 1,
        entryKind: indexManifest.entryKind,
        indexView,
        selectorView,
        encoding: "utf-8",
      },
    },
  };
  const jsonChunk = pad4(Buffer.from(JSON.stringify(gltf), "utf8"), 0x20);
  const header = Buffer.alloc(12);
  const jsonHeader = Buffer.alloc(8);
  const binHeader = Buffer.alloc(8);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(12 + 8 + jsonChunk.length + 8 + binary.length, 8);
  jsonHeader.writeUInt32LE(jsonChunk.length, 0);
  jsonHeader.write("JSON", 4, "latin1");
  binHeader.writeUInt32LE(binary.length, 0);
  binHeader.write("BIN\0", 4, "latin1");
  return Buffer.concat([header, jsonHeader, jsonChunk, binHeader, binary]);
}

function abortError() {
  return new DOMException("The operation was aborted.", "AbortError");
}

test("abortable loads do not reuse a stale pending cache entry", async (t) => {
  const originalFetch = globalThis.fetch;
  const requests = [];
  const url = `/asset-${Date.now()}-${Math.random()}.json`;

  globalThis.fetch = async (requestUrl, { signal } = {}) => new Promise((resolve, reject) => {
    const request = { requestUrl, resolve, reject, signal };
    requests.push(request);
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    signal?.addEventListener("abort", () => reject(abortError()), { once: true });
  });

  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const firstController = new AbortController();
  const firstLoad = loadRenderJson(url, { signal: firstController.signal });
  assert.equal(requests.length, 1);

  firstController.abort();

  const secondController = new AbortController();
  const secondLoad = loadRenderJson(url, { signal: secondController.signal });
  assert.equal(requests.length, 2);

  requests[1].resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));

  await assert.rejects(firstLoad, { name: "AbortError" });
  assert.deepEqual(await secondLoad, { ok: true });
});

test("selector bundles decode STEP_topology bufferViews from GLB", async (t) => {
  const originalFetch = globalThis.fetch;
  const glbUrl = `/topology-${Date.now()}-${Math.random()}.glb`;
  const edgeIds = Buffer.alloc(8);
  edgeIds.writeUInt32LE(7, 0);
  edgeIds.writeUInt32LE(11, 4);
  const requests = [];
  const glb = topologyGlb(
    { cadRef: "fixtures/box", tables: {}, occurrences: [], shapes: [], faces: [], edges: [] },
    { edgeIds: { dtype: "uint32", payload: edgeIds, count: 2, itemSize: 4 } }
  );

  globalThis.fetch = async (requestUrl) => {
    requests.push(String(requestUrl));
    assert.equal(String(requestUrl), glbUrl);
    return new Response(glb, { status: 200 });
  };

  t.after(() => {
    globalThis.fetch = originalFetch;
  });

  const bundle = await loadRenderSelectorBundle(glbUrl);
  assert.deepEqual(Array.from(bundle.buffers.edgeIds), [7, 11]);
  assert.equal((await loadRenderTopologyIndex(glbUrl)).cadRef, "fixtures/box");
  assert.deepEqual(requests, [glbUrl]);
});
