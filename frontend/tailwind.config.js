/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paytm: { blue: "#00BAF2", navy: "#002E6E", ink: "#0B1F3A", soft: "#EAF7FD" },
      },
      fontFamily: { sans: ["Inter", "Noto Sans Devanagari", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
