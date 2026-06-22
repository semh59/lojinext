import { test, expect } from '../fixtures/auth'

const MOCK_JOB_TAMAMLANDI = {
    id: 1,
    dosya_adi: 'seferler_ocak.xlsx',
    aktarim_tipi: 'sefer',
    baslama_zamani: '2026-06-15T10:00:00Z',
    durum: 'tamamlandi',
    basarili: 42,
    hatali: 2,
    toplam: 44,
}

const MOCK_JOB_GERI_ALINDI = {
    id: 2,
    dosya_adi: 'yakitlar_subat.csv',
    aktarim_tipi: 'yakit',
    baslama_zamani: '2026-06-10T08:30:00Z',
    durum: 'geri_alindi',
    basarili: 15,
    hatali: 0,
    toplam: 15,
}

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Veri Yönetimi sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/imports/history**', r =>
            r.fulfill(json([MOCK_JOB_TAMAMLANDI, MOCK_JOB_GERI_ALINDI]))
        )
        await page.route('**/api/v1/admin/imports/*/rollback', r =>
            r.fulfill(json({ ok: true }))
        )
    })

    test('sayfa başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('Veri İçe Aktarım ve Rollback').first()).toBeVisible({ timeout: 10_000 })
    })

    test('tablo yüklenir — dosya adları görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('Veri İçe Aktarım ve Rollback').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 8_000 })
        await expect(page.getByText('yakitlar_subat.csv').first()).toBeVisible({ timeout: 5_000 })
    })

    test('durum badge\'leri doğru — Tamamlandı ve Geri Alındı', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        // Anchor on a table cell that actually loaded before checking badges
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('Tamamlandı').first()).toBeVisible({ timeout: 5_000 })
        await expect(page.getByText('Geri Alındı').first()).toBeVisible({ timeout: 5_000 })
    })

    test('geri_alindi satırında "Geri Al" butonu devre dışı', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('yakitlar_subat.csv').first()).toBeVisible({ timeout: 10_000 })
        // The geri_alindi row is the second row — find the button inside that row
        const geriAlindiRow = page.locator('tr', { hasText: 'yakitlar_subat.csv' }).first()
        const rollbackBtn = geriAlindiRow.getByRole('button', { name: 'Geri Al' })
        await expect(rollbackBtn).toBeDisabled({ timeout: 5_000 })
    })

    test('rollback iptal edilirse POST isteği gönderilmez', async ({ authedPage: page }) => {
        let postCount = 0
        await page.unroute('**/api/v1/admin/imports/*/rollback')
        await page.route('**/api/v1/admin/imports/*/rollback', r => {
            postCount++
            return r.fulfill(json({ ok: true }))
        })

        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })

        // Register dismiss handler BEFORE clicking
        page.on('dialog', dialog => dialog.dismiss())

        const tamamlandiRow = page.locator('tr', { hasText: 'seferler_ocak.xlsx' }).first()
        await tamamlandiRow.getByRole('button', { name: 'Geri Al' }).click()

        // Wait for a stable DOM element to confirm no navigation/loading occurred
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible()
        expect(postCount).toBe(0)
    })

    test('rollback onaylanırsa POST /imports/1/rollback gönderilir', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })

        // Register accept handler BEFORE clicking
        page.on('dialog', dialog => dialog.accept())

        const tamamlandiRow = page.locator('tr', { hasText: 'seferler_ocak.xlsx' }).first()

        const [request] = await Promise.all([
            page.waitForRequest(
                req => req.url().includes('/admin/imports/1/rollback') && req.method() === 'POST',
                { timeout: 8_000 }
            ),
            tamamlandiRow.getByRole('button', { name: 'Geri Al' }).click(),
        ])
        expect(request.method()).toBe('POST')
        expect(request.url()).toMatch(/\/admin\/imports\/1\/rollback$/)
    })

    test('rollback onayı sonrası başarı bildirimi görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/veri')
        await expect(page.getByText('seferler_ocak.xlsx').first()).toBeVisible({ timeout: 10_000 })

        page.on('dialog', dialog => dialog.accept())

        const tamamlandiRow = page.locator('tr', { hasText: 'seferler_ocak.xlsx' }).first()
        await tamamlandiRow.getByRole('button', { name: 'Geri Al' }).click()

        // Wait for success toast — either the title or message text
        await expect(
            page.getByText('İşlem başarıyla geri alındı').or(page.getByText('Başarılı')).first()
        ).toBeVisible({ timeout: 8_000 })
    })

    test('boş durum — "Aktarım geçmişi bulunamadı" görünür', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/imports/history**', r =>
            r.fulfill(json([]))
        )
        await page.goto('/admin/veri')
        await expect(page.getByText('Aktarım geçmişi bulunamadı').first()).toBeVisible({ timeout: 8_000 })
    })

    test('backend 500 döndüğünde sayfa çökmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/imports/history**', r =>
            r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Internal Server Error"}' })
        )
        await page.goto('/admin/veri')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        // If ErrorBoundary triggers, the page heading disappears
        await expect(page.getByRole('heading', { name: 'Veri İçe Aktarım ve Rollback' })).toBeVisible({ timeout: 5_000 })
        // Page body stays intact
        await expect(page.locator('body')).toBeVisible()
    })
})
