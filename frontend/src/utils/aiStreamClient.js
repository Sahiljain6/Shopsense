let streamMetricSequence = 0;

/**
 * Emits privacy-safe User Timing entries for DevTools. These marks contain no
 * prompt text, tokens, account identifiers, or credentials.
 */
function createStreamLatencyMetrics() {
  if (typeof performance === "undefined" || typeof performance.mark !== "function") {
    return { responseReceived() {}, firstToken() {}, complete() {} };
  }

  const id = ++streamMetricSequence;
  const prefix = `shopsense-chat-${id}`;
  const marks = {
    start: `${prefix}-request-start`,
    response: `${prefix}-response-headers`,
    firstToken: `${prefix}-first-token`,
    complete: `${prefix}-complete`,
  };
  let responseMarked = false;
  let firstTokenMarked = false;
  let completed = false;

  const mark = (name) => {
    try {
      performance.mark(name);
      return true;
    } catch {
      return false;
    }
  };

  const measure = (name, start, end) => {
    try {
      if (start && end) performance.measure(name, start, end);
    } catch {
      // Timing telemetry must never affect chat delivery.
    }
  };

  mark(marks.start);

  return {
    responseReceived() {
      if (responseMarked) return;
      responseMarked = mark(marks.response);
    },
    firstToken() {
      if (firstTokenMarked) return;
      firstTokenMarked = mark(marks.firstToken);
    },
    complete() {
      if (completed) return;
      completed = true;
      mark(marks.complete);
      measure(`${prefix} total request duration`, marks.start, marks.complete);
      measure(`${prefix} time to response headers`, marks.start, marks.response);
      measure(`${prefix} time to first token`, marks.start, marks.firstToken);
    },
  };
}

/**
 * Production-ready AI Streaming Response Handler.
 * Consumes Server-Sent Events (SSE) or chunked HTTP transfer streams with
 * low-latency token dispatch, error recovery, and AbortController cancellation.
 */

/**
 * Streams an LLM response from an API endpoint.
 *
 * @param {Object} options
 * @param {string} options.url - The API endpoint URL.
 * @param {Object} [options.headers] - Additional HTTP headers (e.g. auth tokens).
 * @param {Object} options.body - Payload (messages, model configuration).
 * @param {AbortSignal} [options.signal] - Signal for instant stream cancellation.
 * @param {(chunk: string) => void} options.onToken - Callback fired for each streamed token/delta.
 * @param {(data: any) => void} [options.onToolCall] - Callback fired when a tool-calling event arrives.
 * @param {(fullText: string) => void} [options.onComplete] - Callback fired upon stream completion.
 * @param {(error: Error) => void} [options.onError] - Callback fired if an error occurs.
 * @returns {Promise<string>} Full accumulated response text.
 */
export async function streamAIResponse({
  url,
  headers = {},
  body,
  signal,
  timeoutMs = 105000,
  maxResponseChars = 1000000,
  maxEventBufferChars = 262144,
  onToken,
  onStatus,
  onProducts,
  onLiveDeals,
  onToolCall,
  onDoneMetadata,
  onComplete,
  onError
}) {
  let accumulatedText = "";
  let fullResponseMeta = null;
  const latencyMetrics = createStreamLatencyMetrics();
  const boundedTimeoutMs = Math.max(1, Number(timeoutMs) || 105000);
  const responseCharLimit = Math.min(5000000, Math.max(1, Number(maxResponseChars) || 1000000));
  const eventBufferLimit = Math.min(1048576, Math.max(1024, Number(maxEventBufferChars) || 262144));
  let activeReader = null;
  const appendToken = (token) => {
    const chunk = typeof token === "string" ? token : String(token ?? "");
    if (accumulatedText.length + chunk.length > responseCharLimit) {
      const limitError = new Error("The AI response exceeded the configured size limit.");
      limitError.name = "ResponseLimitError";
      throw limitError;
    }
    accumulatedText += chunk;
    return chunk;
  };
  const requestController = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => requestController.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) abortFromCaller();
    else signal.addEventListener("abort", abortFromCaller, { once: true });
  }
  const timeoutId = setTimeout(() => {
    timedOut = true;
    requestController.abort();
  }, boundedTimeoutMs);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream, application/json",
        ...headers
      },
      body: JSON.stringify(body),
      signal: requestController.signal
    });
    latencyMetrics.responseReceived();

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      throw new Error(`AI Gateway Error (${response.status}): ${errorText || response.statusText}`);
    }

    if (!response.body) {
      throw new Error("ReadableStream not supported by response");
    }

    const reader = response.body.getReader();
    activeReader = reader;
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Retain the last incomplete fragment in the buffer and bound individual SSE events.
      buffer = lines.pop() || "";
      if (buffer.length > eventBufferLimit) {
        const limitError = new Error("The AI stream contained an oversized event.");
        limitError.name = "ResponseLimitError";
        throw limitError;
      }

      for (const line of lines) {
        if (line.length > eventBufferLimit) {
          const limitError = new Error("The AI stream contained an oversized event.");
          limitError.name = "ResponseLimitError";
          throw limitError;
        }
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(":")) continue; // Skip comments/keep-alives

        if (trimmed.startsWith("data:")) {
          const rawData = trimmed.replace(/^data:\s*/, "");
          if (rawData === "[DONE]") {
            latencyMetrics.complete();
            if (onComplete) onComplete(accumulatedText, fullResponseMeta);
            return accumulatedText;
          }

          try {
            const parsed = JSON.parse(rawData);

            if (parsed.type === "status" && parsed.status) {
              if (onStatus) onStatus(parsed.status);
              continue;
            }

            if (parsed.type === "products") {
              if (onProducts) onProducts(parsed.products || [], parsed.product_ids || []);
              continue;
            }

            if (parsed.type === "live_deals") {
              if (onLiveDeals) onLiveDeals(parsed.live_deals || []);
              continue;
            }

            if (parsed.type === "done" && parsed.response) {
              fullResponseMeta = parsed.response;
              if (onDoneMetadata) onDoneMetadata(parsed.response);
              continue;
            }

            // Handle tool-call streaming event
            if (parsed.type === "tool_call" || parsed.tool_calls) {
              if (onToolCall) onToolCall(parsed);
              continue;
            }

            // Extract token from common LLM response formats (OpenAI, Anthropic, Gemini, Vercel AI SDK)
            const token =
              parsed.token ||
              parsed.choices?.[0]?.delta?.content ||
              parsed.candidates?.[0]?.content?.parts?.[0]?.text ||
              parsed.delta?.text ||
              parsed.chunk ||
              parsed.text ||
              "";

            if (token) {
              latencyMetrics.firstToken();
              const safeToken = appendToken(token);
              if (onToken) onToken(safeToken);
            }
          } catch (parseError) {
            if (parseError?.name === "ResponseLimitError") throw parseError;
            // Raw text fallback if payload is not JSON
            latencyMetrics.firstToken();
            const safeToken = appendToken(rawData);
            if (onToken) onToken(safeToken);
          }
        }
      }
    }

    // Flush any remaining buffer text
    if (buffer.trim().startsWith("data:")) {
      const rawData = buffer.trim().replace(/^data:\s*/, "");
      if (rawData !== "[DONE]") {
        latencyMetrics.firstToken();
        const safeToken = appendToken(rawData);
        if (onToken) onToken(safeToken);
      }
    }

    latencyMetrics.complete();
    if (onComplete) {
      onComplete(accumulatedText);
    }

    return accumulatedText;
  } catch (error) {
    latencyMetrics.complete();
    if (timedOut) {
      const timeoutError = new Error("The AI response exceeded its overall request budget. Please try again.");
      timeoutError.name = "TimeoutError";
      if (onError) onError(timeoutError);
      throw timeoutError;
    }
    if (signal?.aborted || error?.name === "AbortError") {
      // A caller/UI abort is intentional; do not turn it into an automatic retry.
      if (onComplete) onComplete(accumulatedText);
      return accumulatedText;
    }
    if (onError) {
      onError(error);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    if (signal) signal.removeEventListener("abort", abortFromCaller);
    if (activeReader) {
      try { await activeReader.cancel(); } catch { /* Reader may already be closed or cancelled. */ }
      try { activeReader.releaseLock(); } catch { /* Reader lock may already be released. */ }
    }
  }
}
