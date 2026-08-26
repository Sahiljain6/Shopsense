const API_URL = (import.meta.env.VITE_API_URL && import.meta.env.VITE_API_URL.trim()) || "https://shopsense-api-pb2g.onrender.com";
const TOKEN_KEY = "shopsense_token";
const PROTECTED_PATHS = ["/chat", "/compare", "/reviews/summary", "/history", "/wishlist"];

class ApiError extends Error {
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
    if (error.status === 0) return `Connection error: ${message}`;
    if (error.status === 400) return `400 validation error: ${message}`;
    if (error.status === 401) return `401 authentication error: ${message}`;
    if (error.status === 403) return `403 authorization error: ${message}`;
    if (error.status === 404) return `404 endpoint not found: ${message}`;
    if (error.status >= 500) return `${error.status} backend/server error: ${message}`;
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

async function apiFetch(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers || {}),
  };
  const token = getToken();
  if (token && PROTECTED_PATHS.some((p) => path.startsWith(p))) {
    headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!response.ok)
      throw new ApiError(response.status, await responseMessage(response));
    return response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        408,
        "The request timed out after 15 seconds. Please try again."
      );
    }
    throw new ApiError(
      0,
      error instanceof Error
        ? error.message
        : "Network request failed. Please try again."
    );
  } finally {
    clearTimeout(timeoutId);
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

export const sendChat = (message, mode, history) =>
  apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message, mode, history }),
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
