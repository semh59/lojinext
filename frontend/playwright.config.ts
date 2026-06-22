import { defineConfig, devices } from '@playwright/test'
import { config } from 'dotenv'

config({ path: '.env.test' })

export default defineConfig({
    testDir: './e2e/tests',
    // inventory.spec.ts normal suite'e dahil değil — ayrıca çalıştırılır:
    //   npx playwright test --config playwright.inventory.config.ts
    testIgnore: ['**/inventory.spec.ts'],
    timeout: 30_000,
    expect: { timeout: 8_000 },
    fullyParallel: true,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : 2,
    reporter: [['html', { open: 'never' }], ['list']],

    use: {
        baseURL: 'http://localhost:3000',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
    },

    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

    webServer: {
        command: 'npm run dev',
        port: 3000,
        reuseExistingServer: true,
        timeout: 120_000,
    },
})
