import assert from "node:assert/strict";
import test from "node:test";

import { loadRenderJson } from "./renderAssetClient.js";

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
