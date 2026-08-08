const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export type ChatResponse = { answer: string; product_ids: number[]; reasons: Record<string,string>; pros: Record<string,string[]>; cons: Record<string,string[]>; clarification?: string | null };
export type Product = { id: number; name: string; brand: string; description: string; price: number; currency: string; rating: number; stock: number; image_url: string; attributes: Record<string, unknown>; category_id: number; category_name?: string | null };
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> { const res = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } }); if (!res.ok) throw new Error(await res.text()); return res.json() as Promise<T>; }
export const sendChat = (message: string, mode?: string | null) => apiFetch<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message, mode }) });
export const getProducts = (q = "", limit = 8) => apiFetch<Product[]>(`/products?q=${encodeURIComponent(q)}&limit=${limit}`);
