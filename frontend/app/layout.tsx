import "./globals.css";
import Link from "next/link";
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en"><body><nav className="flex gap-4 border-b p-4"><Link href="/chat">Chat</Link><Link href="/history">History</Link><Link href="/wishlist">Wishlist</Link><Link href="/profile">Profile</Link><Link href="/settings">Settings</Link><Link href="/admin">Admin</Link></nav>{children}</body></html>; }
