import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, apiFetch } from "../api.js";

function installLocalStorage() {
  const previous = globalThis.localStorage;
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
  return () => {
    if (previous === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = previous;
  };
}

test("an explicit caller abort is not automatically retried", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  const controller = new AbortController();
  let calls = 0;

  globalThis.fetch = (_url, { signal }) => {
    calls += 1;
    if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
    return new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  };

  try {
    const request = apiFetch("/health", {
      signal: controller.signal,
      retries: 1,
      timeoutMs: 500,
      totalTimeoutMs: 1000,
    });
    controller.abort();
    await assert.rejects(request, (error) => error?.name === "AbortError");
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});

test("an attempt timeout returns a bounded 408 error", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  globalThis.fetch = (_url, { signal }) => {
    if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
    return new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
    });
  };

  try {
    await assert.rejects(
      apiFetch("/health", { retries: 0, timeoutMs: 10, totalTimeoutMs: 100 }),
      (error) => error instanceof ApiError && error.status === 408
    );
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});
