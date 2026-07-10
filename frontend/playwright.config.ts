import { defineConfig, devices } from '@playwright/test'
import { config } from 'dotenv'

config({ path: '.env.test' })

export default defineConfig({
    testDir: './e2e/tests',
    // inventory.spec.ts normal suite'e dahil değil — ayrıca çalıştırılır:
    //   npx playwright test --config playwright.inventory.config.ts
    testIgnore: ['**/inventory.spec.ts', '**/_design-audit.spec.ts'],
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
        // i18n.ts has no hardcoded `lng` (a saved/detected language should
        // survive reload — see commit 834e007), so a fresh browser context
        // with no localStorage falls through to navigator.language. Every
        // spec in this suite asserts Turkish text; without pinning this,
        // a runner whose OS/container locale isn't Turkish would boot the
        // app in English and fail most of the suite for a reason that has
        // nothing to do with the feature under test.
        locale: 'tr-TR',
    },

    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

    webServer: {
        command: 'npm run dev',
        port: 3000,
        reuseExistingServer: true,
        timeout: 120_000,
    },
})
