import type { Metadata } from "next";
import "./globals.css";
import { AppNav } from "@/components/AppNav";

export const metadata: Metadata = {
  title: "Prism — Investment Research Intelligence",
  description: "Prism decomposes market complexity into clear research, valuation, and strategy workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen flex-col bg-[var(--bg)] text-[var(--t1)] antialiased">
        <AppNav />
        <main className="flex-1 overflow-hidden">{children}</main>
      </body>
    </html>
  );
}
