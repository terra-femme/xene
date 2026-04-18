/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        xene: {
          bg:      '#0a0a0a',
          surface: '#111111',
          border:  '#1e1e1e',
          gold:    '#c9a96e',
          'gold-dim': '#8a6e3f',
          muted:   '#444444',
          text:    '#e8e8e8',
          'text-dim': '#888888',
          sc:  '#ff5500',
          ig:  '#e1306c',
          bc:  '#4e9a06',
          bp:  '#5b7cfa',
          tt:  '#ffffff',
        },
      },
      fontFamily: {
        display: ['"Bebas Neue"', 'sans-serif'],
        mono:    ['"DM Mono"', 'monospace'],
        body:    ['"Archivo"', 'sans-serif'],
      },
      gridTemplateColumns: {
        magazine: '2fr 1fr 1fr',
        'magazine-sm': '1fr 1fr',
      },
      animation: {
        'waveform': 'waveform 1.2s ease-in-out infinite alternate',
        'waveform-slow': 'waveform 1.8s ease-in-out infinite alternate',
        'waveform-fast': 'waveform 0.8s ease-in-out infinite alternate',
        'scan': 'scan 3s linear infinite',
        'pulse-gold': 'pulseGold 2s ease-in-out infinite',
      },
      keyframes: {
        waveform: {
          '0%':   { transform: 'scaleY(0.15)' },
          '100%': { transform: 'scaleY(1)' },
        },
        scan: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        pulseGold: {
          '0%, 100%': { opacity: '0.6' },
          '50%':      { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
