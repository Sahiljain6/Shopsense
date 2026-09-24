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
  onToken,
  onToolCall,
  onComplete,
  onError
}) {
  let accumulatedText = "";

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream, application/json",
        ...headers
      },
      body: JSON.stringify(body),
      signal
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      throw new Error(`AI Gateway Error (${response.status}): ${errorText || response.statusText}`);
    }

    if (!response.body) {
      throw new Error("ReadableStream not supported by response");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Retain the last incomplete fragment in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(":")) continue; // Skip comments/keep-alives

        if (trimmed.startsWith("data:")) {
          const rawData = trimmed.replace(/^data:\s*/, "");
          if (rawData === "[DONE]") {
            if (onComplete) onComplete(accumulatedText);
            return accumulatedText;
          }

          try {
            const parsed = JSON.parse(rawData);

            // Handle tool-call streaming event
            if (parsed.type === "tool_call" || parsed.tool_calls) {
              if (onToolCall) onToolCall(parsed);
              continue;
            }

            // Extract token from common LLM response formats (OpenAI, Anthropic, Gemini, Vercel AI SDK)
            const token =
              parsed.choices?.[0]?.delta?.content ||
              parsed.candidates?.[0]?.content?.parts?.[0]?.text ||
              parsed.delta?.text ||
              parsed.chunk ||
              parsed.text ||
              "";

            if (token) {
              accumulatedText += token;
              if (onToken) onToken(token);
            }
          } catch {
            // Raw text fallback if payload is not JSON
            accumulatedText += rawData;
            if (onToken) onToken(rawData);
          }
        }
      }
    }

    // Flush any remaining buffer text
    if (buffer.trim().startsWith("data:")) {
      const rawData = buffer.trim().replace(/^data:\s*/, "");
      if (rawData !== "[DONE]") {
        accumulatedText += rawData;
        if (onToken) onToken(rawData);
      }
    }

    if (onComplete) {
      onComplete(accumulatedText);
    }

    return accumulatedText;
  } catch (error) {
    if (error.name === "AbortError") {
      // User explicitly stopped generation; do not surface as uncaught fault
      if (onComplete) onComplete(accumulatedText);
      return accumulatedText;
    }
    if (onError) {
      onError(error);
    }
    throw error;
  }
}
