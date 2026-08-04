import './globals.css';
import Link from 'next/link';
import type { Metadata } from 'next';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export const metadata: Metadata = { title: 'ShopSense', description: 'AI powered conversational shopping assistant' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <script src={`${basePath}/chatbot-config.js`} defer></script>
        <nav className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 p-4 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <Link href="/" className="text-xl font-bold">ShopSense</Link>
            <div className="flex gap-4 text-sm">
              <Link href="/chat">Chat</Link>
              <Link href="/history">History</Link>
              <Link href="/wishlist">Wishlist</Link>
              <Link href="/profile">Profile</Link>
              <Link href="/settings">Settings</Link>
              <Link href="/admin">Admin</Link>
            </div>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
