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
      <body className="h-screen overflow-hidden bg-[var(--iris-bg)] text-[var(--iris-text)] antialiased flex flex-col">
        {/* ─── Top Navigation ─── */}
        <nav className="flex items-center justify-between px-3 h-8 shrink-0 border-b border-[var(--iris-border)] bg-[var(--iris-surface)]">
          {/* Left: Logo + Links */}
          <div className="flex items-center gap-4">
            <a href="/" className="font-mono text-xs font-semibold tracking-[0.12em] text-[var(--iris-accent)]">
              IRIS
            </a>
            <a
              href="/"
              className="text-[12px] text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)] transition-colors duration-150"
            >
              首页
            </a>
            <a
              href="/knowledge"
              className="text-[12px] text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)] transition-colors duration-150"
            >
              知识库
            </a>
            <a
              href="/memory"
              className="text-[12px] text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)] transition-colors duration-150"
            >
              记忆管理
            </a>
          </div>

          {/* Right: Live indicator */}
          <div className="flex items-center gap-[5px] font-mono text-[11px] tracking-[0.1em] text-[var(--iris-text-muted)]">
            LIVE
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--iris-accent)] animate-pulse-dot" />
          </div>
        </nav>

        {/* ─── Main Content ─── */}
        <main className="flex-1 overflow-hidden">{children}</main>
      </body>
    </html>
  );
}
