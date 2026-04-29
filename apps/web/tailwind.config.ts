import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Match the dev console's dark SOC palette
        bg: {
          DEFAULT: "#020617",
          elev: "#0f172a",
          card: "#0f172a",
        },
        border: {
          DEFAULT: "#1e293b",
        },
        ink: {
          DEFAULT: "#e2e8f0",
          dim: "#94a3b8",
          mute: "#64748b",
          faint: "#475569",
        },
        // Severity tokens
        sev: {
          critical: "#991b1b",
          "critical-fg": "#fecaca",
          high: "#9a3412",
          "high-fg": "#fed7aa",
          medium: "#854d0e",
          "medium-fg": "#fef08a",
          low: "#166534",
          "low-fg": "#bbf7d0",
          informational: "#334155",
          "informational-fg": "#cbd5e1",
        },
        // Observable group tokens
        obs: {
          net: "#064e3b",
          "net-fg": "#6ee7b7",
          host: "#1e3a8a",
          "host-fg": "#93c5fd",
          hash: "#581c87",
          "hash-fg": "#d8b4fe",
          id: "#78350f",
          "id-fg": "#fcd34d",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
