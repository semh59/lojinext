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
        // Real-backend (0-mock Faz 2) suit'leri gerçek HTTP + gerçek DB'ye
        // gider; tam-suite koşumunda backend yük altında yavaşlar ve 5s'lik
        // vitest varsayılanı yük-bağımlı sahte timeout'lar üretir (2026-07-05
        // ve -07 tam koşumlarında her seferinde FARKLI dosyalar düştü).
        // Geçen testin süresi değişmez; sadece failure tespiti gecikir.
        testTimeout: 20000,
        hookTimeout: 30000,
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
            // Ratchet 2026-07-07: real-backend suit'leri CI'da gerçekten
            // koşmaya başlayınca ölçüm 53.89→58.56 (lines) yükseldi; eşikler
            // ölçülen değerin ~1.5 puan altına sabitlendi ki kayma (testsiz
            // yeni kod) gate'e takılsın. Ölçüm kaynağı: CI run 28881225641
            // (lokal run 10 ile 0.05 içinde tutarlı: 58.53/75.48/40.44).
            // Coverage yükseldikçe eşikleri de yukarı taşı — asla düşürme
            // (düşürme = regresyonu susturma; bkz [[no-error-no-fake-code]]).
            thresholds: {
                lines: 57,        // measured 58.56 (CI, 2026-07-07)
                functions: 39,    // measured 40.44
                branches: 74,     // measured 75.43
                statements: 57,   // measured 58.56
            },
        },
    },
})
