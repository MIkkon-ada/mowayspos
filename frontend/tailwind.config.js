/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: '#0369A1',   // sky-700  — main CTA, sidebar accents
          accent:  '#0EA5E9',   // sky-500  — hover states, icons, gradients
          subtle:  '#E9EFF6',   // custom   — card borders, dividers (139 uses)
          surface: '#F1F5F9',   // slate-100 — page backgrounds (60 uses)
        },
      },
    },
  },
  plugins: [],
}
