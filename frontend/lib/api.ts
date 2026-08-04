export type Product={id:number;category_id:number;name:string;brand:string;price:number;currency:string;rating:number;stock:number;image_url:string;description:string;attributes?:Record<string,unknown>};
const API=process.env.NEXT_PUBLIC_API_URL??'http://localhost:8000';
export const token=()=>typeof window==='undefined'?'':localStorage.getItem('token')||'';
async function req<T>(path:string,init:RequestInit={}):Promise<T>{const h=new Headers(init.headers);h.set('content-type','application/json');const t=token();if(t)h.set('authorization',`Bearer ${t}`);const r=await fetch(`${API}${path}`,{...init,headers:h});if(!r.ok)throw new Error(await r.text());return r.json();}
export const login=(email:string,password:string)=>req<{access_token:string}>('/login',{method:'POST',body:JSON.stringify({email,password})});
export const register=(email:string,password:string,full_name:string)=>req<{access_token:string}>('/register',{method:'POST',body:JSON.stringify({email,password,full_name})});
export const chat=(message:string)=>req<{answer:string;products:Product[];clarification?:string}>('/chat',{method:'POST',body:JSON.stringify({message})});
export const products=(q='')=>req<Product[]>(`/products?q=${encodeURIComponent(q)}`);
export const wishlist=()=>req<Product[]>('/wishlist');
export const saveWishlist=(product_id:number)=>req<{saved:boolean}>('/wishlist',{method:'POST',body:JSON.stringify({product_id})});
export const history=()=>req<Array<{id:number;role:string;content:string;created_at:string}>>('/history');
export const compare=(product_ids:number[])=>req<{products:any[];winner:string;recommendation:string}>('/compare',{method:'POST',body:JSON.stringify({product_ids})});
export const reviewSummary=(product_id:number)=>req<any>('/reviews/summary',{method:'POST',body:JSON.stringify({product_id})});
export const analytics=()=>req<Record<string,number>>('/admin/analytics');
