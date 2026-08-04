export type Product = { id:number; name:string; brand:string; price:number; currency:string; rating:number; stock:number; image_url:string; description:string };
const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export async function chat(message: string): Promise<{answer:string; products:Product[]; clarification?:string}> { const r = await fetch(`${API}/chat`, { method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({message}) }); if(!r.ok) throw new Error('Chat failed'); return r.json(); }
export async function products(q=''): Promise<Product[]> { const r = await fetch(`${API}/products?q=${encodeURIComponent(q)}`); if(!r.ok) throw new Error('Products failed'); return r.json(); }
