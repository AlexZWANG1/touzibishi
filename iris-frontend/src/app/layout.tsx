import type { Metadata } from "next";
import { Playfair_Display, Sora, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/AppNav";

const playfair = Playfair_Display({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--font-display",
});

const sora = Sora({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
  variable: "--font-sans",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-mono",
});

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
    <html lang="zh-CN" className={`${playfair.variable} ${sora.variable} ${jetbrainsMono.variable}`}>
      <body className="flex min-h-screen flex-col bg-[var(--bg)] text-[var(--t1)] antialiased">
        <AppNav />
        <main className="flex-1 overflow-hidden">{children}</main>
      </body>
    </html>
  );
}
