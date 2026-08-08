import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShopSense",
  description: "A lightweight shopping assistant demo.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
