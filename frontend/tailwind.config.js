/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        zinc: {
          950: '#0B0C0E',
          900: '#121214',
          800: '#1E1F22',
          700: '#2B2D31',
          600: '#4E5058',
        }
      },
      animation: {
        bounce: 'bounce 1s infinite',
      }
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
