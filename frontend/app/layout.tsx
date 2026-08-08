import "./globals.css";
import TopNav from "../components/TopNav";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 font-sans text-slate-950 antialiased">
        <TopNav />
        {children}
      </body>
    </html>
  );
}
