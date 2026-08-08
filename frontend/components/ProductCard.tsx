import type { ChatResponse, Product } from "../lib/api";

function list(items?: string[]) {
  if (!items?.length) return null;
  return <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-slate-600">{items.map((item) => <li key={item}>{item}</li>)}</ul>;
}

export default function ProductCard({ product, chat }: { product: Product; chat?: ChatResponse }) {
  const key = String(product.id);
  const price = new Intl.NumberFormat("en-IN", { style: "currency", currency: product.currency || "INR", maximumFractionDigits: 0 }).format(product.price);
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="h-36 bg-slate-100">
        {product.image_url ? <img src={product.image_url} alt={product.name} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-sm text-slate-400">No image</div>}
      </div>
      <div className="space-y-3 p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-blue-600">{product.brand}</p>
          <h3 className="font-semibold text-slate-950">{product.name}</h3>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-lg font-bold text-slate-950">{price}</span>
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${product.stock > 0 ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>{product.stock > 0 ? "In stock" : "Out of stock"}</span>
        </div>
        <p className="text-sm text-amber-500">{"★".repeat(Math.round(product.rating))}<span className="text-slate-400"> ({product.rating}/5)</span></p>
        {chat?.reasons?.[key] && <p className="rounded-xl bg-blue-50 p-3 text-sm text-blue-900">{chat.reasons[key]}</p>}
        {list(chat?.pros?.[key])}
        {list(chat?.cons?.[key])}
      </div>
    </article>
  );
}
