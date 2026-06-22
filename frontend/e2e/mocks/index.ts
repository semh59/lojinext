import { Page } from '@playwright/test'

// ── Shared mock data ────────────────────────────────────────────────────────

export const MOCK_TRIP = {
    id: 1, sefer_no: 'S-001', tarih: '2025-01-15', saat: '08:00',
    guzergah_id: 1, cikis_yeri: 'İstanbul', varis_yeri: 'Ankara', mesafe_km: 450,
    arac_id: 1, sofor_id: 1, dorse_id: null,
    durum: 'PLANLANDI', net_kg: 20000, bos_agirlik_kg: 10000, dolu_agirlik_kg: 30000,
    tuketim: null, dagitilan_yakit: null, baslangic_km: null, bitis_km: null,
    created_at: '2025-01-15T08:00:00',
}

export const MOCK_FUEL = {
    id: 1, tarih: '2025-01-15', arac_id: 1, arac_plaka: '34ABC01', plaka: '34ABC01',
    istasyon: 'BP Atatürk', litre: 150, fiyat_tl: 38.5, toplam_tutar: 5775,
    km_sayac: 125000, fis_no: 'F001', created_at: '2025-01-15T10:00:00',
    depo_durumu: 'Doldu', durum: 'Onaylandı',
}

export const MOCK_VEHICLE = {
    id: 1, plaka: '34ABC01', marka: 'Mercedes', model: 'Actros', yil: 2020,
    yakit_tipi: 'DIZEL', tank_kapasitesi: 600, hedef_tuketim: 30, dingil_sayisi: 3,
    aktif: true, bos_agirlik_kg: 8000, hava_direnc_katsayisi: 0.7,
    on_kesit_alani_m2: 9.0, motor_verimliligi: 0.9, lastik_direnc_katsayisi: 0.007,
    maks_yuk_kapasitesi_kg: 25000,
}

export const MOCK_DRIVER = {
    id: 1, ad_soyad: 'Ahmet Yılmaz', telefon: '05301234567',
    ehliyet_sinifi: 'CE', aktif: true, score: 1.0, manual_score: 1.0,
    ise_baslama: '2020-01-01', created_at: '2020-01-01T00:00:00',
}

export const MOCK_LOCATION = {
    id: 1, cikis_yeri: 'İstanbul', varis_yeri: 'Ankara', mesafe_km: 450,
    sure_saat: 5.0, ucret_tl: 3500, aktif: true, created_at: '2025-01-01T00:00:00',
    cikis_lat: 41.0082, cikis_lon: 28.9784,
    varis_lat: 39.9208, varis_lon: 32.8541,
    tahmini_sure_saat: 5, zorluk: 'Normal', ascent_m: 0, descent_m: 0,
    flat_distance_km: 0, otoban_mesafe_km: 0, sehir_ici_mesafe_km: 0, notlar: '',
}

const TRIP_LIST = { items: [MOCK_TRIP], meta: { total: 34, skip: 0, limit: 20 } }
const TRIP_STATS = {
    total_count: 34, completed_count: 29, cancelled_count: 2,
    planned_count: 3, in_progress_count: 0,
    total_distance_km: 12500, avg_consumption: 31.5,
}

const FUEL_LIST = { items: [MOCK_FUEL], total: 1 }
const FUEL_STATS = {
    avg_price: 38.5,
    total_consumption: 5301.5, total_cost: 204109.0,
    avg_consumption: 31.2, total_distance: 16985.0,
}

const VEHICLE_LIST = { items: [MOCK_VEHICLE], total: 1, page: 1, pages: 1 }
const VEHICLE_STATS = { total: 1, aktif: 1, pasif: 0 }

const DRIVER_LIST = [MOCK_DRIVER]

const LOCATION_LIST = { items: [MOCK_LOCATION], total: 1 }

const DASHBOARD_STATS = {
    total_vehicles: 1, active_vehicles: 1,
    total_drivers: 1, active_drivers: 1,
    total_trips: 1, total_fuel_cost: 5775,
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function json(body: unknown) {
    return { status: 200, contentType: 'application/json', body: JSON.stringify(body) }
}
function created(body: unknown) {
    return { status: 201, contentType: 'application/json', body: JSON.stringify(body) }
}
function noContent() {
    return { status: 204 }
}

// NOTE: All patterns use /api/v1/ prefix to avoid matching Vite dynamic imports
// (e.g. **/fuel/** would also match /src/pages/FuelPage.tsx in Playwright's glob)

export async function setupTripMocks(page: Page) {
    await page.route('**/api/v1/trips/**', r => {
        const method = r.request().method()
        const url = r.request().url()
        if (url.includes('/stats')) return r.fulfill(json(TRIP_STATS))
        if (url.includes('/fuel-performance')) return r.fulfill(json([]))
        if (url.includes('/timeline')) return r.fulfill(json([]))
        if (url.includes('/return') && method === 'POST') return r.fulfill(created(MOCK_TRIP))
        if (method === 'GET') return r.fulfill(json(TRIP_LIST))
        if (method === 'POST') return r.fulfill(created(MOCK_TRIP))
        if (method === 'PATCH') return r.fulfill(json({ ...MOCK_TRIP, durum: 'TAMAMLANDI' }))
        if (method === 'DELETE') return r.fulfill(noContent())
        return r.continue()
    })
    await setupDropdownMocks(page)
}

export async function setupFuelMocks(page: Page) {
    await page.route('**/api/v1/fuel/**', r => {
        const method = r.request().method()
        const url = r.request().url()
        if (url.includes('/stats')) return r.fulfill(json(FUEL_STATS))
        if (url.includes('/excel')) return r.fulfill(noContent())
        if (method === 'GET') return r.fulfill(json(FUEL_LIST))
        if (method === 'POST') return r.fulfill(created(MOCK_FUEL))
        if (method === 'PUT') return r.fulfill(json(MOCK_FUEL))
        if (method === 'DELETE') return r.fulfill(noContent())
        return r.continue()
    })
    await page.route('**/api/v1/vehicles/**', r => {
        if (r.request().method() === 'GET') return r.fulfill(json(VEHICLE_LIST))
        return r.continue()
    })
}

export async function setupVehicleMocks(page: Page) {
    await page.route('**/api/v1/vehicles/**', r => {
        const method = r.request().method()
        const url = r.request().url()
        if (url.includes('/stats')) return r.fulfill(json(VEHICLE_STATS))
        if (url.includes('/excel')) return r.fulfill(noContent())
        if (method === 'GET') return r.fulfill(json(VEHICLE_LIST))
        if (method === 'POST') return r.fulfill(created(MOCK_VEHICLE))
        if (method === 'PUT') return r.fulfill(json(MOCK_VEHICLE))
        if (method === 'DELETE') return r.fulfill(noContent())
        return r.continue()
    })
}

export async function setupDriverMocks(page: Page) {
    await page.route('**/api/v1/drivers/**', r => {
        const method = r.request().method()
        const url = r.request().url()
        if (url.includes('/stats')) return r.fulfill(json({ total: 1, aktif: 1, pasif: 0 }))
        if (url.includes('/excel')) return r.fulfill(noContent())
        if (url.includes('/score') && method === 'POST') return r.fulfill(json({ success: true, new_score: 1.0 }))
        if (url.includes('/performance')) return r.fulfill(json({}))
        if (method === 'GET') return r.fulfill(json(DRIVER_LIST))
        if (method === 'POST') return r.fulfill(created(MOCK_DRIVER))
        if (method === 'PUT') return r.fulfill(json(MOCK_DRIVER))
        if (method === 'DELETE') return r.fulfill(noContent())
        return r.continue()
    })
}

export async function setupLocationMocks(page: Page) {
    await page.route('**/api/v1/locations/**', r => {
        const method = r.request().method()
        const url = r.request().url()
        if (url.includes('/unique-names')) return r.fulfill(json(['İstanbul', 'Ankara']))
        if (url.includes('/route-info')) return r.fulfill(json({
            distance_km: 450, duration_min: 300, difficulty: 'Normal',
            ascent_m: 0, descent_m: 0, flat_distance_km: 200,
            otoban_mesafe_km: 200, sehir_ici_mesafe_km: 50, route_analysis: null,
        }))
        if (url.includes('/geocode')) return r.fulfill(json([]))
        if (url.includes('/analyze') && method === 'POST') return r.fulfill(json({ success: true }))
        if (url.includes('/search')) return r.fulfill(json([]))
        if (method === 'GET') return r.fulfill(json(LOCATION_LIST))
        if (method === 'POST') return r.fulfill(created(MOCK_LOCATION))
        if (method === 'PUT') return r.fulfill(json(MOCK_LOCATION))
        if (method === 'DELETE') return r.fulfill(noContent())
        return r.continue()
    })
}

export async function setupFleetPageMocks(page: Page) {
    await setupVehicleMocks(page)
    await setupDriverMocks(page)
    await page.route('**/api/v1/trailers/**', r => {
        const method = r.request().method()
        const url = r.request().url()
        if (url.includes('/export')) return r.fulfill(noContent())
        if (method === 'GET') return r.fulfill(json({ items: [], data: [], total: 0 }))
        if (method === 'POST') return r.fulfill(created({ id: 1 }))
        if (method === 'PUT') return r.fulfill(json({ id: 1 }))
        if (method === 'DELETE') return r.fulfill(noContent())
        return r.continue()
    })
    await page.route('**/api/v1/reports/**', r => {
        const url = r.request().url()
        if (url.includes('/dashboard')) return r.fulfill(json(DASHBOARD_STATS))
        if (url.includes('/consumption-trend')) return r.fulfill(json([]))
        return r.fulfill(json(DASHBOARD_STATS))
    })
}

export async function setupReportsMocks(page: Page) {
    await page.route('**/api/v1/reports/**', r => {
        const url = r.request().url()
        if (url.includes('/dashboard')) return r.fulfill(json(DASHBOARD_STATS))
        if (url.includes('/consumption-trend')) return r.fulfill(json([]))
        return r.fulfill(noContent())
    })
    await page.route('**/api/v1/advanced-reports/**', r => r.fulfill(json([])))
}

async function setupDropdownMocks(page: Page) {
    await setupLocationMocks(page)
    await setupVehicleMocks(page)
    await setupDriverMocks(page)
    await page.route('**/api/v1/trailers/**', r => {
        if (r.request().method() === 'GET')
            return r.fulfill(json({ items: [], data: [], total: 0 }))
        return r.continue()
    })
}
