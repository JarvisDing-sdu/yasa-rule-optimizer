/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brutal: {
          black:  '#000000',
          white:  '#FFFFFF',
          cream:  '#FFFBF0',
          yellow: '#FFE500',
          red:    '#FF3B3B',
          cyan:   '#00E5FF',
          purple: '#6B00FF',
          gray:   '#E8E8E8',
        },
      },
      boxShadow: {
        brutal:          '4px 4px 0px #000000',
        'brutal-sm':     '2px 2px 0px #000000',
        'brutal-lg':     '6px 6px 0px #000000',
        'brutal-red':    '4px 4px 0px #FF3B3B',
        'brutal-yellow': '4px 4px 0px #FFE500',
        'brutal-cyan':   '4px 4px 0px #00E5FF',
        'brutal-purple': '4px 4px 0px #6B00FF',
      },
      borderWidth: {
        '3': '3px',
      },
    },
  },
  plugins: [],
}
