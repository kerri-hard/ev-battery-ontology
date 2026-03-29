import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg1: '#0a0a1a',
        bg2: '#1a1a3e',
        bg3: '#12122a',
        glass: 'rgba(255,255,255,0.04)',
        'glass-border': 'rgba(255,255,255,0.08)',
        cyan: '#00d2ff',
        neon: {
          green: '#06d6a0',
          red: '#f5576c',
          yellow: '#ffd166',
          purple: '#a855f7',
          orange: '#FF6B35',
        },
        'text-primary': '#e0e0f0',
        'text-dim': '#8888aa',
      },
      fontFamily: {
        mono: ['var(--font-geist-mono)', 'SF Mono', 'Consolas', 'monospace'],
        ui: ['var(--font-geist-sans)', '-apple-system', 'Noto Sans KR', 'sans-serif'],
      },
      animation: {
        'glow-pulse': 'glow-pulse 1.5s infinite',
        'step-flash': 'step-flash 0.8s ease-out 3',
        'fade-in': 'fadeIn 0.3s ease-out',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 6px rgba(0,210,255,.3)' },
          '50%': { boxShadow: '0 0 18px rgba(0,210,255,.7)' },
        },
        'step-flash': {
          '0%': { boxShadow: '0 0 0 0 rgba(6,214,160,.7)' },
          '70%': { boxShadow: '0 0 0 10px rgba(6,214,160,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(6,214,160,0)' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
export default config;
