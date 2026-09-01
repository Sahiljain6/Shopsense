const API_URL = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL ? import.meta.env.VITE_API_URL.trim() : null) || "https://shopsense-api-pb2g.onrender.com";
const TOKEN_KEY = "shopsense_token";
const PROTECTED_PATHS = ["/chat", "/compare", "/reviews/summary", "/history", "/wishlist"];

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

  const maxRetries = options.retries ?? 1;
  const onStatusChange = options.onStatusChange;

  let attempt = 0;
  while (attempt <= maxRetries) {
    // 35s on first attempt, 65s on second attempt to accommodate Render free-tier spin-up
    const timeoutMs = attempt === 0 ? 35000 : 65000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      if (attempt > 0 && onStatusChange) {
        onStatusChange("waking");
      }
      const response = await fetch(`${API_URL}${path}`, {
        ...options,
        credentials: "include",
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        // Render free-tier returns 502/503/504 while waking the container
        if (attempt < maxRetries && [502, 503, 504].includes(response.status)) {
          attempt++;
          if (onStatusChange) onStatusChange("waking");
          await new Promise((resolve) => setTimeout(resolve, 3000));
          continue;
        }
        throw new ApiError(response.status, await responseMessage(response));
      }
      return await response.json();
    } catch (error) {
      if (error instanceof ApiError && ![502, 503, 504].includes(error.status)) {
        throw error;
      }
      const isTimeout = error instanceof DOMException && error.name === "AbortError";
      const isNetworkError =
        error instanceof TypeError ||
        error.name === "TypeError" ||
        (error instanceof ApiError && error.status === 0);

      if (
        attempt < maxRetries &&
        (isTimeout || isNetworkError || (error instanceof ApiError && [502, 503, 504].includes(error.status)))
      ) {
        attempt++;
        if (onStatusChange) onStatusChange("waking");
        await new Promise((resolve) => setTimeout(resolve, 2500));
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

export const googleLogin = (credential) =>
  apiFetch("/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });

export const sendChat = (message, mode, history, cart = [], onStatusChange = null, model = "Sonnet 4.5") =>
  apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message, mode, history, cart, model }),
    onStatusChange,
    retries: 1,
  });

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
