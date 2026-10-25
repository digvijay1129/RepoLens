/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--bg)",
        surface: "var(--surface)",
        "surface-raised": "var(--surface-raised)",
        foreground: "var(--text)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        border: "var(--border)",
      },
      boxShadow: {
        panel: "var(--shadow-sm)",
        glow: "var(--shadow-glow)",
      },
      borderRadius: {
        panel: "var(--radius-lg)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "soft-pulse": {
          "0%, 100%": { opacity: "0.6", transform: "scale(1)" },
          "50%": { opacity: "1", transform: "scale(1.04)" },
        },
      },
      animation: {
        "fade-up": "fade-up .24s ease both",
        "soft-pulse": "soft-pulse 2.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
