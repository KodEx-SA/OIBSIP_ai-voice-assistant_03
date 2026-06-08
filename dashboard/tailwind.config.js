/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        display: ['"Orbitron"', 'monospace'],
      },
      colors: {
        bg:      '#080c10',
        surface: '#0d1117',
        border:  '#1a2332',
        cyan:    '#00d4ff',
        green:   '#00ff88',
        amber:   '#ffb800',
        red:     '#ff4455',
        muted:   '#3d5066',
        dim:     '#1e2d3d',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flicker':    'flicker 4s linear infinite',
        'scan':       'scan 8s linear infinite',
      },
      keyframes: {
        flicker: {
          '0%, 100%': { opacity: '1' },
          '92%':      { opacity: '1' },
          '93%':      { opacity: '0.4' },
          '94%':      { opacity: '1' },
          '96%':      { opacity: '0.6' },
          '97%':      { opacity: '1' },
        },
        scan: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
      },
    },
  },
  plugins: [],
}
