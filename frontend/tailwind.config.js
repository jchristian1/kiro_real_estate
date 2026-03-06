/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: 'rgba(255,255,255,0.04)',
        accent: '#6366f1',
      },
    },
  },
  plugins: [],
}
