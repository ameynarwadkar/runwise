import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        charcoal: {
          DEFAULT: "#101114",
          subtle: "#14161B",
          darker: "#0B0C0E",
        },
        surface: {
          DEFAULT: "#16181D",
          hover: "#1C1F26",
          active: "#20242D",
          border: "#232730",
          borderSubtle: "#1D212A",
        },
        brand: {
          orange: "#F97316",
          orangeHover: "#EA580C",
          orangeSubtle: "rgba(249, 115, 22, 0.12)",
          purple: "#A855F7",
          purpleSubtle: "rgba(168, 85, 247, 0.12)",
          green: "#10B981",
          greenSubtle: "rgba(16, 185, 129, 0.12)",
          amber: "#F59E0B",
          amberSubtle: "rgba(245, 158, 11, 0.12)",
          red: "#EF4444",
          redSubtle: "rgba(239, 68, 68, 0.12)",
        },
      },
      fontFamily: {
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
