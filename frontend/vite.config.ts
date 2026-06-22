import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { visualizer } from 'rollup-plugin-visualizer'
import { VitePWA } from 'vite-plugin-pwa'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [
        react(),
        // RV2.PWA — Plan §7.1: manifest + service worker + push handler
        VitePWA({
            registerType: 'autoUpdate',
            injectRegister: 'auto',
            includeAssets: ['favicon.ico', 'icons/*.png'],
            // sw-push.ts: kendi push/notificationclick handler'ımız var
            strategies: 'injectManifest',
            srcDir: 'src',
            filename: 'sw-push.ts',
            injectManifest: {
                globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
                maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
            },
            devOptions: { enabled: false },
            manifest: {
                name: 'LojiNext',
                short_name: 'LojiNext',
                description: 'AI-powered TIR fleet management',
                theme_color: '#1e40af',
                background_color: '#f8fafc',
                display: 'standalone',
                start_url: '/today',
                lang: 'tr',
                icons: [
                    { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
                    { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
                    {
                        src: '/icons/icon-maskable-512.png',
                        sizes: '512x512',
                        type: 'image/png',
                        purpose: 'maskable',
                    },
                ],
            },
        }),
        ...(process.env.ANALYZE === 'true' ? [visualizer({
            open: false,
            filename: 'bundle-stats.html',
            gzipSize: true,
            brotliSize: true,
        })] : []),
    ],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        host: true, // Listen on all addresses
        strictPort: true,
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://127.0.0.1:8000',
                changeOrigin: true,
                secure: false,
                ws: true,
            }
        },
        watch: {
            usePolling: true,
        },
    },
    build: {
        chunkSizeWarningLimit: 600,
        rollupOptions: {
            output: {
                manualChunks: {
                    'vendor-react': ['react', 'react-dom', 'react-router-dom'],
                    'vendor-query': ['@tanstack/react-query'],
                    // recharts: manualChunks içinde değil — entry HTML'e
                    // modulepreload olarak eklenince 387 KB'lık asset login
                    // sayfasında bile yüklenir. Auto-split olarak bırakıyoruz
                    // → sadece chart import eden lazy sayfa açıldığında yüklenir.
                    'vendor-motion': ['framer-motion'],
                    'vendor-forms': ['react-hook-form', '@hookform/resolvers', 'zod'],
                    'vendor-ui': ['sonner', 'lucide-react'],
                },
            },
        },
    },
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: './src/test/setup.ts',
        css: true,
        include: ['src/**/*.{test,spec}.{js,ts,jsx,tsx}'],
        exclude: ['e2e/**', 'node_modules/**'],
    }
})
