'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';

type Role = 'assistant' | 'user';
type Message = { role: Role; content: string };
type Product = {
  name: string;
  category: string;
  price: string;
  why: string;
  link: string;
};

type ChatbotConfig = {
  apiKey?: string;
  model?: string;
  endpoint?: string;
};

declare global {
  interface Window {
    SHOP_SENSE_CHATBOT_CONFIG?: ChatbotConfig;
  }
}

const starterPrompts = [
  'Find comfortable running shoes under $120 for daily training',
  'Compare noise cancelling headphones for travel',
  'Build a skincare routine for oily skin under $80',
  'Suggest gifts for a tech lover around $50',
];

const fallbackProducts: Product[] = [
  {
    name: 'Smart comparison shortlist',
    category: 'Shopping plan',
    price: 'Custom budget',
    why: 'I can turn your needs into must-have specs, nice-to-have features, and search keywords.',
    link: 'https://www.google.com/search?q=best+products+shopping+guide',
  },
  {
    name: 'Deal safety checklist',
    category: 'Buyer protection',
    price: 'Free',
    why: 'Use seller ratings, return windows, warranty terms, and total delivered price before buying.',
    link: 'https://www.consumer.ftc.gov/',
  },
  {
    name: 'Value score method',
    category: 'Decision helper',
    price: 'Free',
    why: 'Score every option on fit, quality, reviews, price, and return policy to avoid impulse buys.',
    link: 'https://www.google.com/search?q=product+reviews',
  },
];

const systemPrompt = `You are ShopSense, a practical shopping assistant. Help users choose products by asking clarifying questions only when required. When enough detail is available, recommend 3-5 options or search phrases, compare trade-offs, mention budget fit, warn about common pitfalls, and end with a short buying checklist. Do not claim live prices or stock unless the user provides them.`;

function parseProducts(text: string, query: string): Product[] {
  const lines = text.split('\n').filter((line) => /\$|under|best|recommend|option|pick|buy/i.test(line));
  const products = lines.slice(0, 3).map((line, index) => ({
    name: line.replace(/^[-*\d.\s]+/, '').slice(0, 70) || `Recommended option ${index + 1}`,
    category: 'AI recommendation',
    price: 'Check latest price',
    why: 'Matched to your shopping request. Verify reviews, warranty, seller, and return policy before purchase.',
    link: `https://www.google.com/search?q=${encodeURIComponent(`${query} ${line}`)}`,
  }));

  return products.length ? products : fallbackProducts;
}

function offlineAnswer(query: string) {
  return `I can help you shop for “${query || 'your next product'}”.\n\nTo choose well, compare these points:\n1. Budget: set a hard maximum and include shipping or accessories.\n2. Must-have features: list the 2-3 features you cannot compromise on.\n3. Quality signals: prefer strong recent reviews, clear warranty, and a seller with easy returns.\n4. Value: avoid paying extra for features you will not use.\n\nPaste your API key in frontend/public/chatbot-config.js to enable live AI answers on GitHub Pages. Until then, tell me your budget, product type, preferred brands, and any deal-breakers, and I will structure a shortlist for you.`;
}

async function askOpenAI(messages: Message[], query: string) {
  const config = window.SHOP_SENSE_CHATBOT_CONFIG || {};
  const apiKey = config.apiKey?.trim();

  if (!apiKey || apiKey.includes('PASTE_YOUR')) {
    return offlineAnswer(query);
  }

  const response = await fetch(config.endpoint || 'https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: config.model || 'gpt-4o-mini',
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages.map((message) => ({ role: message.role, content: message.content })),
        { role: 'user', content: query },
      ],
      temperature: 0.4,
    }),
  });

  if (!response.ok) {
    throw new Error(`AI request failed: ${response.status} ${await response.text()}`);
  }

  const data = await response.json();
  return data.choices?.[0]?.message?.content?.trim() || 'I could not generate a shopping answer. Try adding more product details.';
}

export default function ChatPage() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hi! I am your ShopSense shopping bot. Tell me what you want to buy, your budget, and what matters most.',
    },
  ]);
  const [products, setProducts] = useState<Product[]>(fallbackProducts);
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const hasApiKey = useMemo(() => {
    if (typeof window === 'undefined') return false;
    const key = window.SHOP_SENSE_CHATBOT_CONFIG?.apiKey?.trim();
    return Boolean(key && !key.includes('PASTE_YOUR'));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setInput('');
    setLoading(true);
    const previousMessages = messages;
    setMessages((current) => [...current, { role: 'user', content: query }]);

    try {
      const answer = await askOpenAI(previousMessages, query);
      setMessages((current) => [...current, { role: 'assistant', content: answer }]);
      setProducts(parseProducts(answer, query));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Something went wrong.';
      setMessages((current) => [...current, { role: 'assistant', content: `I could not contact the AI service. ${message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto grid min-h-[calc(100vh-64px)] max-w-7xl gap-6 p-4 lg:grid-cols-[360px_1fr]">
      <aside className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 shadow-2xl">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-indigo-300">Shopping Copilot</p>
        <h1 className="mt-3 text-3xl font-bold">Buy smarter with an AI chat bot</h1>
        <p className="mt-3 text-sm text-slate-300">Ask for product picks, comparisons, gift ideas, budget trade-offs, or a buying checklist.</p>
        <div className="mt-5 rounded-2xl bg-slate-950 p-4 text-sm text-slate-300">
          <p className="font-semibold text-slate-100">API key setup</p>
          <p className="mt-2">Paste your key in <code className="rounded bg-slate-800 px-1">frontend/public/chatbot-config.js</code>.</p>
          <p className="mt-2 text-xs text-amber-200">GitHub Pages is public, so use a restricted key or a backend proxy for production.</p>
          <p className="mt-3">Status: <span className={hasApiKey ? 'text-emerald-300' : 'text-amber-300'}>{hasApiKey ? 'AI key detected' : 'Offline demo mode'}</span></p>
        </div>
        <div className="mt-5 space-y-2">
          {starterPrompts.map((prompt) => (
            <button key={prompt} onClick={() => setInput(prompt)} className="w-full rounded-xl border border-slate-700 p-3 text-left text-sm hover:border-indigo-400">
              {prompt}
            </button>
          ))}
        </div>
      </aside>

      <section className="flex min-h-[680px] flex-col rounded-3xl border border-slate-800 bg-slate-900 p-4 shadow-2xl">
        <div className="flex-1 space-y-4 overflow-y-auto rounded-2xl bg-slate-950 p-4">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`max-w-3xl whitespace-pre-wrap rounded-2xl p-4 ${message.role === 'user' ? 'ml-auto bg-indigo-600' : 'bg-slate-800'}`}>
              {message.content}
            </div>
          ))}
          {loading && <div className="rounded-2xl bg-slate-800 p-4 text-slate-300">ShopSense is comparing options…</div>}
          <div ref={chatEndRef} />
        </div>

        <form onSubmit={sendMessage} className="mt-4 flex gap-2">
          <input className="flex-1 rounded-2xl bg-slate-800 p-4 outline-none ring-indigo-500 focus:ring-2" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Example: Best budget phone under $400 with great camera" />
          <button disabled={loading || !input.trim()} className="rounded-2xl bg-indigo-500 px-6 font-semibold disabled:opacity-50">Send</button>
        </form>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {products.map((product) => (
            <a key={product.name} href={product.link} target="_blank" rel="noreferrer" className="rounded-2xl border border-slate-800 bg-slate-950 p-4 hover:border-indigo-400">
              <p className="text-xs uppercase tracking-wide text-indigo-300">{product.category}</p>
              <h3 className="mt-2 font-semibold">{product.name}</h3>
              <p className="mt-2 text-sm text-emerald-300">{product.price}</p>
              <p className="mt-2 text-sm text-slate-400">{product.why}</p>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}
