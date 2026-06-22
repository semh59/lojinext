import { defineConfig, devices } from '@playwright/test'
import { config } from 'dotenv'

config({ path: '.env.test' })

/**
 * Inventory-only Playwright config.
 * Kullanım: npx playwright test --config playwright.inventory.config.ts
 */
export default defineConfig({
    testDir: './e2e/tests',
    testMatch: ['**/inventory.spec.ts'],
    timeout: 180_000,  // Inventory daha uzun sürer (31 route × ~3s)
    fullyParallel: false,
    retries: 0,
    workers: 1,
    reporter: [['list']],

    use: {
        baseURL: 'http://localhost:3000',
        trace: 'off',
        screenshot: 'off',
        video: 'off',
    },

    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

    webServer: {
        command: 'npm run dev',
        port: 3000,
        reuseExistingServer: true,
        timeout: 120_000,
    },
})
