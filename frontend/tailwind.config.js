/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#f8fafc",
        panel: "#ffffff",
        panel2: "#f1f5f9",
        edge: "#cbd5e1",
        sebiNavy: "#002e6e",
        sebiTeal: "#1b68b3",
        sebiSlate: "#475569",
      },
      boxShadow: {
        glow: "0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03), 0 0 0 1px rgba(0, 0, 0, 0.05)",
      },
      keyframes: {
        pulseline: {
          "0%,100%": { opacity: 0.4 },
          "50%": { opacity: 1 },
        },
      },
      animation: {
        pulseline: "pulseline 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
