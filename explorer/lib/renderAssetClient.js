import { parseDxf } from "./dxf/parseDxf.js";
import { buildMeshDataFromGlbBuffer } from "./render/glbMeshData.js";
import { buildMeshDataFromStlBuffer } from "./render/stlMeshData.js";
import { buildMeshDataFrom3MfBuffer } from "./render/threeMfMeshData.js";

function isObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function fetchError(url, response) {
  return new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
}

const jsonCache = new Map();
const textCache = new Map();
const arrayBufferCache = new Map();
const glbCache = new Map();
const stlCache = new Map();
const threeMfCache = new Map();
const selectorCache = new Map();
const dxfCache = new Map();
const urdfCache = new Map();

async function fetchJson(url, { signal } = {}) {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw fetchError(url, response);
  }
  return response.json();
}

async function fetchText(url, { signal } = {}) {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw fetchError(url, response);
  }
  return response.text();
}

async function fetchArrayBuffer(url, { signal } = {}) {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw fetchError(url, response);
  }
  return response.arrayBuffer();
}

async function loadCached(cache, key, loader, { cachePending = true } = {}) {
  if (!key) {
    throw new Error("Missing asset cache key");
  }
  if (cache.has(key)) {
    const cached = cache.get(key);
    if (cachePending || typeof cached?.then !== "function") {
      return cached;
    }
  }
  if (!cachePending) {
    const payload = await loader();
    cache.set(key, payload);
    return payload;
  }
  let pending;
  pending = loader().catch((error) => {
    if (cache.get(key) === pending) {
      cache.delete(key);
    }
    throw error;
  });
  cache.set(key, pending);
  return pending;
}

function peekCached(cache, key) {
  const value = cache.get(key);
  return value && typeof value.then !== "function" ? value : null;
}

function finalizeCached(cache, key, value) {
  cache.set(key, value);
  return value;
}

export function isAbortError(error) {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function loadRenderJson(url, { signal } = {}) {
  const payload = await loadCached(jsonCache, url, () => fetchJson(url, { signal }), { cachePending: !signal });
  return finalizeCached(jsonCache, url, payload);
}

export function peekRenderJson(url) {
  return peekCached(jsonCache, url);
}

export async function loadRenderText(url, { signal } = {}) {
  const payload = await loadCached(textCache, url, () => fetchText(url, { signal }), { cachePending: !signal });
  return finalizeCached(textCache, url, payload);
}

export function peekRenderText(url) {
  return peekCached(textCache, url);
}

export async function loadRenderArrayBuffer(url, { signal } = {}) {
  const payload = await loadCached(arrayBufferCache, url, () => fetchArrayBuffer(url, { signal }), { cachePending: !signal });
  return finalizeCached(arrayBufferCache, url, payload);
}

export function peekRenderArrayBuffer(url) {
  return peekCached(arrayBufferCache, url);
}

export async function loadRenderGlb(url, { signal } = {}) {
  const meshData = await loadCached(glbCache, url, async () => {
    const buffer = await loadRenderArrayBuffer(url, { signal });
    return buildMeshDataFromGlbBuffer(buffer);
  }, { cachePending: !signal });
  return finalizeCached(glbCache, url, meshData);
}

export function peekRenderGlb(url) {
  return peekCached(glbCache, url);
}

export async function loadRenderStl(url, { signal } = {}) {
  const meshData = await loadCached(stlCache, url, async () => {
    const buffer = await loadRenderArrayBuffer(url, { signal });
    return buildMeshDataFromStlBuffer(buffer);
  }, { cachePending: !signal });
  return finalizeCached(stlCache, url, meshData);
}

export function peekRenderStl(url) {
  return peekCached(stlCache, url);
}

export async function loadRender3Mf(url, { signal } = {}) {
  const meshData = await loadCached(threeMfCache, url, async () => {
    const buffer = await loadRenderArrayBuffer(url, { signal });
    return buildMeshDataFrom3MfBuffer(buffer);
  }, { cachePending: !signal });
  return finalizeCached(threeMfCache, url, meshData);
}

export function peekRender3Mf(url) {
  return peekCached(threeMfCache, url);
}

function buildTypedView(arrayBuffer, view) {
  if (!isObject(view)) {
    return null;
  }
  const count = Number(view.count || 0);
  const offset = Number(view.offset || 0);
  if (!Number.isFinite(count) || count < 0 || !Number.isFinite(offset) || offset < 0) {
    return null;
  }
  if (view.dtype === "float32") {
    return new Float32Array(arrayBuffer, offset, count);
  }
  if (view.dtype === "uint32") {
    return new Uint32Array(arrayBuffer, offset, count);
  }
  return null;
}

function buildSelectorBuffers(manifest, arrayBuffer) {
  const views = manifest?.buffers?.views;
  if (!isObject(views)) {
    return {};
  }
  const output = {};
  for (const [name, view] of Object.entries(views)) {
    const typed = buildTypedView(arrayBuffer, view);
    if (typed) {
      output[name] = typed;
    }
  }
  return output;
}

export async function loadRenderSelectorBundle(manifestUrl, binaryUrl = "", { signal } = {}) {
  const cacheKey = `${manifestUrl}::${binaryUrl}`;
  const bundle = await loadCached(selectorCache, cacheKey, async () => {
    const manifest = await loadRenderJson(manifestUrl, { signal });
    const resolvedBinaryUrl = binaryUrl || (
      typeof manifest?.buffers?.uri === "string" && manifest.buffers.uri
        ? new URL(manifest.buffers.uri, manifestUrl).toString()
        : ""
    );
    if (!resolvedBinaryUrl) {
      return { manifest, buffers: {} };
    }
    if (manifest?.buffers?.littleEndian === false) {
      throw new Error("Big-endian selector buffers are not supported");
    }
    const arrayBuffer = await loadRenderArrayBuffer(resolvedBinaryUrl, { signal });
    return {
      manifest,
      buffers: buildSelectorBuffers(manifest, arrayBuffer),
    };
  }, { cachePending: !signal });
  return finalizeCached(selectorCache, cacheKey, bundle);
}

export function peekRenderSelectorBundle(manifestUrl, binaryUrl = "") {
  return peekCached(selectorCache, `${manifestUrl}::${binaryUrl}`);
}

export async function loadRenderDxf(url, { signal } = {}) {
  const payload = await loadCached(dxfCache, url, async () => {
    const dxfText = await loadRenderText(url, { signal });
    return parseDxf(dxfText, { fileRef: "", sourceUrl: url });
  }, { cachePending: !signal });
  return finalizeCached(dxfCache, url, payload);
}

export function peekRenderDxf(url) {
  return peekCached(dxfCache, url);
}

function urdfCacheKey(url, explorerMetadataUrl = "", motionExplorerMetadataUrl = "") {
  return [url, explorerMetadataUrl, motionExplorerMetadataUrl].filter(Boolean).join("::");
}

export async function loadRenderUrdf(url, { signal, explorerMetadataUrl = "", motionExplorerMetadataUrl = "" } = {}) {
  const cacheKey = urdfCacheKey(url, explorerMetadataUrl, motionExplorerMetadataUrl);
  const payload = await loadCached(urdfCache, cacheKey, async () => {
    const [xmlText, explorerMetadata, motionExplorerMetadata, { parseUrdf }] = await Promise.all([
      loadRenderText(url, { signal }),
      explorerMetadataUrl ? loadRenderJson(explorerMetadataUrl, { signal }) : null,
      motionExplorerMetadataUrl ? loadRenderJson(motionExplorerMetadataUrl, { signal }) : null,
      import("./urdf/parseUrdf.js"),
    ]);
    return parseUrdf(xmlText, { sourceUrl: url, explorerMetadata, motionExplorerMetadata });
  }, { cachePending: !signal });
  return finalizeCached(urdfCache, cacheKey, payload);
}

export function peekRenderUrdf(url, { explorerMetadataUrl = "", motionExplorerMetadataUrl = "" } = {}) {
  return peekCached(urdfCache, urdfCacheKey(url, explorerMetadataUrl, motionExplorerMetadataUrl));
}
