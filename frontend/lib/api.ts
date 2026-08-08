const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ChatResponse = {
  answer: string;
  product_ids: number[];
  reasons: Record<string, string>;
  pros: Record<string, string[]>;
  cons: Record<string, string[]>;
  clarification?: string | null;
};
export type Product = {
  id: number;
  name: string;
  brand: string;
  description: string;
  price: number;
  currency: string;
  rating: number;
  stock: number;
  image_url: string;
  attributes: Record<string, unknown>;
  category_id: number;
  category_name?: string | null;
};
export type AuthPayload = { email: string; password: string; full_name?: string };
export type Token = { access_token: string; token_type: string };

const PROTECTED_PATHS = ["/chat", "/compare", "/reviews/summary", "/history", "/wishlist"];

export function getStoredToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("shopsense_token");
}

export function storeToken(token: string) {
  localStorage.setItem("shopsense_token", token);
}

export function clearToken() {
  localStorage.removeItem("shopsense_token");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function responseMessage(res: Response) {
  const text = await res.text();
  if (!text) return res.statusText || "Request failed";
  try {
    const data = JSON.parse(text) as { detail?: string };
    return data.detail || text;
  } catch {
    return text;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token && PROTECTED_PATHS.some((protectedPath) => path.startsWith(protectedPath))) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });
  if (!res.ok) throw new ApiError(res.status, await responseMessage(res));
  return res.json() as Promise<T>;
}

export const login = (payload: AuthPayload) => apiFetch<Token>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
export async function register(payload: AuthPayload) {
  await apiFetch("/auth/register", { method: "POST", body: JSON.stringify(payload) });
  return login({ email: payload.email, password: payload.password });
}
export const sendChat = (message: string, mode?: string | null) => apiFetch<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message, mode }) });
export const getProducts = (q = "", limit = 8) => apiFetch<Product[]>(`/products?q=${encodeURIComponent(q)}&limit=${limit}`);
