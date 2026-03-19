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
      <body className="min-h-screen bg-[var(--iris-bg)] text-[var(--iris-text)] antialiased">
        {/* ─── Top Navigation ─── */}
        <nav
          className="sticky top-0 z-50 flex items-center justify-between px-4"
          style={{
            height: "32px",
            borderBottom: "1px solid var(--iris-border)",
            backgroundColor: "var(--iris-surface)",
          }}
        >
          {/* Left: Logo + Links */}
          <div className="flex items-center">
            <a href="/" className="flex items-center gap-1.5">
              <span
                className="text-[12px] font-semibold tracking-tight"
                style={{ color: "var(--iris-text)" }}
              >
                IRIS
              </span>
            </a>

            {/* Nav Links */}
            <div className="ml-6 flex items-center gap-4">
              <a
                href="/"
                className="text-[11px] text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)]"
              >
                首页
              </a>
              <a
                href="/knowledge"
                className="text-[11px] text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)]"
              >
                知识库
              </a>
              <a
                href="/memory"
                className="text-[11px] text-[var(--iris-text-secondary)] hover:text-[var(--iris-text)]"
              >
                记忆管理
              </a>
            </div>
          </div>

          {/* Right: Live indicator */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] tracking-wide text-[var(--iris-text-muted)]">
              LIVE
            </span>
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: "var(--iris-accent)" }}
            />
          </div>
        </nav>

        {/* ─── Main Content ─── */}
        <main>{children}</main>
      </body>
    </html>
  );
}
