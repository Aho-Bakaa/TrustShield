/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0b1120",
        panel: "#111a2e",
        panel2: "#16223c",
        edge: "#243356",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(56,189,248,0.15), 0 10px 40px -12px rgba(2,6,23,0.9)",
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
