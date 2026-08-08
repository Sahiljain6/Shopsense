"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  ChatResponse,
  Product,
  clearToken,
  getProducts,
  getStoredToken,
  login,
  register,
  sendChat,
  storeToken,
} from "../lib/api";

type Role = "user" | "assistant";
type Message = { role: Role; text: string; response?: ChatResponse | null; products?: Product[] };
type Mode = "compare" | "budget_optimizer" | "gift_mode" | "quick_answer";

const modifiers: { id: Mode; label: string }[] = [
  { id: "compare", label: "Compare" },
  { id: "budget_optimizer", label: "Budget" },
  { id: "gift_mode", label: "Gift" },
  { id: "quick_answer", label: "Quick answer" },
];

function friendlyError(error: unknown) {
  if (error instanceof ApiError) {
    return error.status === 401 ? "401: Session expired. Please log in again." : `${error.status}: ${error.message}`;
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function productKey(product: Product) {
  return String(product.id);
}

export default function ChatApp() {
  const [authed, setAuthed] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const checkedRef = useRef(false);

  useEffect(() => {
    if (checkedRef.current) return;
    checkedRef.current = true;
    setAuthed(Boolean(getStoredToken()));
  }, []);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setAuthLoading(true);
    try {
      const token = isRegister
        ? await register({ email, password, full_name: fullName || undefined })
        : await login({ email, password });
      storeToken(token.access_token);
      setAuthed(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setAuthLoading(false);
    }
  }

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || chatLoading) return;

    setInput("");
    setError(null);
    setChatLoading(true);
    setMessages((current) => [...current, { role: "user", text }]);

    try {
      const response = await sendChat(text, mode);
      const ids = Array.isArray(response.product_ids) ? response.product_ids : [];
      const allProducts = ids.length ? await getProducts(text, 12) : [];
      const products = Array.isArray(allProducts) ? allProducts.filter((product) => ids.includes(product.id)) : [];
      setMessages((current) => [...current, { role: "assistant", text: response.answer || "I found a few options.", response, products }]);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setChatLoading(false);
    }
  }

  function logout() {
    clearToken();
    setAuthed(false);
    setMessages([]);
    setError(null);
  }

  function renderProductCard(product: Product, response?: ChatResponse | null) {
    const key = productKey(product);
    const pros = Array.isArray(response?.pros?.[key]) ? response?.pros?.[key] : [];
    const cons = Array.isArray(response?.cons?.[key]) ? response?.cons?.[key] : [];
    return (
      <article key={product.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {product.image_url ? <img src={product.image_url} alt="" className="h-36 w-full object-cover" /> : null}
        <div className="space-y-3 p-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">{product.brand || product.category_name || "ShopSense"}</p>
            <h3 className="text-lg font-bold text-slate-950">{product.name || "Recommended product"}</h3>
          </div>
          <p className="line-clamp-3 text-sm text-slate-600">{product.description || "No description available."}</p>
          <div className="flex items-center justify-between text-sm">
            <span className="font-bold text-slate-950">{product.currency || "$"}{product.price}</span>
            <span className="text-amber-600">★ {product.rating || "N/A"}</span>
          </div>
          {response?.reasons?.[key] ? <p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-900">{response.reasons[key]}</p> : null}
          {pros.length ? <p className="text-xs text-emerald-700">Pros: {pros.join(", ")}</p> : null}
          {cons.length ? <p className="text-xs text-rose-700">Cons: {cons.join(", ")}</p> : null}
        </div>
      </article>
    );
  }

  function renderMessage(message: Message, index: number) {
    if (!message || (message.role !== "user" && message.role !== "assistant")) {
      return <div key={index} className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">Couldn&apos;t display this message.</div>;
    }
    const products = Array.isArray(message.products) ? message.products : [];
    return (
      <div key={index} className="space-y-3">
        <div className={`max-w-3xl rounded-2xl px-4 py-3 shadow-sm ${message.role === "user" ? "ml-auto bg-blue-600 text-white" : "mr-auto border border-slate-200 bg-white text-slate-800"}`}>
          <p className="whitespace-pre-wrap text-sm leading-6">{message.text || "Couldn’t display this message."}</p>
        </div>
        {message.response?.clarification ? <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{message.response.clarification}</div> : null}
        {products.length ? <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{products.map((product) => renderProductCard(product, message.response))}</div> : null}
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-950">
      <section className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-5xl flex-col">
        <header className="rounded-3xl bg-gradient-to-r from-blue-600 to-indigo-600 p-6 text-white shadow-lg">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-100">ShopSense</p>
              <h1 className="mt-2 text-3xl font-black">Lightweight shopping assistant</h1>
              <p className="mt-2 max-w-2xl text-blue-50">Ask for recommendations, comparisons, gifts, or budget-friendly picks.</p>
            </div>
            {authed ? <button onClick={logout} className="rounded-xl bg-white/15 px-4 py-2 text-sm font-semibold text-white hover:bg-white/25">Log out</button> : null}
          </div>
        </header>

        {error ? <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-700">{error}</div> : null}

        {!authed ? (
          <section className="mx-auto mt-10 w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
            <h2 className="text-2xl font-bold">{isRegister ? "Create your account" : "Log in to continue"}</h2>
            <form onSubmit={submitAuth} className="mt-6 space-y-4">
              {isRegister ? <input className="w-full rounded-xl border border-slate-200 px-4 py-3" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Full name" /> : null}
              <input className="w-full rounded-xl border border-slate-200 px-4 py-3" value={email} onChange={(event) => setEmail(event.target.value)} type="email" placeholder="Email" required />
              <input className="w-full rounded-xl border border-slate-200 px-4 py-3" value={password} onChange={(event) => setPassword(event.target.value)} type="password" placeholder="Password" required />
              <button disabled={authLoading} className="w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:bg-blue-300">{authLoading ? "Please wait…" : isRegister ? "Register" : "Log in"}</button>
            </form>
            <button className="mt-4 text-sm font-semibold text-blue-700" onClick={() => setIsRegister((value) => !value)}>{isRegister ? "Already have an account? Log in" : "Need an account? Register"}</button>
          </section>
        ) : (
          <>
            <div className="mt-4 flex flex-wrap gap-2">{modifiers.map((item) => <button key={item.id} onClick={() => setMode((current) => current === item.id ? null : item.id)} className={`rounded-full border px-4 py-2 text-sm font-semibold ${mode === item.id ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-700"}`}>{item.label}</button>)}</div>
            <div className="mt-4 flex-1 space-y-5 overflow-y-auto rounded-3xl border border-slate-200 bg-slate-100/70 p-4">
              {!Array.isArray(messages) || messages.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-slate-500">Try “recommend a budget phone under 15000”.</div> : messages.map(renderMessage)}
              {chatLoading ? <div className="mr-auto inline-flex rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">ShopSense is typing…</div> : null}
            </div>
            <form onSubmit={submitChat} className="mt-4 flex gap-3">
              <input className="flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100" value={input} onChange={(event) => setInput(event.target.value)} placeholder="recommend a budget phone under 15000" />
              <button disabled={chatLoading || !input.trim()} className="rounded-2xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:bg-blue-300">{chatLoading ? "Sending…" : "Send"}</button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}
