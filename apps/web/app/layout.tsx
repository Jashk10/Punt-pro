import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Moneyball",
  description: "Multi-sport tipping & simulation platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-terminal-bg font-mono text-sm">{children}</body>
    </html>
  );
}
