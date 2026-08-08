"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, ChatResponse, getProducts, getStoredToken, login, Product, register, sendChat, storeToken } from "../lib/api";
import ChatBubble from "./ChatBubble";
import ClarificationPrompt from "./ClarificationPrompt";
import ModifierToggle from "./ModifierToggle";
import ProductCard from "./ProductCard";

type Message = { role: "user" | "assistant"; text: string; response?: ChatResponse; products?: Product[] };

function friendlyError(error: unknown) {
  if (error instanceof ApiError) return error.status === 401 ? "401: Session expired, please log in again." : `${error.status}: ${error.message}`;
  return error instanceof Error ? error.message : "Something went wrong.";
}

function AuthForm({ onAuthed }: { onAuthed: () => void }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null); setLoading(true);
    try {
      const token = isRegister ? await register({ email, password, full_name: fullName }) : await login({ email, password });
      storeToken(token.access_token); onAuthed();
    } catch (err) { setError(friendlyError(err)); } finally { setLoading(false); }
  }
  return (
    <section className="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
      <h1 className="text-3xl font-bold text-slate-950">Welcome to ShopSense</h1>
      <p className="mt-2 text-sm text-slate-600">Log in or create an account before chatting with your shopping assistant.</p>
      {error && <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
      <form onSubmit={submit} className="mt-6 space-y-4">
        {isRegister && <input className="w-full rounded-xl border border-slate-200 px-4 py-3" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" />}
        <input className="w-full rounded-xl border border-slate-200 px-4 py-3" value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="Email" required />
        <input className="w-full rounded-xl border border-slate-200 px-4 py-3" value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password" required />
        <button disabled={loading} className="w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:bg-blue-300">{loading ? "Please wait..." : isRegister ? "Create account" : "Log in"}</button>
      </form>
      <button className="mt-4 text-sm font-medium text-blue-700" onClick={() => setIsRegister((value) => !value)}>{isRegister ? "Already have an account? Log in" : "Need an account? Register"}</button>
    </section>
  );
}

export default function ChatWindow() {
  const [authed, setAuthed] = useState(false);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const checkedAuthRef = useRef(false);

  useEffect(() => {
    if (checkedAuthRef.current) return;
    checkedAuthRef.current = true;

    const hasToken = Boolean(getStoredToken());
    setAuthed((current) => (current === hasToken ? current : hasToken));
  }, []);

  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages.length, loading]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput(""); setError(null); setLoading(true);
    setMessages((current) => [...current, { role: "user", text }]);
    try {
      const response = await sendChat(text, mode);
      const allProducts = response.product_ids.length ? await getProducts(text, 12) : [];
      const products = allProducts.filter((product) => response.product_ids.includes(product.id));
      setMessages((current) => [...current, { role: "assistant", text: response.answer, response, products }]);
    } catch (err) { setError(friendlyError(err)); } finally { setLoading(false); }
  }

  if (!authed) return <main className="min-h-[calc(100vh-73px)] bg-slate-50 px-4 py-12"><AuthForm onAuthed={() => setAuthed(true)} /></main>;
  return (
    <section className="mx-auto flex h-[calc(100vh-97px)] max-w-5xl flex-col px-4 py-6">
      <div className="mb-4 rounded-3xl bg-gradient-to-r from-blue-600 to-indigo-600 p-6 text-white shadow-lg">
        <h1 className="text-3xl font-bold">ShopSense assistant</h1>
        <p className="mt-2 text-blue-50">Ask for recommendations, comparisons, gifts, or budget-friendly picks.</p>
      </div>
      <ModifierToggle mode={mode} setMode={setMode} />
      {error && <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-700">{error}</div>}
      <div className="mt-4 flex-1 space-y-5 overflow-y-auto rounded-3xl border border-slate-200 bg-slate-100/70 p-4">
        {messages.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-slate-500">Try “recommend a budget phone under 15000”.</div>}
        {messages.map((message, index) => <div key={index} className="space-y-3"><ChatBubble role={message.role} text={message.text} />{message.response?.clarification && <ClarificationPrompt text={message.response.clarification} />}{Boolean(message.products?.length) && <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{message.products?.map((product) => <ProductCard key={product.id} product={product} chat={message.response} />)}</div>}</div>)}
        {loading && <div className="mr-auto inline-flex rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">ShopSense is typing…</div>}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={submit} className="mt-4 flex gap-3">
        <input className="flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm outline-none focus:border-blue-400 focus:ring-4 focus:ring-blue-100" value={input} onChange={(e) => setInput(e.target.value)} placeholder="recommend a budget phone under 15000" />
        <button disabled={loading || !input.trim()} className="rounded-2xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:bg-blue-300">{loading ? "Sending…" : "Send"}</button>
      </form>
    </section>
  );
}
