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


test("retry pauses cannot stretch a request beyond the total deadline", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response("", { status: 503, statusText: "Unavailable" });
  };

  try {
    await assert.rejects(
      apiFetch("/health", { retries: 1, timeoutMs: 100, totalTimeoutMs: 20 }),
      (error) => error instanceof ApiError && error.status === 408
    );
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});


test("a POST without an idempotency key is never automatically replayed", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new TypeError("simulated network drop");
  };

  try {
    await assert.rejects(
      apiFetch("/wishlist", {
        method: "POST",
        body: JSON.stringify({ product_id: 12 }),
        retries: 2,
        totalTimeoutMs: 1000,
      }),
      (error) => error instanceof ApiError && error.status === 0
    );
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});

test("an idempotent chat POST may safely retry a transient network error", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    if (calls === 1) throw new TypeError("simulated network drop");
    return new Response(JSON.stringify({ answer: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await apiFetch("/chat", {
      method: "POST",
      body: JSON.stringify({ message: "find headphones", idempotency_key: "chat-test-key-001" }),
      retries: 1,
      timeoutMs: 500,
      totalTimeoutMs: 1500,
    });
    assert.equal(result.answer, "ok");
    assert.equal(calls, 2);
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});


test("an idempotency header alone does not enable mutation retries unsupported by the backend", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new TypeError("simulated network drop");
  };

  try {
    await assert.rejects(
      apiFetch("/wishlist", {
        method: "POST",
        headers: { "Idempotency-Key": "header-only-key-001" },
        body: JSON.stringify({ product_id: 12 }),
        retries: 2,
        totalTimeoutMs: 1000,
      }),
      (error) => error instanceof ApiError && error.status === 0
    );
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});


test("a non-chat POST is not retried even if its body contains an idempotency-looking field", async () => {
  const restoreStorage = installLocalStorage();
  const previousFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    throw new TypeError("simulated network drop");
  };

  try {
    await assert.rejects(
      apiFetch("/fetch-link", {
        method: "POST",
        body: JSON.stringify({ url: "https://example.com/product", idempotency_key: "client-only-key-001" }),
        retries: 2,
        totalTimeoutMs: 1000,
      }),
      (error) => error instanceof ApiError && error.status === 0
    );
    assert.equal(calls, 1);
  } finally {
    globalThis.fetch = previousFetch;
    restoreStorage();
  }
});
