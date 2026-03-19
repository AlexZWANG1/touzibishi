import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "-apple-system", "sans-serif"],
        "dm-sans": ['"DM Sans"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "Consolas", "monospace"],
        "jetbrains-mono": ['"JetBrains Mono"', "Consolas", "monospace"],
      },
      colors: {
        iris: {
          bg: "var(--iris-bg)",
          surface: "var(--iris-surface)",
          "surface-hover": "var(--iris-surface-hover)",
          border: "var(--iris-border)",
          "border-active": "var(--iris-border-active)",
          text: "var(--iris-text)",
          "text-secondary": "var(--iris-text-secondary)",
          "text-muted": "var(--iris-text-muted)",
          accent: "var(--iris-accent)",
          "accent-hover": "var(--iris-accent-hover)",
          "accent-dim": "var(--iris-accent-dim)",
          "accent-glow": "var(--iris-accent-glow)",
          data: "var(--iris-data)",
          green: "var(--iris-green)",
          red: "var(--iris-red)",
          blue: "var(--iris-blue)",
          amber: "var(--iris-amber)",
          purple: "var(--iris-purple)",
        },
        phase: {
          gather: "var(--phase-gather)",
          analyze: "var(--phase-analyze)",
          evaluate: "var(--phase-evaluate)",
          finalize: "var(--phase-finalize)",
        },
        event: {
          search: "var(--event-search)",
          analyze: "var(--event-analyze)",
          model: "var(--event-model)",
          system: "var(--event-system)",
          user: "var(--event-user)",
        },
        status: {
          bullish: "var(--status-bullish)",
          bearish: "var(--status-bearish)",
          neutral: "var(--status-neutral)",
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        shimmer: "shimmer 1.8s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out forwards",
        "slide-up": "slide-up 0.4s ease-out forwards",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
