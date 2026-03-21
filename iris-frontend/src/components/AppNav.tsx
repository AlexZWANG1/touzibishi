"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PrismLogo } from "./PrismLogo";
import { classNames } from "@/utils/formatters";

const PRIMARY_LINKS = [
  { href: "/", label: "首页" },
  { href: "/knowledge", label: "知识库" },
  { href: "/memory", label: "记忆管理" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="shrink-0 border-b border-[var(--b2)] bg-[rgba(255,255,255,0.88)] backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="shrink-0">
          <PrismLogo />
        </Link>

        <div className="hidden flex-1 items-center justify-center gap-1 md:flex">
          {PRIMARY_LINKS.map((link) => {
            const active = isActive(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={classNames(
                  "rounded-md px-3 py-2 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-[var(--bg-2)] text-[var(--t1)]"
                    : "text-[var(--t2)] hover:bg-[var(--bg-hover)] hover:text-[var(--t1)]",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </div>

        <div className="ml-auto flex items-center gap-3">
          <Link
            href="/dev"
            className={classNames(
              "rounded-md px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.1em] transition-colors",
              isActive(pathname, "/dev")
                ? "bg-[var(--ac-s)] text-[var(--ac)]"
                : "text-[var(--t3)] hover:bg-[var(--bg-hover)] hover:text-[var(--ac)]",
            )}
          >
            Dev
          </Link>

        </div>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto px-4 py-2 md:hidden">
        {PRIMARY_LINKS.map((link) => {
          const active = isActive(pathname, link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={classNames(
                "whitespace-nowrap rounded-pill px-3 py-1.5 text-[12px] font-medium transition-colors",
                active
                  ? "bg-[var(--ac)] text-white"
                  : "bg-[var(--bg-2)] text-[var(--t2)] hover:text-[var(--t1)]",
              )}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
