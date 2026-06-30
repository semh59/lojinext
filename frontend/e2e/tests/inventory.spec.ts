/**
 * UI Element Inventory — Her sayfadaki tüm interaktif elementleri toplar.
 *
 * Çalıştır: npx playwright test e2e/tests/inventory.spec.ts
 * Çıktı:    e2e/reports/ui-inventory.json
 *
 * Bu spec normal suite'e dahil DEĞİLDİR (aşağıdaki testIgnore).
 * Gap raporu için önce bu spec çalıştırılır, sonra:
 *   node e2e/scripts/gap-report.mjs
 */

import { test, expect } from '../fixtures/auth'
import type { Page } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ── Tüm uygulama route'ları ─────────────────────────────────────────────────

const ROUTES = [
    { path: '/',                      label: 'Home (rol bazlı)' },
    { path: '/today',                 label: 'Bugün (TodayPage)' },
    { path: '/trips',                 label: 'Seferler' },
    { path: '/fuel',                  label: 'Yakıt' },
    { path: '/fleet',                 label: 'Filo (Araçlar)' },
    { path: '/fleet?tab=trailers',    label: 'Filo (Dorseler)' },
    { path: '/drivers',               label: 'Şoförler' },
    { path: '/locations',             label: 'Güzergahlar' },
    { path: '/coaching',              label: 'Koçluk' },
    { path: '/reports',               label: 'Raporlar (Studio)' },
    { path: '/reports/legacy',        label: 'Raporlar (Legacy)' },
    { path: '/route-lab',             label: 'Güzergah Lab' },
    { path: '/executive',             label: 'Executive (Cockpit)' },
    { path: '/insights/fleet',        label: 'Filo İçgörüleri' },
    { path: '/monitoring',            label: 'İzleme' },
    { path: '/profile',               label: 'Profil' },
    { path: '/alerts',                label: 'Uyarılar' },
    { path: '/predictions',           label: 'Tahminler' },
    { path: '/legacy-dashboard',      label: 'Dashboard (Legacy)' },
    { path: '/maintenance',           label: 'Bakım' },
    { path: '/admin',                 label: 'Admin Genel Bakış' },
    { path: '/admin/konfig',          label: 'Admin Konfigürasyon' },
    { path: '/admin/kullanicilar',    label: 'Admin Kullanıcılar' },
    { path: '/admin/roller',          label: 'Admin Roller' },
    { path: '/admin/dogruluk',        label: 'Admin Doğruluk' },
    { path: '/admin/atama',           label: 'Admin Atama' },
    { path: '/admin/ml',              label: 'Admin ML Yönetimi' },
    { path: '/admin/analitik',        label: 'Admin Analitik' },
    { path: '/admin/veri',            label: 'Admin Veri Yönetimi' },
    { path: '/admin/saglik',          label: 'Admin Sistem Sağlığı' },
    { path: '/admin/bildirimler',     label: 'Admin Bildirimler' },
]

// ── Geniş API mock — tüm endpoint'leri minimal veriyle yanıtlar ─────────────

async function setupBroadMocks(page: Page) {
    const json = (body: unknown) => ({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
    })

    // Tek MOCK_VEHICLE ve MOCK_DRIVER — list endpoint'leri için
    const VEHICLE = { id: 1, plaka: '34ABC01', marka: 'Mercedes', model: 'Actros', yil: 2020, aktif: true, yakit_tipi: 'DIZEL', tank_kapasitesi: 600, hedef_tuketim: 30, dingil_sayisi: 3, bos_agirlik_kg: 8000, hava_direnc_katsayisi: 0.7, on_kesit_alani_m2: 9.0, motor_verimliligi: 0.9, lastik_direnc_katsayisi: 0.007, maks_yuk_kapasitesi_kg: 25000 }
    const DRIVER  = { id: 1, ad_soyad: 'Ahmet Yılmaz', telefon: '05301234567', ehliyet_sinifi: 'CE', aktif: true, score: 1.0, manual_score: 1.0, ise_baslama: '2020-01-01', created_at: '2020-01-01T00:00:00' }
    const TRIP    = { id: 1, sefer_no: 'S-001', tarih: '2025-01-15', saat: '08:00', cikis_yeri: 'İstanbul', varis_yeri: 'Ankara', mesafe_km: 450, durum: 'PLANLANDI', arac_id: 1, sofor_id: 1, net_kg: 20000, bos_agirlik_kg: 10000, dolu_agirlik_kg: 30000 }
    const FUEL    = { id: 1, tarih: '2025-01-15', arac_id: 1, arac_plaka: '34ABC01', plaka: '34ABC01', istasyon: 'BP', litre: 150, fiyat_tl: 38.5, toplam_tutar: 5775, km_sayac: 125000, fis_no: 'F001', created_at: '2025-01-15T10:00:00', depo_durumu: 'Doldu', durum: 'Onaylandı' }
    const ROLE    = { id: 2, ad: 'operator', yetkiler: ['sefer:goruntule'], kullanici_sayisi: 3, olusturulma_tarihi: '2025-01-01' }
    const USER    = { id: 2, kullanici_adi: 'user1', ad_soyad: 'Test Kullanıcı', rol: { ad: 'operator' }, aktif: true, created_at: '2025-01-01' }
    const IMPORT  = { id: 1, dosya_adi: 'seferler.xlsx', aktarim_tipi: 'sefer', baslama_zamani: '2025-01-15T10:00:00', durum: 'tamamlandi', basarili: 10, hatali: 0, toplam: 10 }
    const ANOMALY = { id: 1, tip: 'yakit_kacagi', aciklama: 'Anormal tüketim', siddet: 'warning', durum: 'open', arac_id: 1, created_at: '2025-01-15T10:00:00', acknowledged_at: null, resolved_at: null }
    const MAINTENANCE = { id: 1, arac_id: 1, bakim_tipi: 'PERIYODIK', planlanan_tarih: '2026-07-01', tamamlandi: false, notlar: '', arac_plaka: '34ABC01' }
    const TRIAGE  = { items: [{ id: 1, category: 'anomaly', severity: 'critical', title: 'Yakıt açığı', description: 'Açıklama', entity_id: 1 }], active_trips_count: 5, completed_today_count: 12 }

    await page.route('**/api/v1/**', (route) => {
        const url  = route.request().url()
        const meth = route.request().method()

        // Auth — fixture'ın kendi handler'ına bırak
        if (url.includes('/auth/')) return route.continue()

        // Specific response shapes
        if (url.includes('/trips/') && url.includes('/stats'))       return route.fulfill(json({ total_count: 34, completed_count: 29, cancelled_count: 2, planned_count: 3, in_progress_count: 0, total_distance_km: 12500, avg_consumption: 31.5 }))
        if (url.includes('/fuel') && url.includes('/stats'))         return route.fulfill(json({ avg_price: 38.5, total_consumption: 5301, total_cost: 204109, avg_consumption: 31.2, total_distance: 16985 }))
        if (url.includes('/vehicles') && url.includes('/stats'))     return route.fulfill(json({ total: 1, aktif: 1, pasif: 0 }))
        if (url.includes('/drivers') && url.includes('/stats'))      return route.fulfill(json({ total: 1, aktif: 1, pasif: 0 }))
        if (url.includes('/vehicles/inspection-alerts'))             return route.fulfill(json({ expiring: [], overdue: [] }))
        if (url.includes('/trailers'))                               return route.fulfill(json(meth === 'GET' ? { items: [], total: 0 } : {}))
        if (url.includes('/trips'))    return route.fulfill(json(meth === 'GET' ? { items: [TRIP], meta: { total: 1, skip: 0, limit: 20 } } : TRIP))
        if (url.includes('/fuel'))     return route.fulfill(json(meth === 'GET' ? { items: [FUEL], total: 1 } : FUEL))
        if (url.includes('/vehicles')) return route.fulfill(json(meth === 'GET' ? { items: [VEHICLE], total: 1, page: 1, pages: 1 } : VEHICLE))
        if (url.includes('/drivers'))  return route.fulfill(json(meth === 'GET' ? { data: [DRIVER], meta: { total: 1 } } : DRIVER))
        if (url.includes('/locations') && url.includes('/unique'))   return route.fulfill(json(['İstanbul', 'Ankara']))
        if (url.includes('/locations') && url.includes('/route-info')) return route.fulfill(json({ distance_km: 450, duration_min: 300 }))
        if (url.includes('/locations')) return route.fulfill(json(meth === 'GET' ? { items: [], total: 0 } : {}))
        if (url.includes('/admin/roles'))      return route.fulfill(json(meth === 'GET' ? { roles: [ROLE] } : ROLE))
        if (url.includes('/admin/users'))      return route.fulfill(json(meth === 'GET' ? [USER] : USER))
        if (url.includes('/admin/imports'))    return route.fulfill(json(meth === 'GET' ? [IMPORT] : {}))
        if (url.includes('/admin/configs'))    return route.fulfill(json([{ key: 'ANOMALY_Z_THRESHOLD', value: '3.0', description: 'Z eşik değeri' }]))
        if (url.includes('/admin/analytics'))  return route.fulfill(json({ period_days: 30, total_views: 1240, top_routes: [{ route: '/trips', count: 450 }], bottom_routes: [{ route: '/route-lab', count: 5 }] }))
        if (url.includes('/anomalies') && url.includes('/stats'))    return route.fulfill(json({ total: 3, open: 2, by_type: { yakit_kacagi: 2, rota_sapmasi: 1 } }))
        if (url.includes('/anomalies')) return route.fulfill(json(meth === 'GET' ? { items: [ANOMALY], total: 1 } : {}))
        if (url.includes('/maintenance') || url.includes('/bakim'))  return route.fulfill(json(meth === 'GET' ? { items: [MAINTENANCE], total: 1 } : {}))
        if (url.includes('/coaching/effectiveness'))  return route.fulfill(json({ period_days: 30, sent_count: 12, improvement_rate: 0.65 }))
        if (url.includes('/coaching'))               return route.fulfill(json({}))
        if (url.includes('/reports/executive'))      return route.fulfill(json({ value: 81, label: 'FVI', period: 'month' }))
        if (url.includes('/reports/insights'))       return route.fulfill(json({ period: 'month', fuel_consumption_l: 5000, fuel_cost_tl: 200000 }))
        if (url.includes('/reports/dashboard'))      return route.fulfill(json({ total_vehicles: 1, active_vehicles: 1, total_drivers: 1, active_drivers: 1, total_trips: 34, total_fuel_cost: 204109 }))
        if (url.includes('/reports'))                return route.fulfill(json([]))
        if (url.includes('/predictions'))            return route.fulfill(json({ mae: 2.1, rmse: 3.4, accuracy_pct: 82, compared_count: 120 }))
        if (url.includes('/simulate'))               return route.fulfill(json({ total_km: 451, total_l: 135, total_eta_sec: 18000, avg_l_per_100km: 30, elevation_coverage_pct: 85, segments: [] }))
        if (url.includes('/today/triage'))           return route.fulfill(json(TRIAGE))
        if (url.includes('/preferences'))            return route.fulfill(json({ items: [] }))
        if (url.includes('/users'))                  return route.fulfill(json(meth === 'GET' ? [USER] : {}))
        if (url.includes('/system-health') || url.includes('/saglik')) return route.fulfill(json({ db: 'ok', redis: 'ok', celery: 'ok' }))
        if (url.includes('/notifications') || url.includes('/bildirimler')) return route.fulfill(json(meth === 'GET' ? [] : {}))

        // Catch-all
        return route.fulfill(json({}))
    })
}

// ── DOM element extractor ────────────────────────────────────────────────────

interface UIElement {
    tag: string
    text: string
    aria: string
    inputType: string
    disabled: boolean
    role: string
}

async function extractElements(page: Page): Promise<UIElement[]> {
    return page.evaluate(() => {
        const results: UIElement[] = []
        const seen = new Set<string>()

        const nodes = document.querySelectorAll<HTMLElement>(
            'button, [role="button"], input[type="submit"], input[type="checkbox"], input[type="radio"], select, a[href]'
        )

        for (const el of nodes) {
            const tag   = el.tagName.toLowerCase()
            let text    = ''
            if (tag === 'select') {
                const selectEl = el as HTMLSelectElement
                const selectedOpt = selectEl.options[selectEl.selectedIndex]
                text = selectedOpt?.textContent?.trim().replace(/\s+/g, ' ').slice(0, 100) ?? ''
            } else {
                text = el.textContent?.trim().replace(/\s+/g, ' ').slice(0, 100) ?? ''
            }
            const aria  = el.getAttribute('aria-label') ?? el.getAttribute('title') ?? ''
            const iType = (el as HTMLInputElement).type ?? ''
            const role  = el.getAttribute('role') ?? ''

            const label = (text || aria).trim()
            if (!label) continue

            // SVG-only / icon-only butonları atla (metin yok)
            const hasOnlyIcons = text.length === 0 && !aria
            if (hasOnlyIcons) continue

            // Gizli elementler
            const style = window.getComputedStyle(el)
            if (style.display === 'none' || style.visibility === 'hidden') continue
            if (el.closest('[hidden]')) continue

            const key = `${tag}:${text}:${aria}`
            if (seen.has(key)) continue
            seen.add(key)

            results.push({
                tag,
                text,
                aria,
                inputType: iType,
                disabled: (el as HTMLButtonElement).disabled ?? false,
                role,
            })
        }

        return results
    })
}

// Modal expansion şu an devre dışı — sayfa navigasyonu tetiklenirse context crash'e yol açıyor.
// v2'de her route için fresh page açarak implemente edilecek.
interface ModalInventory {
    trigger: string
    elements: UIElement[]
}

// ── Ana test ─────────────────────────────────────────────────────────────────

test.describe.configure({ mode: 'serial' })

test('UI element inventory @inventory', async ({ authedPage: page }) => {
    test.slow() // Timeout'u 3x artır

    await setupBroadMocks(page)

    const inventory: Array<{
        route: string
        label: string
        url: string
        elements: UIElement[]
        modals: ModalInventory[]
        error?: string
    }> = []

    for (const route of ROUTES) {
        try {
            await page.goto(route.path, { waitUntil: 'domcontentloaded', timeout: 15_000 })
            // Kısa settle süresi — skeleton loader'ların geçmesi için
            await page.waitForTimeout(400)

            const currentUrl = page.url()
            const expectedPath = route.path.split('?')[0]
            const actualPath = new URL(currentUrl).pathname
            const normExpected = expectedPath.replace(/\/$/, '')
            const normActual = actualPath.replace(/\/$/, '')
            const isRedirect = normExpected !== normActual

            const elements   = isRedirect ? [] : await extractElements(page)

            inventory.push({
                route: route.path,
                label: route.label,
                url: currentUrl,
                elements,
                modals: [],
            })

            console.log(`✓ ${route.label}: ${elements.length} element`)
        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            console.error(`✗ ${route.label}: ${msg.slice(0, 100)}`)
            inventory.push({ route: route.path, label: route.label, url: '', elements: [], modals: [], error: msg })
        }
    }

    // Raporu kaydet
    const reportsDir = path.join(__dirname, '..', 'reports')
    fs.mkdirSync(reportsDir, { recursive: true })

    const outputPath = path.join(reportsDir, 'ui-inventory.json')
    fs.writeFileSync(outputPath, JSON.stringify(inventory, null, 2), 'utf-8')

    const totalElements = inventory.reduce((n, r) => n + r.elements.length, 0)
    const totalModals   = inventory.reduce((n, r) => n + r.modals.length, 0)
    const failedRoutes  = inventory.filter(r => r.error).length

    console.log(`\n📦 Inventory tamamlandı:`)
    console.log(`   ${inventory.length} route | ${totalElements} element | ${totalModals} modal`)
    console.log(`   ${failedRoutes} route başarısız`)
    console.log(`   Kaydedildi: ${outputPath}`)

    // Test olarak her zaman geçer — veri toplama amaçlı
    expect(inventory.length).toBeGreaterThan(0)
})
