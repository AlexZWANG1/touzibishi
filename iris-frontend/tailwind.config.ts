import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--sans)'],
        display: ['var(--display)'],
        mono: ['var(--mono)'],
        sora: ['var(--sans)'],
        playfair: ['var(--display)'],
        data: ['var(--mono)'],
      },
      colors: {
        prism: {
          bg: "var(--bg)",
          surface: "var(--bg-w)",
          muted: "var(--bg-2)",
          mutedDeep: "var(--bg-3)",
          hover: "var(--bg-hover)",
          border: "var(--b1)",
          borderStrong: "var(--b2)",
          borderEmphasis: "var(--b3)",
          text: "var(--t1)",
          textMuted: "var(--t2)",
          textSoft: "var(--t3)",
          hint: "var(--t4)",
          accent: "var(--ac)",
          accentHover: "var(--ac-h)",
          accentSoft: "var(--ac-s)",
          accentMedium: "var(--ac-m)",
          accentText: "var(--ac-t)",
          data: "var(--cy)",
          dataSoft: "var(--cy-s)",
          success: "var(--green)",
          danger: "var(--red)",
          warning: "var(--amber)",
        },
      },
      borderRadius: {
        sm: "var(--r-sm)",
        md: "var(--r-md)",
        lg: "var(--r-lg)",
        xl: "var(--r-xl)",
        pill: "var(--r-pill)",
      },
      boxShadow: {
        card: "var(--sh)",
        lift: "var(--sh-lg)",
      },
      animation: {
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        "fade-up": "fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "dot-pulse": "dot-pulse 1.4s ease-in-out infinite",
        shimmer: "shimmer 1.6s ease-in-out infinite",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(16px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "dot-pulse": {
          "0%, 100%": { opacity: "0.25", transform: "scale(0.85)" },
          "50%": { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
