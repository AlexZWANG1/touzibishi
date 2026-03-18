import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IRIS - Investment Research Intelligence System",
  description: "AI-powered investment research automation platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[var(--iris-bg)] text-[var(--iris-text)] antialiased">
        <nav className="sticky top-0 z-50 flex h-14 items-center border-b border-[var(--iris-border)] bg-[var(--iris-surface)]/80 px-6 backdrop-blur-md">
          <a href="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--iris-accent)]">
              <span className="text-sm font-bold text-white">IR</span>
            </div>
            <span className="text-lg font-semibold tracking-tight">IRIS</span>
          </a>
          <div className="ml-8 flex gap-6">
            <a
              href="/"
              className="text-sm text-[var(--iris-text-secondary)] transition-colors hover:text-[var(--iris-text)]"
            >
              首页
            </a>
            <a
              href="/memory"
              className="text-sm text-[var(--iris-text-secondary)] transition-colors hover:text-[var(--iris-text)]"
            >
              记忆管理
            </a>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
