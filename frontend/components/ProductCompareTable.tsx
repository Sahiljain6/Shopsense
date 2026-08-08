import type { Product } from "../lib/api";
export default function ProductCompareTable({ products }: { products: Product[] }) { return <table className="w-full bg-white"><tbody>{products.map((p) => <tr key={p.id} className="border"><td className="p-2">{p.name}</td><td className="p-2">{p.currency} {p.price}</td><td className="p-2">{p.rating}/5</td></tr>)}</tbody></table>; }
