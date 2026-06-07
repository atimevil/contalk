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
          high:    '#DC2626',
          medium:  '#EA580C',
          caution: '#CA8A04',
          safe:    '#16A34A',
        },
        // 브랜드 색상 — 딥 네이비 (권위·신뢰·안정)
        brand: {
          50:  '#F0F4FA',
          100: '#DCE5F2',
          200: '#B9CCE6',
          300: '#8AABD4',
          400: '#5B85BE',
          500: '#2D5A9E',
          600: '#0F2B5B',   // 메인 딥 네이비
          700: '#0C2249',
          800: '#091A38',
          900: '#061127',
          950: '#030A18',
        },
        // 골드 포인트 (프리미엄·신뢰 강조)
        accent: {
          50:  '#FDF8EB',
          100: '#F9EFD0',
          200: '#F2DDA0',
          300: '#E8C560',
          400: '#D4A017',
          500: '#B8860B',   // 다크골드
          600: '#96690A',
          700: '#6E4D08',
        },
        // 중립 (쿨 그레이)
        slate: {
          50:  '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
        },
      },
      screens: {
        xs: '375px',
      },
      boxShadow: {
        'up': '0 -4px 6px -1px rgba(0,0,0,0.07)',
        'card': '0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04)',
        'card-hover': '0 4px 12px rgba(15,23,42,0.12), 0 2px 4px rgba(15,23,42,0.06)',
        'elevated': '0 8px 24px rgba(15,23,42,0.12)',
      },
      borderRadius: {
        'lg':  '8px',
        'xl':  '12px',
        '2xl': '16px',
      },
      animation: {
        'slide-down': 'slideDown 0.2s ease-out',
        'fade-in':    'fadeIn 0.3s ease-out',
        'fade-up':    'fadeUp 0.4s ease-out',
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
        fadeUp: {
          '0%':   { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)',    opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
