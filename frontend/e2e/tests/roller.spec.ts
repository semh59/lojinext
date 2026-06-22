import { test, expect } from '../fixtures/auth'

const MOCK_ROLES = [
    { id: 1, ad: 'super_admin', yetkiler: { 'sefer:read': true, 'sefer:write': true, 'sefer:onayla': true } },
    { id: 2, ad: 'admin', yetkiler: { 'sefer:read': true, 'kullanici_goruntule': true } },
    { id: 3, ad: 'operator', yetkiler: { 'sefer:read': true } },
    { id: 4, ad: 'muhasebe', yetkiler: { 'sefer:read': true, 'yakit:write': true } },
]

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

test.describe('Roller sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/roles/**', r => {
            const method = r.request().method()
            if (method === 'GET') return r.fulfill(json(MOCK_ROLES))
            if (method === 'POST') return r.fulfill({
                status: 201,
                contentType: 'application/json',
                body: JSON.stringify({ id: 5, ad: 'yeni_rol', yetkiler: { 'sefer:read': true } }),
            })
            if (method === 'PUT') return r.fulfill(json({ ...MOCK_ROLES[3], ad: 'muhasebe_v2' }))
            if (method === 'DELETE') return r.fulfill({ status: 204 })
            return r.continue()
        })
    })

    test('sayfa yüklenir ve rol listesi görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await page.waitForLoadState('networkidle', { timeout: 15_000 })
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('operator').first()).toBeVisible()
        await expect(page.getByText('muhasebe').first()).toBeVisible()
    })

    test('"Henüz rol yok" görünmemeli — mock format doğruysa', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        // Liste render edildi mi önce doğrula — yoksa 'Henüz rol yok' yokluğu vacuous pass olur
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText('Henüz rol yok')).toHaveCount(0)
    })

    test('"Yeni Rol" butonu görünür ve modal açar', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        const newBtn = page.getByRole('button', { name: /yeni rol/i })
        await expect(newBtn).toBeVisible({ timeout: 5_000 })
        await newBtn.click()
        await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5_000 })
    })

    test('boş form submit — "Rol adı en az 2 karakter" hatası gösterir', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni rol/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })
        // Save button label is "Oluştur" in create mode
        await dialog.getByRole('button', { name: /oluştur|güncelle|kaydet/i }).first().click()
        await expect(dialog.getByText(/en az 2 karakter/i).first()).toBeVisible({ timeout: 5_000 })
    })

    test('ad dolu ama yetki seçilmeden submit — "En az bir yetki seçin" hatası', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni rol/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })
        // Fill rol adı — the input has placeholder "ör. operasyon_yonetici"
        const adInput = dialog.locator('input[placeholder*="operasyon"]')
        await adInput.fill('yeni_rol')
        // Permissions are toggle buttons (not checkboxes); submit without selecting any
        await dialog.getByRole('button', { name: /oluştur|güncelle|kaydet/i }).first().click()
        await expect(dialog.getByText(/en az bir yetki/i).first()).toBeVisible({ timeout: 5_000 })
    })

    test('yeni rol oluşturma — ad + yetki seçilip POST gönderilir', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })
        await page.getByRole('button', { name: /yeni rol/i }).click()
        const dialog = page.getByRole('dialog')
        await expect(dialog).toBeVisible({ timeout: 5_000 })

        // Fill rol adı
        const adInput = dialog.locator('input[placeholder*="operasyon"]')
        await adInput.fill('yeni_rol')

        // Permissions are <button type="button"> toggles — click the first one (sefer:read)
        const firstPerm = dialog.getByRole('button', { name: 'sefer:read' })
        await firstPerm.click()

        const [request] = await Promise.all([
            page.waitForRequest(
                req => req.url().includes('/admin/roles') && req.method() === 'POST',
                { timeout: 8_000 }
            ),
            dialog.getByRole('button', { name: /oluştur/i }).first().click(),
        ])
        expect(request.method()).toBe('POST')
        const body = JSON.parse(request.postData() ?? '{}')
        expect(body.ad).toBe('yeni_rol')
        expect(body.yetkiler['sefer:read']).toBe(true)
    })

    test('korumalı roller (super_admin, admin) için Düzenle/Sil butonu gizli', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('super_admin').first()).toBeVisible({ timeout: 10_000 })

        // super_admin satırı — Düzenle ve Sil title'lı butonlar olmamalı
        const superAdminRow = page.locator('tr', { hasText: 'super_admin' }).first()
        await expect(superAdminRow.locator('[title="Düzenle"]')).toHaveCount(0)
        await expect(superAdminRow.locator('[title="Sil"]')).toHaveCount(0)

        // admin satırı da korumalı — aynı kural geçerli
        const adminRow = page.locator('tr', { hasText: /^admin$/ }).first()
        await expect(adminRow.locator('[title="Düzenle"]')).toHaveCount(0)
        await expect(adminRow.locator('[title="Sil"]')).toHaveCount(0)
    })

    test('korumsuz rol (operator) için Düzenle/Sil butonları görünür', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('operator').first()).toBeVisible({ timeout: 10_000 })

        // operator satırı — aksiyon butonları görünür olmalı
        const operatorRow = page.locator('tr', { hasText: 'operator' }).first()
        await expect(operatorRow.locator('[title="Düzenle"]')).toBeVisible({ timeout: 5_000 })
        await expect(operatorRow.locator('[title="Sil"]')).toBeVisible({ timeout: 5_000 })
    })

    test('sil butonu tıklanınca onay modalı açılır', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('operator').first()).toBeVisible({ timeout: 10_000 })

        const operatorRow = page.locator('tr', { hasText: 'operator' }).first()
        await operatorRow.locator('[title="Sil"]').click()

        // Confirm modal — title "Rolü Sil" içermeli
        const deleteDialog = page.getByRole('dialog')
        await expect(deleteDialog).toBeVisible({ timeout: 5_000 })
        await expect(deleteDialog.getByText(/rolü sil/i)).toBeVisible()
        // "Sil" confirm button and "İptal" button must both be present
        await expect(deleteDialog.getByRole('button', { name: /^sil$/i })).toBeVisible()
        await expect(deleteDialog.getByRole('button', { name: 'İptal' })).toBeVisible()
    })

    test('silme onayında DELETE isteği gönderilir', async ({ authedPage: page }) => {
        await page.goto('/admin/roller')
        await expect(page.getByText('operator').first()).toBeVisible({ timeout: 10_000 })

        const operatorRow = page.locator('tr', { hasText: 'operator' }).first()
        await operatorRow.locator('[title="Sil"]').click()

        const deleteDialog = page.getByRole('dialog')
        await expect(deleteDialog).toBeVisible({ timeout: 5_000 })

        const [request] = await Promise.all([
            page.waitForRequest(
                req => req.url().includes('/admin/roles') && req.method() === 'DELETE',
                { timeout: 8_000 }
            ),
            deleteDialog.getByRole('button', { name: /^sil$/i }).click(),
        ])
        expect(request.method()).toBe('DELETE')
        expect(request.url()).toMatch(/\/roles\/3$/)  // operator's id = 3 — exact trailing segment
    })

    test('backend 500 döndüğünde sayfa crash etmez', async ({ authedPage: page }) => {
        await page.route('**/api/v1/admin/roles/**', r =>
            r.fulfill({
                status: 500,
                contentType: 'application/json',
                body: JSON.stringify({ detail: 'Internal Server Error' }),
            })
        )
        await page.goto('/admin/roller')
        await page.waitForLoadState('domcontentloaded', { timeout: 15_000 })
        // ErrorBoundary wraps the page — should not show generic crash, page structure must stay intact
        await expect(page.locator('text=/Something went wrong/i')).toHaveCount(0)
    })
})
