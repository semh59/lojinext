# Reports v2 — Derin İnceleme ve Mimari Önerisi

**Tarih:** 2026-05-27
**Status:** ANALYSIS (henüz uygulama planı değil)
**Tetikleyici:** Kullanıcı geri bildirimi (2026-05-26):
"genel yönetim ve rapor sayfasından memnun değilim, projeye uygun ve yeterli bulmuyorum."

Bu doküman v3 mini-planın **öncülü**: önce mevcut durumu objektif olarak
envanterleyip kök problemleri çıkarıyoruz; ondan sonra (kullanıcı onayıyla)
yapısal plan yazılacak.

---

## §0 TL;DR — 60 saniyelik özet

**Şu anki durum:**
- 3 ayrı "rapor benzeri" sayfa (`/`, `/reports`, `/executive`) + 7 admin sayfası
- A/B/C/D motorları zengin **insight** üretiyor (FVI, what-if, cross-feature,
  bus factor, bakım tahmini, koçluk etkisi, hırsızlık zararı, plan-wizard)
  ama bu insight'ların **çoğu mevcut Reports/Dashboard'larda görünmüyor**
- ReportsPage hâlâ "PDF/Cost/ROI/Vehicle Karşılaştırma" — klasik BI tablo
  dump'ı; AI motorlarının üretimini yansıtmıyor
- DashboardPage operasyonel (6 KPI + 2 chart); cross-feature impact yok
- "Yönetim" menüsü 7 alt sayfa içeriyor ama yarısı **yapılandırma**,
  diğer yarısı **iş süreç yönetimi** — kullanıcı bilgi mimarisi karışık

**Problem 3 katmanlı:**
1. **Bilgi mimarisi**: rapor/yönetim/dashboard sınırları belirsiz; aynı
   veriler farklı yerlerde
2. **AI insight kullanımı**: A-E'nin ürettiği değer yüzeye çıkmıyor
3. **Action-orientation eksik**: salt veri gösterimi var; "şu kararı şu
   kanıtla ver" formatı yok

**Çözüm vizyonu (3-katmanlı mimari):**
1. **Insight Hub** (yeni `/intelligence`) — AI insight'ların birleşik
   karar destek paneli
2. **Reports Studio** (`/reports` rewrite) — şablonlu rapor üretici +
   AI insight'larıyla zenginleştirilmiş export
3. **Admin Console** (`/admin/*` yeniden organize) — yalnız sistem
   yapılandırma; iş süreçleri (bakım, anomali, soruşturma) ilgili Reports
   sekmelerine taşınır

**Tahmini iş yükü (uygulama yapıldığında):** ~30-40 saat (önceki E
büyüklüğünde, frontend ağırlıklı).

---

## §1 Mevcut sayfaların envanteri

### 1.1 Ana navigasyon sayfaları

| Path | Dosya | Satır | Persona | Veri kaynağı | İçerik özet |
|---|---|---|---|---|---|
| `/` | DashboardPage.tsx | 121 | Operasyon Şefi | reportService, anomaly, prediction, trip | 6 KPI + Consumption chart + Anomaly widget + Bugünkü seferler |
| `/reports` | ReportsPage.tsx | 245 | Belirsiz | reportsApi | 4 sekme: PDF / Cost / ROI / Vehicle |
| `/executive` | ExecutivePage.tsx | E.8 commit | CEO/CFO, fleet_manager | executiveService (7 endpoint) | FVI + What-if + Carbon + Compliance + Cashflow + CrossFeature + BusFactor |
| `/alerts` | AlertsPage.tsx | — | Operasyon + Filo | anomaly + investigation | Yakıt kaçağı + Bakım + Soruşturma kanban |
| `/coaching` | CoachingPage.tsx | — | İK / Filo | coachingService | Şoför listesi + insight + send + effectiveness |
| `/predictions` | PredictionsPage.tsx | — | ML / Veri | predictionService | Tahmin gönderme + sonuç |

### 1.2 Admin sayfaları (`/admin/*`)

| Path | Dosya | Satır | Tip | Asıl amaç |
|---|---|---|---|---|
| `/admin` | OverviewPage.tsx | 198 | BI dashboard | 4 KPI + consumption chart + Telegram onay + operational health |
| `/admin/bakim` | BakimPage.tsx | — | İş süreci | Bakım uyarıları + D.1-D.3 predictions takvim + drawer |
| `/admin/ml` | MLYonetimPage.tsx | 236 | Sistem | Eğitim kuyruğu + manuel trigger |
| `/admin/saglik` | SistemSaglikPage.tsx | 597 | Sistem | Sağlık + error stream + Layer × Severity filter |
| `/admin/veri` | VeriYonetimPage.tsx | 172 | Sistem | Import history + rollback |
| `/admin/bildirimler` | BildirimlerPage.tsx | 266 | Sistem | Notification kural CRUD |
| `/admin/konfigurasyon` | KonfigurasyonPage.tsx | 211 | Sistem | Settings + flag UI |
| `/admin/kullanicilar` | KullanicilarPage.tsx | 416 | Sistem | Kullanıcı + rol CRUD |

**Tespit:** admin/ klasörü iki farklı işlevi karıştırıyor:
- **İş süreci** (anomali aksiyonu, bakım yönetimi): `/admin/bakim`
- **Sistem** (kullanıcı, rol, ML model, import, sağlık): kalan 6

Doğru ayrım: iş süreç sayfaları ana navigasyona (örn. `/maintenance`,
`/investigations`) taşınmalı.

### 1.3 Veri kaynakları (backend endpoint'leri)

#### Mevcut reports endpoint'leri (`/reports/*`)

| Endpoint | Tip | Kullanım |
|---|---|---|
| `GET /reports/dashboard` | KPI özet | DashboardPage + OverviewPage |
| `GET /reports/consumption-trend` | 12 aylık trend | Dashboard + Overview |
| `GET /advanced-reports/pdf/fleet-summary` | PDF | ReportsPage export |
| `GET /advanced-reports/pdf/vehicle/{id}` | PDF | ReportsPage export |
| `GET /advanced-reports/pdf/driver-comparison` | PDF | ReportsPage export |
| `GET /advanced-reports/cost/period` | Maliyet kırılım | PeriodCostBreakdown |
| `GET /advanced-reports/cost/trend` | Maliyet trendi | CostAnalysisChart |
| `GET /advanced-reports/cost/vehicle-comparison` | Araç tüketim | ReportsPage Vehicle tab |
| `GET /advanced-reports/cost/savings-potential` | Tasarruf potansiyeli | SavingsPotentialCard |
| `GET /advanced-reports/cost/roi` | ROI hesap | ROICalculator |
| `GET /advanced-reports/excel/*` | Excel export | ReportsPage |

#### E.8 strategic cockpit (yeni eklenenler)

| Endpoint | Kullanım |
|---|---|
| `GET /reports/executive/kpi` | FVI |
| `POST /reports/executive/what-if` | 3 senaryo |
| `GET /reports/executive/carbon` | Karbon raporu |
| `GET /reports/executive/compliance` | Muayene heatmap |
| `GET /reports/executive/cashflow` | 90g projeksiyon |
| `GET /reports/executive/cross-feature` | D.4+A.5+B aggregat |
| `GET /reports/executive/bus-factor` | Top-N şoför kayıp |
| `GET /reports/executive/pdf` | CEO 1-pager |

#### A/B/C/D feature endpoint'leri

A: `/coaching/*` (insights, send, effectiveness)
B: `/admin/investigations/*` (CRUD + patterns)
C: `/trips/plan-wizard` (öneri)
D: `/admin/maintenance/*` (predictions, ics, alerts)

---

## §2 Kök problem analizi

### 2.1 Bilgi mimarisi sorunları

#### Sorun A — "Rapor", "Dashboard", "Yönetim" sınırları belirsiz

Kullanıcı "Aylık yakıt raporunu görmek istiyorum" derse:
- `/` → ConsumptionChart var (son 12 ay aggregat)
- `/reports/cost` → CostAnalysisChart var (yine 12 ay)
- `/admin/overview` → ConsumptionTrend var (aynı veri)
- `/executive/cashflow` → ileri projeksiyon var

**Aynı veri 3-4 yerde, farklı görsellerle, hangisinin "doğru kaynak" olduğu belirsiz.**

#### Sorun B — Cross-feature impact tek yerde

E.6 `CrossFeatureSavings` widget'ı yalnız `/executive`'de. Filo müdürü
sezgisel olarak burayı aramaz; `/reports` veya `/alerts`'a bakar.

#### Sorun C — Action items dağınık

Kullanıcı "Bugün ne yapmalıyım?" sorusuna cevap için:
- `/` → KPI (statik)
- `/alerts` → anomali listesi
- `/admin/bakim` → bakım uyarıları
- `/coaching` → şoför listesi (manuel send)

Bunlar tek bir **Triage** ekranında birleştirilmemiş. Linear'ın "Triage"
veya Datadog Watchdog gibi otomatik öncelikli liste yok.

#### Sorun D — Persona dağılımı eksik

| Persona | Bugün ne kullanıyor? | İhtiyaç |
|---|---|---|
| Operasyon Şefi | Dashboard + Alerts + Coaching | Tek panel: günün eylem listesi |
| Filo Müdürü | Reports + Coaching + Drivers + Fleet | Cross-feature insight + kıyaslama |
| CFO / CEO | Executive | (kapsanıyor, E.8) |
| İK Müdürü | Drivers + Coaching | Şoför karneleri, A.5 detay |
| Compliance Auditor | yok | E.4'ün dışında **hiç sayfa yok** |
| Sistem Yöneticisi | admin/* | (kapsanıyor) |

**3 persona için sayfa yok** veya **eksik**.

### 2.2 AI insight kullanım gap'i

A/B/C/D motorlarında zengin AI **kanıtlanmış** insight üretildi. Bunlar
**şu an** nereye yansıyor:

| AI çıktısı | Üretildiği yer | Yansıdığı sayfalar | Gap |
|---|---|---|---|
| D.1 bakım tahmini | `/admin/maintenance/predictions` | BakimPage, ExecutivePage cashflow | DashboardPage'de yok, ReportsPage'de yok |
| D.4 maintenance_factor | predict_consumption pipeline | E.6 cross-feature widget | Sefer detayında "Bakım %X fazla yakıyor" yok |
| A.5 koçluk effectiveness | `/coaching/effectiveness` | CoachingPage + E.6 widget | Şoför karnesinde drill yok |
| B suspicion_score | FuelTheftClassifier | InvestigationsKanban | Anomaly listesinde "şüpheli skor" badge yok |
| B real_theft loss | E.6 aggregat | ExecutivePage | Aylık güvenlik raporu yok |
| C plan-wizard | TripFormModal wizard | Yalnız sefer açma akışında | Geçmiş tavsiyeler/kullanım istatistiği yok |
| E.1 FVI | `/executive/kpi` | ExecutivePage | DashboardPage'de yok (operasyon görmeli) |
| E.2 what-if | `/executive/what-if` | ExecutivePage | Dashboard hızlı erişim CTA'sı yok |
| E.3 carbon | `/executive/carbon` | ExecutivePage | Compliance auditor için ayrı rapor yok |
| E.7 bus factor | `/executive/bus-factor` | ExecutivePage | DriversPage'de görünürlük yok |

**Sonuç:** AI motorlarının yarattığı değer **bir tek sayfada toplandı**
(`/executive`); diğer personalar bu içgörülerden faydalanmıyor.

### 2.3 Action-orientation eksiği

Modern dashboard'lar 4 katmanlı:
1. **Observation**: KPI/tablo (mevcut sayfalar burada)
2. **Insight**: "Şu trend X yönünde"
3. **Diagnosis**: "Bu, Y'nin sonucu"
4. **Action**: "Z yap"

Mevcut sayfalarda çoğu zaman 1+2 var; 3 ve 4 eksik.

Örnek:
- `/coaching` insight var ama "şu şoföre şu mesajı gönder" CTA tek tık değil
- `/alerts` anomali var ama "bu sefer için investigation aç" tek tık değil
- `/admin/bakim` bakım uyarısı var ama "araca bakım planla" CTA aynı sayfadan yapılabiliyor (görece iyi)

### 2.4 Teknik gaplar

#### a. URL state + paylaşım

- Tablolarda filter/sort/pagination URL'e yansımıyor (TripsPage istisna)
- "Bu raporu link olarak paylaş" özelliği yok
- Bookmark'lanabilir görünüm yok (ör. "Filo müdürü haftalık snapshot")

#### b. Export çeşitliliği sınırlı

- Mevcut: PDF + Excel (klasik BI dump)
- Eksik: **AI insight gömülü** PDF, CSV insight export, PowerPoint, e-posta planı
- Audit raporu (KVKK uyumlu, retention politikası ile) eksik

#### c. Comparison/benchmark yapısı zayıf

- Periyod karşılaştırma (Q-on-Q, Y-on-Y) yok
- Filo-içi araç karşılaştırma sadece ReportsPage Vehicle tab'ında (3 ay sınırlı)
- Sektör benchmark sadece E.3 carbon'da

#### d. Real-time vs cache karışıklığı

- Dashboard staleTime 1 dk (anomali/critical için yetersiz)
- Reports/Executive 30 dk (operatör için fazla)
- WebSocket sadece `/monitoring`'te kullanılıyor

#### e. Görselleştirme çeşitliliği

- Yalnız Recharts (Line/Bar/Pie); FullCalendar D.3'te tek kullanım
- Eksik görseller: heatmap (karbon × araç), sankey (kayıp akışları),
  network/force-directed (bus factor görselleştirmesi), histogram (skor dağılımı),
  box plot (tüketim dağılımı)

#### f. Mobil UX

- Layout responsive ama mobile-first değil
- PWA değil
- "Mobil filo müdürü" persona için optimize değil

### 2.5 Kullanıcı geri bildirim döngüsü yok

- "Bu insight işe yaradı mı?" thumbs up/down yok
- A.5 effectiveness ölçümü dışında AI insight kalite skoru ölçülmüyor
- Kullanıcı kendi raporlarını oluşturup paylaşamıyor

---

## §3 Persona derinleştirme

### 3.1 Operasyon Şefi (Persona: Ahmet)

**Günlük rutini:**
- Sabah 08:00 — bugünkü aktif sefer listesi
- Gün boyu — anomali bildirimleri + acil müdahaleler
- Akşam — günlük performans özeti

**Şu an kullandığı sayfalar:**
DashboardPage, AlertsPage, MonitoringPage, CoachingPage

**Reports v2'de yapılmalı:**
- **"Bugün" sekmesi** — gün için tek panel: aktif seferler + acil anomali +
  şoför uyarısı + bakım deadline'ları (öncelik sıralı)
- "Triage" tarzı: her item için tek-tık aksiyon
- Bildirim çalan items'ı işaretle / sustur
- Mobil/PWA optimize (operasyon şefi yolda kullanır)

### 3.2 Filo Müdürü (Persona: Burcu)

**Haftalık rutini:**
- Pazartesi — geçen hafta filo verimi
- Ortalama — şoför skor değişimleri
- Cuma — gelecek haftaya plan

**Şu an kullandığı sayfalar:**
ReportsPage (sınırlı), CoachingPage, DriversPage, FleetPage

**Reports v2'de yapılmalı:**
- **"Filo İçgörü" sekmesi** — FVI + alt skorlar (E.1 reuse) + cross-feature (E.6 reuse)
- Aylık/haftalık performans karşılaştırma (period-over-period)
- Top performer / bottom performer şoför listesi (anonimleştirilmiş + drill)
- "Haftalık aksiyon planı" — D.1 bakım takvimi + A koçluk önerileri
- Excel "Filo Müdürü Brifing" şablonu (AI insight'ları gömülü)

### 3.3 İK Müdürü (Persona: Cem)

**Aylık rutini:**
- Şoför karneleri (skor + ihlal sayısı + iyileşme)
- Eğitim ihtiyacı tespit
- Bordro/prim hesabı için skor verisi

**Şu an kullandığı sayfalar:**
DriversPage, CoachingPage

**Reports v2'de yapılmalı:**
- **"Şoför İK" sekmesi** — şoför × performans matris
- Per-şoför karne PDF (aylık)
- A.5 effectiveness detayı: hangi şoför hangi öneriyi alıp ne kadar
  iyileşti
- Anonimleştirilmiş benchmark
- (V2'de Takograf gelirse) AETR ihlal sayısı + uyum yüzdesi

### 3.4 Compliance Auditor (Persona: Demet)

**3-aylık rutini:**
- Muayene + ehliyet uyumu denetimi
- Karbon raporu (yıllık)
- KVKK uyum kontrolü (audit log)
- Yıllık iç denetim

**Şu an kullandığı sayfalar:**
**HIÇBIRI** — sayfa yok.

**Reports v2'de yapılmalı:**
- **"Uyum Defteri" sekmesi** (yeni) — muayene + ehliyet + karbon + audit log
- E.4 compliance heatmap reuse (genişletilmiş)
- E.3 carbon report reuse + yıllık özet
- audit_log filtrelenebilir + export (CSV)
- "Yıllık Compliance Raporu" PDF şablonu
- (V2'de Takograf) AETR uyum raporu

### 3.5 CFO / CEO (Persona: Esra)

**Aylık rutini:**
- 1-sayfa özet (FVI + cashflow + cross-feature + stratejik öneri)
- Yatırım kararları (E.2 what-if)
- Aylık board toplantısı slide'ları

**Şu an kullandığı sayfalar:**
ExecutivePage (E.8 yapıldı) — **iyi kapsanıyor**.

**Reports v2'de iyileştirme:**
- "Kıyaslamalar" sekmesi (yeni) — geçen ay/yıl vs bu ay/yıl
- PowerPoint / Google Slides export
- "What-if çalıştır → board slide'ına ekle" workflow

---

## §4 Modern dashboard pattern karşılaştırması

Endüstri standartları:

### 4.1 Linear "Triage" (issue management)

**Pattern:** Tek panel, AI'nin önceliklendirdiği eylem listesi.
- Her item: kanıt + öneri + tek-tık aksiyon
- "Skip", "Snooze", "Done" hızlı butonlar
- Klavye kısayolları

**Reports v2'de kullanım:** Operasyon Şefi "Bugün" sekmesi için.

### 4.2 Notion Gallery (database view)

**Pattern:** Kart bazlı kuratör; her kart bir insight/rapor.
- Filtre/sort/group çoklu boyut
- Cover image + tag + property
- Kart açıldığında detay sayfası

**Reports v2'de kullanım:** Reports Studio şablonları kart galerisi.

### 4.3 Tableau Pulse (natural language insight)

**Pattern:** "Geçen hafta X arttı çünkü Y" gibi doğal dilde anomali açıklamaları.
- LLM ile sentence generation
- Drill: "Neden?" tek-tık daha derin analiz

**Reports v2'de kullanım:** GROQ_API_KEY mevcut → A koçluk engine pattern'i
ile her insight için NL açıklama üretilebilir (PII'siz).

### 4.4 Stripe Sigma (SQL-based reporting)

**Pattern:** Kullanıcı SQL yazarak özel raporlar oluşturabilir.
- Şablon kütüphanesi + custom query
- Sonuç tablo + chart preview + export

**Reports v2'de kullanım:** Power user / Compliance auditor için
"Özel sorgu" sekmesi (v2 — opsiyonel).

### 4.5 Datadog Watchdog (anomaly explanation)

**Pattern:** Otomatik anomali tespit + neden-sonuç ilişkisi.
- "Bu metrik %X arttı, ilgili olabilir: Y, Z" otomatik analiz
- Sıklık + confidence + impact tahmini

**Reports v2'de kullanım:** Anomaly genişletmesi — mevcut FuelTheftClassifier
pattern'i ile B kategorisi genişletilmiş.

### 4.6 Mixpanel/Amplitude Funnels

**Pattern:** Aşamalı funnel görselleştirme.

**Reports v2'de kullanım:** A koçluk: gönderilen → okunan → uygulanan →
ölçülen iyileşme funnel'ı.

---

## §5 Reports v2 mimarisi (önerilen)

### 5.1 Üç katmanlı yapı

```
┌─────────────────────────────────────────────────────┐
│  Sidebar Navigation                                  │
├─────────────────────────────────────────────────────┤
│  📊 Bugün       (operasyon şefi — triage)           │
│  🎯 Filo İçgörü (filo müdürü — cross-feature)       │
│  👥 Şoför İK    (ik müdürü — karne)                 │
│  ✅ Uyum Defteri (compliance auditor)                │
│  🚀 Strategic   (CEO/CFO — mevcut /executive)       │
│  📄 Raporlar    (reports studio — şablonlar+export) │
├─────────────────────────────────────────────────────┤
│  Mevcut operasyonel sayfalar (Seferler, Yakıt, ...)  │
├─────────────────────────────────────────────────────┤
│  ⚙ Sistem (yeniden organize edilmiş admin)          │
└─────────────────────────────────────────────────────┘
```

### 5.2 "Bugün" sayfası (Triage)

**Path:** `/today` (varsayılan landing → DashboardPage'i replace eder)

**İçerik:**

```
┌────────────────────────────────────────────────┐
│ Bugün — 27 Mayıs 2026                          │
├────────────────────────────────────────────────┤
│ ⚠ 3 Acil Eylem                                │
│   • [Şoför Ali] son 4.5sa kesintisiz sürmüş   │
│     [Mola hatırlatıcı gönder] [Çöz]           │
│   • [Araç 34 ABC 123] muayene gecikti         │
│     [Randevu planla] [Atla]                   │
│   • [Yakıt anomali #42] sapma %35             │
│     [İncele] [Soruşturma aç]                  │
│                                                │
│ 📋 7 Bekleyen Aksiyon                          │
│ 🔵 23 Aktif Sefer (durum: 18 yolda, 5 mola)    │
│ ✅ 12 Tamamlanan (bugün)                       │
├────────────────────────────────────────────────┤
│ Quick Actions                                  │
│ [Sefer planla] [Anomali ara] [Şoför ara]      │
└────────────────────────────────────────────────┘
```

**Veri kaynakları:**
- Anomaly service (open + critical filter)
- D.1 predictions (sıralı, en yakın 7)
- A koçluk önerileri (high-priority filter)
- Active trips
- Audit log son 24 saat

**Yeni backend endpoint gerek:**
- `GET /reports/today/triage` — tüm action items aggregat (priority queue)

### 5.3 "Filo İçgörü" sayfası

**Path:** `/insights/fleet`

**İçerik:**
- E.1 FVI card (üst) — tek-tık → ExecutivePage detayı
- Period-over-period karşılaştırma (bu hafta vs geçen)
- Top 3 performer + bottom 3 performer şoför (anonim PII'siz, drill ile detay)
- E.6 cross-feature widget reuse
- D.1 yaklaşan bakım takvimi (haftalık)
- A koçluk haftalık özet (kaç gönderildi, ölçülmüş etki)

**Yeni backend endpoint:**
- `GET /reports/insights/fleet?period=week|month` — aggregat
- Period karşılaştırma için: `compare_with=last_week|last_month` parametresi

### 5.4 "Şoför İK" sayfası

**Path:** `/insights/hr`

**İçerik:**
- Şoför × ay matris (skor + sefer + L/100km + ihlal — V2'de takograf)
- A.5 effectiveness drill: gönderilen koçluk → score delta histogram
- "Karne PDF üret" butonu (aylık)
- Eğitim aday listesi (skor düşük + iyileşme yok)
- Anonimleştirilmiş benchmark

**Yeni backend endpoint:**
- `GET /drivers/{id}/karne?month=YYYY-MM` — aylık şoför karnesi data
- `GET /reports/pdf/driver-karne/{id}?month=YYYY-MM` — PDF

### 5.5 "Uyum Defteri" sayfası

**Path:** `/insights/compliance`

**İçerik:**
- E.4 compliance heatmap reuse (genişletilmiş)
- E.3 carbon report reuse + 12 aylık trend
- Audit log timeline (filtrelenebilir)
- "Yıllık Compliance PDF" şablonu
- (V2'de Takograf) AETR ihlal sayısı + uyum yüzdesi

**Yeni backend endpoint:**
- `GET /reports/audit-log?from=X&to=Y&module=...` — audit log timeline
- `GET /reports/pdf/annual-compliance?year=Y` — yıllık compliance PDF

### 5.6 Reports Studio (mevcut `/reports` rewrite)

**Path:** `/reports` (değiştirilir, eski tab'lar şablona dönüşür)

**Konsept:** "Şablon Kütüphanesi + Kişiselleştirilmiş Builder"

```
┌──────────────────────────────────────────────────┐
│ Şablon Kütüphanesi                               │
├──────────────────────────────────────────────────┤
│ [CEO Aylık 1-Pager] [Filo Müdürü Haftalık]      │
│ [Şoför Karne] [Yıllık Compliance]                │
│ [Karbon Raporu] [What-if Sonucu]                 │
│ [Özel Sorgu] (v2)                                │
├──────────────────────────────────────────────────┤
│ Önizleme                                          │
│ [Şablon seçildikten sonra preview burada]        │
├──────────────────────────────────────────────────┤
│ Format: [PDF] [Excel] [CSV] [Email gönder]       │
│ Periyot: [Bu ay] [Geçen ay] [Özel tarih]         │
│ Filtreler: [Tüm filo] [Sadece şu araçlar]        │
│                                                   │
│ [Önizle] [Üret] [Kaydet ve Planla]              │
└──────────────────────────────────────────────────┘
```

**Yeni özellikler:**
- AI insight gömülü PDF (sadece tablo değil; LLM-üretilen özet metin)
- "Kaydet ve Planla" — Celery beat ile haftalık otomatik e-posta
- Email export (config'de SMTP)

### 5.7 Admin Console (yeniden organize)

**Path:** `/admin/*` ama menü yeniden adlandırılır

**Eski menü → Yeni menü:**

| Eski | Yeni konum |
|---|---|
| `/admin` (BI dashboard) | **Kaldır** — `/insights/fleet` zaten kapsıyor |
| `/admin/bakim` | `/maintenance` (ana menü, iş süreci) |
| `/admin/ml` | `/admin/system/ml` (Sistem alt-grubu) |
| `/admin/saglik` | `/admin/system/health` |
| `/admin/veri` | `/admin/system/data` |
| `/admin/bildirimler` | `/admin/system/notifications` |
| `/admin/konfigurasyon` | `/admin/system/config` |
| `/admin/kullanicilar` | `/admin/system/users` |

Menü hiyerarşisi:
- **Sistem** (sidebar group, sadece admin/super_admin)
  - Sistem Sağlık
  - Kullanıcı ve Roller
  - ML Modeller
  - Bildirimler
  - Veri Yönetimi
  - Konfigürasyon

---

## §6 Backend gereksinimleri

### 6.1 Yeni endpoint'ler

```
GET  /reports/today/triage              — bugünün acil aksiyonları
GET  /reports/insights/fleet?period=X   — filo içgörü aggregat
GET  /drivers/{id}/karne?month=YYYY-MM  — aylık şoför karne data
GET  /reports/pdf/driver-karne/{id}     — şoför karne PDF
GET  /reports/audit-log                 — audit log timeline (filtreli)
GET  /reports/pdf/annual-compliance     — yıllık compliance PDF
POST /reports/saved-views               — kullanıcı bookmark'ları
GET  /reports/saved-views               — kullanıcının kaydettiği görünümler
POST /reports/schedule                  — periyodik rapor schedule (Celery)
GET  /reports/schedule                  — aktif schedule listesi
```

### 6.2 Yeni tablolar (migration gerekli)

```sql
-- Bookmark / kullanıcı kaydettiği rapor görünümleri
CREATE TABLE saved_report_views (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES kullanicilar(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    page VARCHAR(40) NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Periyodik rapor scheduler
CREATE TABLE report_schedules (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES kullanicilar(id) ON DELETE CASCADE,
    template VARCHAR(40) NOT NULL,
    frequency VARCHAR(20) NOT NULL,  -- daily/weekly/monthly
    email VARCHAR(200),
    config JSONB,
    active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ
);

-- Insight kalitesi feedback
CREATE TABLE insight_feedback (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES kullanicilar(id),
    insight_type VARCHAR(40),
    insight_ref VARCHAR(60),   -- "fvi:2026-05-27", "what_if:fleet_renewal:1234"
    rating INT,                 -- -1, 0, +1
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 6.3 LLM entegrasyonu (Tableau Pulse-tarzı NL açıklamalar)

Mevcut Groq + DriverCoachingEngine pattern reuse:

```python
# app/core/ai/insight_narrator.py (yeni)
async def narrate_insight(
    insight_type: str, data: dict, locale: str = "tr"
) -> str:
    """Sayısal veri → tek cümle insan dilinde açıklama (PII'siz)."""
    # Groq LLM ile prompt template
    # Örnek çıktı: "Filo verimliliği geçen aya göre +%4 arttı; en büyük
    #              katkı koçluk programı (A.5 +%2.1)."
```

Cache: 1 saat (aynı veri için aynı açıklama).

### 6.4 Mevcut endpoint genişletmeleri

- `GET /coaching/effectiveness` → period parametresi + driver_id filter
- `GET /reports/dashboard` → cross-feature widget data eklenebilir
- `GET /admin/maintenance/predictions` → period summary stats eklenebilir

---

## §7 Frontend mimarisi

### 7.1 Yeni route yapısı

```tsx
// App.tsx (sonra)
<Route path="/" element={<Navigate to="/today" replace />} />  {/* eski dashboard taşındı */}
<Route path="/today" element={<TodayPage />} />                {/* yeni */}
<Route path="/insights/fleet" element={<FleetInsightsPage />} /> {/* yeni */}
<Route path="/insights/hr" element={<HRInsightsPage />} />       {/* yeni */}
<Route path="/insights/compliance" element={<ComplianceInsightsPage />} /> {/* yeni */}
<Route path="/executive" element={<ExecutivePage />} />        {/* var (E.8) */}
<Route path="/reports" element={<ReportsStudioPage />} />      {/* rewrite */}
<Route path="/admin/system/*" element={<AdminSystemLayout />}>  {/* yeniden organize */}
    <Route path="ml" element={<AdminMlPage />} />
    <Route path="health" element={<AdminHealthPage />} />
    {/* vb. */}
</Route>
```

### 7.2 Yeniden kullanılabilir bileşenler

Her insight kartı için ortak pattern:

```tsx
<InsightCard
    title="Filo Verimliliği Endeksi"
    confidence={0.85}
    metric={78}
    trend={+4}
    description="Geçen aya göre +4 puan; en büyük katkı koçluk."  // LLM
    actions={[
        { label: "Detay", to: "/executive" },
        { label: "PDF", onClick: ... },
    ]}
    feedback={(rating) => sendFeedback("fvi", rating)}
/>
```

Bu pattern Insight Hub ve Reports Studio'da reuse edilir.

### 7.3 Görselleştirme genişletmesi

Mevcut Recharts'a ek olarak (opsiyonel, v2):
- `react-heatmap-grid` — karbon × araç matris
- `recharts-funnel` — A koçluk funnel
- `d3-sankey` (Recharts üstüne wrapper) — kayıp akışları

### 7.4 Mobil/PWA

- `vite-plugin-pwa` ile service worker
- "Bugün" sayfası mobile-first redesign (operasyon şefi yolda)
- Push notification (Firebase Cloud Messaging) — kritik anomali için

---

## §8 Risk analizi

| Risk | Etki | Azaltma |
|---|---|---|
| Mevcut sayfalar kırılır | Kullanıcı kaybı | Gradual rollout: feature flag (`REPORTS_V2_ENABLED`), eski sayfalar paralel kalır 3 ay |
| Sidebar değişikliği muscle memory kırar | UX şikayet | URL alias'lar 6 ay korunur (`/admin` → redirect `/admin/system`) |
| Backend yeni endpoint yükü | Performans | Cache + N+1 önleme + benchmark gate |
| LLM narration cost | Bütçe | Groq cache 1h + free-tier limit gözlemi |
| Persona analizi yanlış | Yanlış optimizasyon | Beta kullanıcı testi (3-5 müşteri) |
| Reports Studio karmaşıklığı | Onboarding zorluğu | Şablon-first; "Özel sorgu" v3'e bırakılabilir |
| PWA + push notification | Browser uyumu | Progressive enhancement (yoksa fallback) |

---

## §9 Tahmini iş yükü

| Modül | Backend | Frontend | Test | Toplam |
|---|---|---|---|---|
| RV2.1 Today sayfası | 3h | 4h | 2h | 9h |
| RV2.2 Fleet İçgörü | 2h | 4h | 2h | 8h |
| RV2.3 Şoför İK | 3h | 4h | 2h | 9h |
| RV2.4 Compliance | 2h | 3h | 2h | 7h |
| RV2.5 Reports Studio | 4h | 6h | 3h | 13h |
| RV2.6 LLM narrator | 3h | 1h | 2h | 6h |
| RV2.7 Insight feedback | 2h | 2h | 1h | 5h |
| RV2.8 Saved views + schedule | 3h | 3h | 2h | 8h |
| RV2.9 Sidebar restructure | — | 2h | 1h | 3h |
| RV2.10 Migration + flag | 2h | — | 1h | 3h |

**Toplam tahmin:** ~71 saat (yaklaşık 9 mesai günü).

İlk MVP (RV2.1+2.2+2.5+2.9): ~33 saat.

---

## §10 Açık sorular (kullanıcıya)

Plan v3 yazılmadan önce bu 6 nokta karara bağlanmalı:

1. **MVP scope:** İlk teslim Today + Fleet İçgörü + Reports Studio rewrite
   mi yoksa hepsi tek seferde mi?
2. **LLM narration:** Groq API maliyetini kabul ediyor muyuz? (Cache 1h
   yeterli mi?)
3. **Periyodik rapor (e-posta):** SMTP konfigürasyonu mevcut mu? Yoksa
   bu kısım v2.1'e bırakılır mı?
4. **Mobil/PWA:** Önemli mi, v2.1'e mi bırakılır?
5. **Dashboard → Today rename:** Mevcut "/" route'unu "/today"'e yönlendirmek
   muscle memory'yi kırar. Alternatif: "/" altında Today görünür, eski
   dashboard "/legacy-dashboard" altında 3 ay korunur.
6. **Eski sayfaların kaderi:** ReportsPage tab'ları (PDF/Cost/ROI/Vehicle)
   Reports Studio şablonlarına dönüştürülecek; eski URL korunsun mu (alias)?

---

## §11 Sonraki adımlar

Bu doküman onaylanırsa:

1. **Yukarıdaki 6 soruyu karara bağla** (kullanıcı oturumu)
2. **v3 mini-plan yaz** (~1500-2000 satır, alt-görev RV2.1..RV2.10 detayı)
3. **Backlog'a kaydet** (gerekli ise) — sırasız değil, sıralı uygula

Bu inceleme dokümanı uygulama planı değildir; uygulama için ayrı bir
v3 dokümanı yazılır. Bu doküman **what (ne) ve why (neden)**'i kapsar;
v3 plan **how (nasıl)** ve **when (ne zaman)** olacak.
