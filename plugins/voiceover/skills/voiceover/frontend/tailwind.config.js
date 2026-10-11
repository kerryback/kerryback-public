/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0f172a',
        slate: {
          DEFAULT: '#334155',
        },
        // Brand ramp — brand-600 is the single primary.
        brand: {
          50: '#eef4ff',
          100: '#dbe6fe',
          200: '#bfd3fe',
          300: '#93b4fd',
          400: '#5f8bf9',
          500: '#3b6ef2',
          600: '#2452d6',
          700: '#1d43ad',
          800: '#1c3a8a',
          900: '#1b336e',
          950: '#141f42',
          // Aliases kept so existing tokens resolve to the new ramp.
          blue: '#2452d6', // → brand-600 (primary)
          dark: '#1d43ad', // → brand-700 (primary hover)
          tint: '#eef4ff', // → brand-50 (tint surface)
        },
        // Attention / regenerate accent only — never a forward CTA.
        accent: {
          500: '#f59e0b',
          600: '#d97706',
        },
        bg: '#f8fafc',
        line: '#e2e8f0',
        muted: '#64748b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      boxShadow: {
        xs: '0 1px 2px rgba(15,23,42,.04)',
        sm: '0 1px 3px rgba(15,23,42,.06), 0 1px 2px rgba(15,23,42,.04)',
        md: '0 4px 12px rgba(15,23,42,.08)',
        lg: '0 12px 32px rgba(15,23,42,.12)',
      },
    },
  },
  plugins: [],
}
