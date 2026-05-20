/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Pretendard Variable', 'Pretendard', '-apple-system', 'BlinkMacSystemFont', 'Apple SD Gothic Neo', 'sans-serif'],
      },
      colors: {
        // 위험도 고정 색상
        risk: {
          high:    '#EF4444',
          medium:  '#F97316',
          caution: '#EAB308',
          safe:    '#22C55E',
        },
        // 브랜드 색상
        brand: {
          50:  '#EFF6FF',
          100: '#DBEAFE',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
        },
      },
      screens: {
        xs: '375px',
      },
      boxShadow: {
        'up': '0 -4px 6px -1px rgba(0,0,0,0.07)',
        'card': '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
      },
      borderRadius: {
        'xl':  '12px',
        '2xl': '16px',
      },
      animation: {
        'slide-down': 'slideDown 0.2s ease-out',
        'fade-in':    'fadeIn 0.3s ease-out',
        'spin-slow':  'spin 2s linear infinite',
      },
      keyframes: {
        slideDown: {
          '0%':   { transform: 'translateY(-100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)',      opacity: '1' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    // @tailwindcss/typography and @tailwindcss/forms are optional
    // require('@tailwindcss/typography'),
    // require('@tailwindcss/forms'),
  ],
}
