import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: 'ShopSense', description: 'AI powered conversational shopping assistant' };
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en" className="dark"><body>{children}</body></html>; }
