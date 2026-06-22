#!/usr/bin/env node
/**
 * E2E Gap Report — UI inventory vs mevcut spec'ler
 *
 * Kullanım:
 *   node e2e/scripts/gap-report.mjs
 *   node e2e/scripts/gap-report.mjs --json        # makine okunabilir çıktı
 *   node e2e/scripts/gap-report.mjs --min-score 0.5   # score < 0.5 olan route'ları vurgula
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.join(__dirname, '..')

// ── Arg parsing ─────────────────────────────────────────────────────────────
const args = process.argv.slice(2)
const JSON_MODE  = args.includes('--json')
const MIN_SCORE  = parseFloat(args.find(a => a.startsWith('--min-score='))?.split('=')[1] ?? '0') || 0
const SHOW_ALL   = args.includes('--all')  // normalde sadece untested olanları göster

// ── Inventory yükle ──────────────────────────────────────────────────────────
const inventoryPath = path.join(ROOT, 'reports', 'ui-inventory.json')
if (!fs.existsSync(inventoryPath)) {
    console.error('❌  ui-inventory.json bulunamadı.')
    console.error('    Önce çalıştır: npx playwright test e2e/tests/inventory.spec.ts')
    process.exit(1)
}

const inventory = JSON.parse(fs.readFileSync(inventoryPath, 'utf-8'))

// ── Spec dosyalarını yükle ───────────────────────────────────────────────────
const specsDir = path.join(ROOT, 'tests')
const specFiles = fs.readdirSync(specsDir)
    .filter(f => f.endsWith('.spec.ts') && f !== 'inventory.spec.ts')

// Her spec'in tam içeriği
const specContents = {}
for (const f of specFiles) {
    specContents[f] = fs.readFileSync(path.join(specsDir, f), 'utf-8')
}
const allSpecText = Object.values(specContents).join('\n')

// ── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

/** Bir route'un herhangi bir spec tarafından test edilip edilmediğini kontrol et */
function routeIsTested(routePath) {
    // page.goto('/trips') veya equivalent çağrı var mı?
    // Hem single hem double quote, hem tam hem prefix match
    const escaped = routePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const patterns = [
        new RegExp(`goto\\(['"\`]${escaped}['"\`]`),
        new RegExp(`goto\\(['"\`]${escaped}[?#]`),
    ]
    return patterns.some(p => p.test(allSpecText))
}

/** Bir spec'in belirli bir route'u test edip etmediği */
function specTestsRoute(specContent, routePath) {
    const escaped = routePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return new RegExp(`goto\\(['"\`]${escaped}`).test(specContent)
}

/** Element text'inin herhangi bir spec'te geçip geçmediğini kontrol et */
function elementIsTested(text, ariaLabel, route) {
    if (!text && !ariaLabel) return false

    const labels = [text, ariaLabel].filter(Boolean)

    // Önce bu route'u test eden spec'lerde ara
    const relevantSpecs = Object.entries(specContents)
        .filter(([, content]) => specTestsRoute(content, route))
        .map(([, content]) => content)

    const searchIn = relevantSpecs.length > 0 ? relevantSpecs.join('\n') : allSpecText

    return labels.some(label => {
        // Label 2 karakterden kısaysa atla (false positive'leri önle)
        if (label.length < 2) return false

        // Spec'te string literal olarak geçiyor mu?
        const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/'/g, "\\'")
        const inSingleQ = new RegExp(`'[^']*${escaped}[^']*'`, 'i').test(searchIn)
        const inDoubleQ = new RegExp(`"[^"]*${escaped}[^"]*"`, 'i').test(searchIn)
        const inTemplate = new RegExp(`\`[^\`]*${escaped}[^\`]*\``, 'i').test(searchIn)
        const inRegex = new RegExp(`/${escaped.slice(0, 20)}`, 'i').test(searchIn)

        return inSingleQ || inDoubleQ || inTemplate || inRegex
    })
}

// Sidebar/layout nav linkleri — her sayfada aynı şekilde görünen, sayfa-spesifik değil
// navigation.spec.ts zaten bunları kapsar; gap report'da gürültü oluştururlar
const LAYOUT_NAV_TEXTS = new Set([
    'bugün', 'trips', 'canlı takip', 'fuel', 'bakım',
    'araçlar & dorseler', 'şoförler', 'locations', 'filo içgörü',
    'anomaliler', 'ml tahminler', 'koçluk', 'strategic cockpit',
    'rapor stüdyosu', 'güzergah lab', 'administration',
])

/** Bir element'in muhtemelen önemsiz olup olmadığı (nav, logo, error boundary vs.) */
function isNoise(el) {
    const text = el.text.toLowerCase().trim()

    // Sidebar nav linkleri
    if (el.tag === 'a' && LAYOUT_NAV_TEXTS.has(text)) return true
    // Kullanıcı profil linki (dinamik, "Super Administratorsuper_admin" gibi)
    if (el.tag === 'a' && text.includes('super administrator')) return true
    // ErrorBoundary — sayfa çökmüş, mock yanlış
    if (text === 'sistemi yeniden başlat' || text === 'ana sayfaya dön') return true
    // Genel gürültü
    const NOISE = ['login', 'logout', 'çıkış', 'anasayfa', 'favicon', 'logo',
                   'türkçe', 'english', 'dark', 'light', '...', '›', '‹', '×']
    return NOISE.some(n => text.includes(n)) || text.length <= 1
}

// ── Analiz ──────────────────────────────────────────────────────────────────

const report = {
    generatedAt: new Date().toISOString(),
    inventoryDate: fs.statSync(inventoryPath).mtime.toISOString(),
    specFiles: specFiles.length,
    routes: [],
    summary: {},
}

for (const page of inventory) {
    const { route, label, elements, modals, error } = page

    if (error) {
        report.routes.push({ route, label, error, score: 0, untested: [], tested: [] })
        continue
    }

    const allElements = [
        ...elements,
        ...modals.flatMap(m => m.elements),
    ].filter(el => !isNoise(el))

    const tested   = allElements.filter(el => elementIsTested(el.text, el.aria, route))
    const untested = allElements.filter(el => !elementIsTested(el.text, el.aria, route))

    const routeTested = routeIsTested(route)
    const score = allElements.length === 0 ? (routeTested ? 1 : 0)
                                           : tested.length / allElements.length

    report.routes.push({
        route,
        label,
        routeTested,
        total: allElements.length,
        testedCount: tested.length,
        score: Math.round(score * 100) / 100,
        untested: untested.map(el => ({ tag: el.tag, text: el.text || el.aria, disabled: el.disabled })),
        tested:   SHOW_ALL ? tested.map(el => ({ tag: el.tag, text: el.text || el.aria })) : [],
        modalTriggers: modals.map(m => m.trigger),
    })
}

// ── Özet istatistikler ───────────────────────────────────────────────────────

const untestedRoutes = report.routes.filter(r => !r.routeTested && !r.error)
const totalElements  = report.routes.reduce((n, r) => n + (r.total ?? 0), 0)
const totalTested    = report.routes.reduce((n, r) => n + (r.testedCount ?? 0), 0)
const globalScore    = totalElements > 0 ? Math.round((totalTested / totalElements) * 100) : 0

report.summary = {
    totalRoutes:    report.routes.length,
    untestedRoutes: untestedRoutes.length,
    totalElements,
    totalTested,
    totalUntested:  totalElements - totalTested,
    globalScore,
}

// ── Çıktı ────────────────────────────────────────────────────────────────────

if (JSON_MODE) {
    console.log(JSON.stringify(report, null, 2))
    process.exit(0)
}

// Terminal renkler
const C = {
    reset:  '\x1b[0m',
    bold:   '\x1b[1m',
    red:    '\x1b[31m',
    green:  '\x1b[32m',
    yellow: '\x1b[33m',
    cyan:   '\x1b[36m',
    gray:   '\x1b[90m',
}

const scoreColor = (s) => s >= 0.8 ? C.green : s >= 0.5 ? C.yellow : C.red
const pct = (s) => `${Math.round(s * 100)}%`

console.log(`\n${C.bold}════════════════════════════════════════════════`)
console.log(` E2E Kapsam Raporu`)
console.log(`════════════════════════════════════════════════${C.reset}`)
console.log(`${C.gray} Oluşturma: ${new Date().toLocaleString('tr-TR')}`)
console.log(` Inventory: ${report.inventoryDate.slice(0, 19).replace('T', ' ')}`)
console.log(` Spec dosyası: ${specFiles.length} adet${C.reset}\n`)

// ── 1. TEST EDİLMEYEN ROUTE'LAR ──────────────────────────────────────────────
if (untestedRoutes.length > 0) {
    console.log(`${C.bold}${C.red}▶ TEST EDİLMEYEN ROUTE'LAR (${untestedRoutes.length})${C.reset}`)
    for (const r of untestedRoutes) {
        console.log(`  ${C.red}✗${C.reset} ${r.route.padEnd(30)} ${C.gray}${r.label}${C.reset}`)
    }
    console.log()
} else {
    console.log(`${C.green}✓ Tüm route'lar en az bir spec tarafından kapsanıyor.${C.reset}\n`)
}

// ── 2. DÜŞÜK KAPSAMLI ROUTE'LAR ──────────────────────────────────────────────
const lowCoverage = report.routes
    .filter(r => !r.error && r.routeTested && r.score < (MIN_SCORE || 0.6) && r.total > 0)
    .sort((a, b) => a.score - b.score)

if (lowCoverage.length > 0) {
    console.log(`${C.bold}${C.yellow}▶ DÜŞÜK KAPSAMLI ROUTE'LAR (${pct(MIN_SCORE || 0.6)} altı)${C.reset}`)
    for (const r of lowCoverage) {
        const bar = '█'.repeat(Math.round(r.score * 10)) + '░'.repeat(10 - Math.round(r.score * 10))
        console.log(`  ${scoreColor(r.score)}${bar}${C.reset} ${pct(r.score).padStart(4)}  ${r.route.padEnd(28)} ${C.gray}${r.label}${C.reset}`)
    }
    console.log()
}

// ── 3. TEST EDİLMEYEN ELEMENTLER (route bazında) ─────────────────────────────
const routesWithGaps = report.routes
    .filter(r => r.untested && r.untested.length > 0)
    .sort((a, b) => a.score - b.score)

if (routesWithGaps.length > 0) {
    console.log(`${C.bold}▶ TEST EDİLMEYEN ELEMENTLER${C.reset}`)

    for (const r of routesWithGaps) {
        const icon = r.routeTested ? `${scoreColor(r.score)}◆${C.reset}` : `${C.red}✗${C.reset}`
        console.log(`\n  ${icon} ${C.bold}${r.route}${C.reset} ${C.gray}(${r.testedCount}/${r.total} element, ${pct(r.score)})${C.reset}`)

        for (const el of r.untested) {
            const dis = el.disabled ? ` ${C.gray}[disabled]${C.reset}` : ''
            console.log(`     ${C.gray}${el.tag.padEnd(8)}${C.reset} ${C.yellow}${el.text}${C.reset}${dis}`)
        }

        if (r.modalTriggers && r.modalTriggers.length > 0) {
            console.log(`     ${C.cyan}Modal içi:${C.reset} ${r.modalTriggers.join(', ')}`)
        }
    }
    console.log()
}

// ── 4. ÖZET ──────────────────────────────────────────────────────────────────
const { summary } = report
console.log(`${C.bold}════ ÖZET ════${C.reset}`)
console.log(`  Route'lar:   ${summary.totalRoutes} toplam, ${C.red}${summary.untestedRoutes} test yok${C.reset}`)
console.log(`  Elementler:  ${summary.totalElements} toplam`)
console.log(`  Test edilen: ${C.green}${summary.totalTested}${C.reset} (${scoreColor(summary.globalScore / 100)}${summary.globalScore}%${C.reset})`)
console.log(`  Eksik:       ${C.red}${summary.totalUntested}${C.reset}`)
console.log()

// ── 5. Dosyaya kaydet ─────────────────────────────────────────────────────────
const reportMdPath = path.join(ROOT, 'reports', 'gap-report.md')
const mdLines = [
    `# E2E Gap Report`,
    `> Oluşturma: ${new Date().toISOString()}`,
    ``,
    `## Özet`,
    `| Metrik | Değer |`,
    `|--------|-------|`,
    `| Toplam route | ${summary.totalRoutes} |`,
    `| Test yok | **${summary.untestedRoutes}** |`,
    `| Toplam element | ${summary.totalElements} |`,
    `| Test edilen | ${summary.totalTested} (${summary.globalScore}%) |`,
    `| Eksik | **${summary.totalUntested}** |`,
    ``,
    `## Test Edilmeyen Route'lar`,
    untestedRoutes.length === 0 ? '_Yok -- tum routelar kapsaniyor_' : untestedRoutes.map(r => `- \`${r.route}\` -- ${r.label}`).join('\n'),
    ``,
    `## Element Boşlukları (route bazında)`,
    ...routesWithGaps.map(r => [
        `### \`${r.route}\` — ${r.label} (${r.testedCount}/${r.total}, ${pct(r.score)})`,
        r.untested.map(el => `- **${el.tag}**: \`${el.text}\`${el.disabled ? ' _(disabled)_' : ''}`).join('\n'),
    ].join('\n')),
]

fs.writeFileSync(reportMdPath, mdLines.join('\n'), 'utf-8')
console.log(`${C.gray}Rapor kaydedildi: ${reportMdPath}${C.reset}\n`)

// Exit code: 0 (bilgi amaçlı, CI'yı kırmaz)
// CI'da hata vermek için: process.exit(summary.untestedRoutes > 0 ? 1 : 0)
