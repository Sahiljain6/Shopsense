"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = ["/chat", "/history", "/wishlist", "/profile", "/settings", "/admin"];

export default function TopNav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4">
        <Link href="/chat" prefetch={false} className="text-xl font-black tracking-tight text-blue-700">ShopSense</Link>
        <div className="flex flex-wrap gap-2">
          {links.map((href) => {
            const active = pathname === href;
            const label = href.slice(1).replace(/^./, (letter) => letter.toUpperCase());
            return <Link key={href} href={href} prefetch={false} className={`rounded-full px-3 py-2 text-sm font-medium transition ${active ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"}`}>{label}</Link>;
          })}
        </div>
      </div>
    </nav>
  );
}
