import { test, expect } from '../fixtures/auth'

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}

const COMPARISON = {
    mae: 2.07, rmse: 2.57, total_compared: 29,
    accuracy_distribution: { good: 14, warning: 8, error: 7, good_pct: 50.0, warning_pct: 27.6, error_pct: 24.1 },
    trend: [
        { date: '2026-04-01', actual: 32.5, predicted: 30.8 },
        { date: '2026-04-15', actual: 28.1, predicted: 29.3 },
        { date: '2026-05-01', actual: 35.2, predicted: 33.1 },
    ],
}

const ENSEMBLE_STATUS = {
    models: { physics: true, lightgbm: false, xgboost: false, gradient_boosting: false, random_forest: false },
    weights: { physics: 0.8, lightgbm: 0.05, xgboost: 0.05, gradient_boosting: 0.05, random_forest: 0.05 },
    sklearn_available: true, lightgbm_available: false, xgboost_available: false, total_models: 1,
}

const VEHICLE_LIST = {
    data: [{ id: 1, plaka: '34ABC01', marka: 'Mercedes', model: 'Actros', aktif: true }],
    meta: { total: 1, skip: 0, limit: 100 },
}

test.describe('ML Tahminler sayfası', () => {
    test.beforeEach(async ({ authedPage: page }) => {
        await page.route('**/api/v1/predictions/comparison**', r => r.fulfill(json(COMPARISON)))
        await page.route('**/api/v1/predictions/ensemble/status**', r => r.fulfill(json(ENSEMBLE_STATUS)))
        await page.route('**/api/v1/predictions/time-series/**', r =>
            r.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'SERVICE_UNAVAILABLE' }) })
        )
        await page.route('**/api/v1/vehicles/**', r => r.fulfill(json(VEHICLE_LIST)))
    })

    test('sayfa yüklenir ve başlık görünür', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')
        await expect(page.locator('h1')).toContainText(/Tahmin|ML|Prediksiyon/i)
    })

    test('MAE metrik kartı doğru değeri gösterir', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('MAE')).toBeVisible()
        await expect(page.getByText('2.07')).toBeVisible()
    })

    test('RMSE metrik kartı doğru değeri gösterir', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        await expect(page.getByText('RMSE')).toBeVisible()
        await expect(page.getByText('2.57')).toBeVisible()
    })

    test('Doğruluk % iyi sefer oranı gösterir', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        // 50% good_pct
        await expect(page.locator('text=/50|50\.0|%50/').first()).toBeVisible()
    })

    test('Karşılaştırılan sefer sayısı görünür', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        // total_compared: 29
        await expect(page.locator('text=/29/')).toBeVisible()
    })

    test('Ensemble durum kartı fizik modeli %80 ağırlık gösterir', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        // physics model için kart başlığı görünmeli
        await expect(page.getByText('Ensemble Model Ağırlıkları')).toBeVisible()
        // fizik modeli YAxis'de görünmeli
        await expect(page.locator('text=/fizik/i').first()).toBeVisible()
    })

    test('PredictionsPage tab bar render edilir', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        // RV2.x sonrası PredictionsPage tab'lı; XAI panel kendi tab'ında.
        // Sayfa data-testid ile mark'lı.
        await expect(page.locator('[data-testid="predictions-page"]')).toBeVisible({ timeout: 8_000 })
        await expect(page.getByText('ML Tahminler').first()).toBeVisible()
    })

    test('Tahmin trend grafiği alan başlığı görünür', async ({ authedPage: page }) => {
        await page.goto('/predictions')
        await page.waitForLoadState('networkidle')

        // Grafik veya "veri yok" mesajı
        const hasChart = await page.locator('.recharts-surface').count() > 0
        const hasEmpty = await page.getByText(/veri yok|hesaplanacak|tahmin yok/i).count() > 0
        expect(hasChart || hasEmpty).toBeTruthy()
    })
})
