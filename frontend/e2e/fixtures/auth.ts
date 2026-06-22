import { test as base, Page } from '@playwright/test'
import { loginViaApi } from '../helpers/api'

type AuthFixtures = {
    authedPage: Page
}

export const test = base.extend<AuthFixtures>({
    authedPage: async ({ page }, use) => {
        await loginViaApi(page)
        await use(page)
    },
})

export { expect } from '@playwright/test'
