/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        noc: {
          bg:       '#0a0f1e',
          surface:  '#111827',
          border:   '#1e2d4a',
          accent:   '#00d4ff',
          accent2:  '#7c3aed',
          user:     '#1d4ed8',
          agent:    '#1a2744',
          success:  '#10b981',
          warning:  '#f59e0b',
          danger:   '#ef4444',
          muted:    '#6b7280',
          text:     '#e2e8f0',
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'monospace'],
        sans: ['"Space Grotesk"', 'sans-serif'],
        display: ['"Syne"', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan': 'scan 2s linear infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        scan: {
          '0%': { backgroundPosition: '0% 0%' },
          '100%': { backgroundPosition: '0% 100%' }
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' }
        }
      }
    }
  },
  plugins: []
}
