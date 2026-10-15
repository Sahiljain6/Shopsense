import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { streamAIResponse } from "../utils/aiStreamClient.js";

describe("AI Streaming Client Unit Tests", () => {
  it("accumulates SSE data chunks and triggers onToken and onComplete", async () => {
    const tokensReceived = [];
    const mockSSEPayload = [
      'data: {"chunk": "Hello "}\n\n',
      'data: {"chunk": "world"}\n\n',
      'data: {"chunk": "!"}\n\n',
      'data: [DONE]\n\n'
    ].join("");

    // Mock global fetch
    const originalFetch = global.fetch;
    global.fetch = async () => {
      const encoder = new TextEncoder();
      const readable = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(mockSSEPayload));
          controller.close();
        }
      });
      return {
        ok: true,
        body: readable
      };
    };

    try {
      const result = await streamAIResponse({
        url: "/api/test/stream",
        body: { prompt: "hi" },
        onToken: (tok) => tokensReceived.push(tok)
      });

      assert.equal(result, "Hello world!");
      assert.deepEqual(tokensReceived, ["Hello ", "world", "!"]);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it("delivers structured live shopping listings from the SSE event", async () => {
    const liveDealsReceived = [];
    const deal = {
      title: "Wireless Headphones",
      price: 8999,
      image_url: "https://images.example.test/headphones.jpg",
      url: "https://www.amazon.in/dp/B012345678",
      source: "Amazon.in",
      retrieved_at: "2026-10-15T10:00:00Z",
    };
    const mockSSEPayload = [
      `data: ${JSON.stringify({ type: "live_deals", live_deals: [deal] })}\n\n`,
      `data: ${JSON.stringify({ type: "done", response: { answer: "Found a listing", live_deals: [deal] } })}\n\n`,
      "data: [DONE]\n\n",
    ].join("");
    const originalFetch = global.fetch;
    global.fetch = async () => {
      const encoder = new TextEncoder();
      return {
        ok: true,
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode(mockSSEPayload));
            controller.close();
          },
        }),
      };
    };

    try {
      await streamAIResponse({
        url: "/api/test/stream",
        body: { message: "headphones latest price" },
        onLiveDeals: (deals) => liveDealsReceived.push(...deals),
      });
      assert.deepEqual(liveDealsReceived, [deal]);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it("handles AbortController signal gracefully without crashing", async () => {
    const originalFetch = global.fetch;
    const controller = new AbortController();

    global.fetch = async (_, opts) => {
      if (opts?.signal?.aborted) {
        const err = new Error("The operation was aborted.");
        err.name = "AbortError";
        throw err;
      }
      return {
        ok: true,
        body: new ReadableStream({
          start(ctrl) {
            ctrl.close();
          }
        })
      };
    };

    controller.abort();

    try {
      const result = await streamAIResponse({
        url: "/api/test/stream",
        body: { prompt: "hi" },
        signal: controller.signal
      });
      assert.equal(result, "");
    } finally {
      global.fetch = originalFetch;
    }
  });
});
