import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0a0e14",
          panel: "#121722",
          border: "#1f2937",
          edge: "#22c55e",
          edgeNeg: "#ef4444",
          muted: "#6b7280",
        },
      },
    },
  },
  plugins: [],
};

export default config;
