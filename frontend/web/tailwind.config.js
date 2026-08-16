/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'brand-primary': 'var(--color-brand-primary, #3b82f6)',
        'brand-secondary': 'var(--color-brand-secondary, #8b5cf6)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
