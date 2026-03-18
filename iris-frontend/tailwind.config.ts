import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      colors: {
        iris: {
          bg: "var(--iris-bg)",
          surface: "var(--iris-surface)",
          surfaceHover: "var(--iris-surface-hover)",
          border: "var(--iris-border)",
          text: "var(--iris-text)",
          textSecondary: "var(--iris-text-secondary)",
          textMuted: "var(--iris-text-muted)",
          accent: "var(--iris-accent)",
          accentHover: "var(--iris-accent-hover)",
        },
        phase: {
          gather: "#22c55e",
          analyze: "#3b82f6",
          evaluate: "#f59e0b",
          finalize: "#8b5cf6",
        },
        event: {
          search: "#22c55e",
          analyze: "#3b82f6",
          model: "#f59e0b",
          system: "#9ca3af",
          user: "#a855f7",
        },
        status: {
          bullish: "#22c55e",
          bearish: "#ef4444",
          neutral: "#f59e0b",
        },
      },
      spacing: {
        "gap-xs": "4px",
        "gap-sm": "8px",
        "gap-md": "16px",
        "gap-lg": "24px",
        "gap-xl": "32px",
      },
    },
  },
  plugins: [],
};

export default config;
