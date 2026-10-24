import { streamAIResponse } from "./utils/aiStreamClient.js";

const API_URL = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL ? import.meta.env.VITE_API_URL.trim() : null) || "https://shopsense-api-pb2g.onrender.com";
const TOKEN_KEY = "shopsense_token";
const PROTECTED_PATHS = ["/chat", "/chat/stream", "/compare", "/reviews/summary", "/history", "/wishlist"];

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function friendlyError(error) {
  if (error instanceof ApiError) {
    const message = error.message || "Request failed";
    if (error.status === 0) return `Connection notice: ${message}. The server may be waking up — please try sending again.`;
    if (error.status === 408) return `Server wake-up notice: ${message}`;
    if (error.status === 400) return `Validation error: ${message}`;
    if (error.status === 401) return `Authentication error: ${message}`;
    if (error.status === 403) return `Authorization error: ${message}`;
    if (error.status === 404) return `Endpoint not found: ${message}`;
    if (error.status === 422) return `Registration error: ${message}`;
    if (error.status >= 500) return `Server error (${error.status}): ${message}`;
    return `${error.status}: ${message}`;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

async function responseMessage(response) {
  const text = await response.text();
  if (!text) return response.statusText || "Request failed";
  try {
    const data = JSON.parse(text);
    // Handle Pydantic v2 validation errors: detail is an array of {loc, msg, type}
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((e) => {
          const field = e.loc ? e.loc.slice(1).join(".") : "field";
          return `${field}: ${e.msg}`;
        })
        .join("; ");
    }
    return data.detail || data.message || text;
  } catch {
    return text;
  }
}

function getCsrfToken() {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function hasIdempotencyKey(_headers, body) {
  // Only the backend's durable ChatRequest JSON field currently guarantees a
  // replay-safe mutation. Do not infer idempotency from an arbitrary header.
  if (typeof body !== "string") return false;
  try {
    const payload = JSON.parse(body);
    return typeof payload?.idempotency_key === "string" && payload.idempotency_key.trim().length >= 8;
  } catch {
    return false;
  }
}

function computeRetryDelayMs(attempt, response, deadlineAt) {
  const jitterCap = Math.min(5000, 250 * (2 ** Math.min(Math.max(0, attempt), 5)));
  let delayMs = Math.floor(Math.random() * (jitterCap + 1));
  const retryAfter = response?.headers?.get?.("Retry-After");
  if (retryAfter) {
    const seconds = Number(retryAfter);
    const retryAfterMs = Number.isFinite(seconds)
      ? Math.max(0, seconds * 1000)
      : Math.max(0, Date.parse(retryAfter) - Date.now());
    if (Number.isFinite(retryAfterMs)) delayMs = Math.max(delayMs, retryAfterMs);
  }
  return Math.min(delayMs, Math.max(0, deadlineAt - Date.now()));
}

function waitForRetry(delayMs, signal) {
  if (signal?.aborted) return Promise.reject(new DOMException("Request aborted", "AbortError"));
  if (delayMs <= 0) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const cleanup = () => signal?.removeEventListener("abort", onAbort);
    const timer = setTimeout(() => {
      cleanup();
      resolve();
    }, delayMs);
    const onAbort = () => {
      clearTimeout(timer);
      cleanup();
      reject(new DOMException("Request aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function apiFetch(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    "X-Client-Platform": "Web/Vite",
    "X-Client-Version": "1.0.0",
    ...(options.headers || {}),
  };
  const token = getToken();
  if (token && PROTECTED_PATHS.some((p) => path.startsWith(p))) {
    headers.Authorization = `Bearer ${token}`;
  }

  const method = (options.method || "GET").toUpperCase();
  const isStateChanging = ["POST", "PUT", "DELETE", "PATCH"].includes(method);
  const csrfToken = getCsrfToken();
  if (isStateChanging && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const {
    retries: retryCount,
    onStatusChange,
    timeoutMs: attemptTimeoutOverride,
    totalTimeoutMs: totalTimeoutOverride,
    signal: callerSignal,
    ...fetchOptions
  } = options;
  const requestedRetries = Math.min(3, Math.max(0, Number(retryCount ?? 1) || 0));
  // Never automatically replay a mutation unless it carries an idempotency key.
  const retrySafeMethod = ["GET", "HEAD", "OPTIONS"].includes(method);
  const chatEndpoint = path === "/chat" || path.startsWith("/chat/");
  const retryAllowed = retrySafeMethod || (chatEndpoint && hasIdempotencyKey(headers, fetchOptions.body));
  const maxRetries = retryAllowed ? requestedRetries : 0;
  // Keep the existing 35s/65s wake-up windows, but prevent retries from stacking
  // beyond one overall budget. Callers can lower either budget for short endpoints.
  const totalTimeoutMs = Math.max(1, Number(totalTimeoutOverride ?? 105000) || 105000);
  const deadlineAt = Date.now() + totalTimeoutMs;
  const totalTimeoutMessage = "The request exceeded its overall time budget. Please try again.";

  let attempt = 0;
  while (attempt <= maxRetries) {
    const remainingMs = deadlineAt - Date.now();
    if (remainingMs <= 0) throw new ApiError(408, totalTimeoutMessage);

    // Preserve the Render wake-up allowance unless the overall deadline is closer.
    const attemptDefaultMs = attempt === 0 ? 35000 : 65000;
    const configuredAttemptMs = Number(attemptTimeoutOverride ?? attemptDefaultMs) || attemptDefaultMs;
    const timeoutMs = Math.max(1, Math.min(configuredAttemptMs, remainingMs));
    const controller = new AbortController();
    let timedOut = false;
    const abortFromCaller = () => controller.abort(callerSignal?.reason);
    if (callerSignal) {
      if (callerSignal.aborted) abortFromCaller();
      else callerSignal.addEventListener("abort", abortFromCaller, { once: true });
    }
    const timeoutId = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    try {
      if (attempt > 0 && onStatusChange) {
        onStatusChange("waking");
      }
      const response = await fetch(`${API_URL}${path}`, {
        ...fetchOptions,
        credentials: "include",
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        // Retry only transient server/provider responses; unsafe mutations have maxRetries=0.
        const retryableStatuses = [408, 425, 429, 500, 502, 503, 504];
        if (attempt < maxRetries && retryableStatuses.includes(response.status)) {
          attempt++;
          if (onStatusChange) onStatusChange("waking");
          try { await response.body?.cancel(); } catch { /* best-effort connection cleanup */ }
          const retryDelay = computeRetryDelayMs(attempt - 1, response, deadlineAt);
          if (retryDelay > 0) await waitForRetry(retryDelay, callerSignal);
          continue;
        }
        if (response.status === 401) {
          clearToken();
          if (typeof window !== "undefined") {
            window.dispatchEvent(new Event("auth-expired"));
          }
        }
        throw new ApiError(response.status, await responseMessage(response));
      }
      return await response.json();
    } catch (error) {
      // A UI-initiated abort is intentional and must not trigger an automatic retry.
      if (callerSignal?.aborted) throw error;
      if (error instanceof ApiError && ![408, 425, 429, 500, 502, 503, 504].includes(error.status)) {
        throw error;
      }
      const isTimeout = timedOut || (error instanceof DOMException && error.name === "AbortError");
      const isNetworkError =
        error instanceof TypeError ||
        error.name === "TypeError" ||
        (error instanceof ApiError && error.status === 0);

      if (
        attempt < maxRetries &&
        (isTimeout || isNetworkError || (error instanceof ApiError && [408, 425, 429, 500, 502, 503, 504].includes(error.status)))
      ) {
        attempt++;
        if (onStatusChange) onStatusChange("waking");
        const retryDelay = computeRetryDelayMs(attempt - 1, null, deadlineAt);
        if (retryDelay > 0) await waitForRetry(retryDelay, callerSignal);
        continue;
      }

      if (error instanceof ApiError) throw error;
      if (isTimeout) {
        throw new ApiError(
          408,
          "The server took longer than expected to respond. It may still be waking up — please try again in a moment."
        );
      }
      throw new ApiError(
        0,
        error instanceof Error
          ? error.message
          : "Network request failed. Please check your connection."
      );
    } finally {
      clearTimeout(timeoutId);
      if (callerSignal) callerSignal.removeEventListener("abort", abortFromCaller);
    }
  }
}

export const login = (payload) =>
  apiFetch("/auth/login", { method: "POST", body: JSON.stringify(payload) });

export async function register(payload) {
  await apiFetch("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return login({ email: payload.email, password: payload.password });
}

export const googleLogin = (credentialOrPayload) => {
  const payload =
    typeof credentialOrPayload === "string"
      ? { credential: credentialOrPayload }
      : credentialOrPayload;
  return apiFetch("/auth/google", {
    method: "POST",
    body: JSON.stringify(payload),
  });
};

export function createIdempotencyKey() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `shopsense-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`.slice(0, 128);
}

export async function sendChat(
  message, mode, history, cart = [], onStatusChange = null, model = "Sonnet 4.5", idempotencyKey = null
) {
  let inProgressRetries = 0;
  while (true) {
    try {
      return await apiFetch("/chat", {
        method: "POST",
        body: JSON.stringify({
          message, mode, history, cart, model,
          ...(idempotencyKey ? { idempotency_key: idempotencyKey } : {}),
        }),
        onStatusChange,
        retries: 1,
      });
    } catch (error) {
      // The SSE request may still be finishing after a network disconnect.
      // Wait for that exact operation to complete instead of triggering another LLM call.
      if (
        idempotencyKey &&
        error instanceof ApiError &&
        error.status === 409 &&
        /already processing/i.test(String(error.message)) &&
        inProgressRetries < 12
      ) {
        inProgressRetries += 1;
        await new Promise((resolve) => setTimeout(resolve, 1000));
        continue;
      }
      throw error;
    }
  }
}

export async function streamChat({
  message,
  mode,
  history = [],
  cart = [],
  model = "Sonnet 4.5",
  idempotencyKey,
  signal,
  onToken,
  onStatus,
  onProducts,
  onLiveDeals,
  onComplete,
  onError,
}) {
  const token = getToken();
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "X-Client-Platform": "Web/Vite",
    "X-Client-Version": "1.0.0",
  };
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  return streamAIResponse({
    url: `${API_URL}/chat/stream`,
    headers,
    body: { message, mode, history, cart, model, ...(idempotencyKey ? { idempotency_key: idempotencyKey } : {}) },
    signal,
    onToken,
    onStatus,
    onProducts,
    onLiveDeals,
    onComplete,
    onError,
  });
}

export const fetchLink = (url) =>
  apiFetch("/fetch-link", { method: "POST", body: JSON.stringify({ url }) });

export const fetchPriceHistory = (productId) =>
  apiFetch(`/products/${productId}/price-history`);

export const identifyImage = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/identify-image", { method: "POST", body: formData });
};

export const getProducts = (q = "", limit = 8) =>
  apiFetch(`/products?q=${encodeURIComponent(q)}&limit=${limit}`);

export const logout = () =>
  apiFetch("/auth/logout", { method: "POST" });

export const refreshToken = () =>
  apiFetch("/auth/refresh", { method: "POST" });
