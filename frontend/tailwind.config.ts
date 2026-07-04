import type { Config } from "tailwindcss";

// Colours are driven by CSS variables (R G B triplets) so the whole UI can flip
// between the light "cafe cream" theme and the dark "night cafe" theme by
// toggling the `dark` class on <html>. The `<alpha-value>` placeholder keeps
// Tailwind opacity modifiers (e.g. bg-cafe-danger/20) working.
const withVar = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cafe: {
          bg: withVar("--cafe-bg"),
          surface: withVar("--cafe-surface"),
          raised: withVar("--cafe-raised"),
          border: withVar("--cafe-border"),
          line: withVar("--cafe-line"),
          ink: withVar("--cafe-ink"),
          muted: withVar("--cafe-muted"),
          accent: withVar("--cafe-accent"),
          accentDark: withVar("--cafe-accent-dark"),
          good: withVar("--cafe-good"),
          warn: withVar("--cafe-warn"),
          danger: withVar("--cafe-danger"),
        },
      },
      boxShadow: {
        cafe: "0 1px 2px rgba(0,0,0,0.04), 0 6px 20px rgba(0,0,0,0.06)",
        "cafe-sm": "0 1px 2px rgba(0,0,0,0.06)",
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      keyframes: {
        pulseTension: {
          "0%, 100%": { opacity: "1", strokeWidth: "2" },
          "50%": { opacity: "0.45", strokeWidth: "4" },
        },
      },
      animation: {
        tension: "pulseTension 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
