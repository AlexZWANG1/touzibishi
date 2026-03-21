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
        "fade-up": "fade-up 0.35s ease-out forwards",
        shimmer: "shimmer 1.6s ease-in-out infinite",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
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
