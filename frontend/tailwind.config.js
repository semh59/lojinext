/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class', // Allow manual dark mode toggle via class
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
            },
            colors: {
                base: 'var(--bg-base)',
                surface: 'var(--bg-surface)',
                elevated: 'var(--bg-elevated)',

                primary: 'var(--text-primary)',
                secondary: 'var(--text-secondary)',
                tertiary: 'var(--text-tertiary)',

                border: 'var(--border)',

                accent: {
                    DEFAULT: 'var(--accent)',
                    soft: 'var(--accent-soft)',
                    dark: 'var(--accent-dark)',
                },
                success: 'var(--success)',
                warning: 'var(--warning)',
                danger: 'var(--danger)',
                info: 'var(--info)',
            },
            fontSize: {
                'xs': ['11px', '1.5'],
                'sm': ['13px', '1.5'],
                'base': ['14px', '1.5'],
                'lg': ['16px', '1.5'],
                'xl': ['18px', '1.2'],
                '2xl': ['22px', '1.2'],
                '3xl': ['28px', '1.2'],
                '4xl': ['36px', '1.2'],
            },
            fontWeight: {
                normal: '400',
                medium: '500',
                semibold: '600',
                bold: '700',
            },
            letterSpacing: {
                heading: '-0.01em',
                caps: '0.02em',
            },
            spacing: {
                '4px': '4px',
                '8px': '8px',
                '12px': '12px',
                '16px': '16px',
                '24px': '24px',
                '32px': '32px',
                '48px': '48px',
                '64px': '64px',
            },
            borderRadius: {
                'input': '6px',
                'card': '10px',
                'modal': '14px',
                'pill': '999px',
            },
            transitionTimingFunction: {
                'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
                'dismiss': 'cubic-bezier(0.4, 0, 1, 1)',
            },
            keyframes: {
                shake: {
                    '0%, 100%': { transform: 'translateX(0)' },
                    '20%': { transform: 'translateX(-6px)' },
                    '60%': { transform: 'translateX(6px)' },
                    '80%': { transform: 'translateX(-4px)' },
                    '90%': { transform: 'translateX(4px)' }
                },
                shimmer: {
                    '0%': { backgroundPosition: '200% 0' },
                    '100%': { backgroundPosition: '-200% 0' }
                },
                ringPulse: {
                    '0%': { transform: 'scale(0.8)', opacity: '0.8' },
                    '100%': { transform: 'scale(2.4)', opacity: '0' }
                }
            },
            animation: {
                shake: 'shake 350ms cubic-bezier(0.16, 1, 0.3, 1)',
                shimmer: 'shimmer 1.4s linear infinite',
                'ring-pulse': 'ringPulse 2s cubic-bezier(0.16, 1, 0.3, 1) infinite',
            }
        },
    },
    plugins: [],
}
