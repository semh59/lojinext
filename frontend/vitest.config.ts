import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': resolve(currentDir, 'src'),
        },
    },
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: resolve(currentDir, 'src/test/setup.ts'),
        css: true,
        pool: 'forks',
        include: ['src/**/*.{test,spec}.{js,ts,jsx,tsx}'],
        exclude: ['e2e/**', 'node_modules/**'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html', 'json-summary'],
            reportsDirectory: './coverage',
            include: ['src/**/*.{ts,tsx}'],
            exclude: [
                'src/**/*.{test,spec}.{ts,tsx}',
                'src/test/**',
                'src/main.tsx',
                'src/vite-env.d.ts',
                'src/**/__tests__/**',
            ],
            thresholds: {
                lines: 53,        // measured 53.89% (2026-06-22, after new admin pages added)
                functions: 32,    // measured 32.86%
                branches: 73,     // measured 73.72%
                statements: 53,
            },
        },
    },
})
