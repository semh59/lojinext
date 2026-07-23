# Modül: analytics_executive

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Feature-E "Strategic Cockpit" — CEO/yönetim seviyesi filo analitikleri: Filo
Verimliliği Endeksi (FVI, E.1), what-if simülatörü (E.2, 3 senaryo), filo
karbon raporu (E.3), compliance heatmap (E.4, muayene), 90 gün cashflow
projeksiyonu (E.5), cross-feature etki toplayıcı (E.6), bus-factor risk
analizi (E.7), CEO 1-pager PDF (E.9). Ayrıca maliyet analizi (dönem/aylık
trend/araç karşılaştırma/ROI) ve dashboard/insight üretimi.

Bu modül **saf read-model** — kendi tablosuna yazmaz (`bulk_create_alerts`
istisnası aşağıda). `AnalizRepository` (`infrastructure/
executive_read_models.py`) 7 modülün tablosuna raw-SQL SELECT yapar —
dosya bazında sistemin en yoğun raw-SQL kaynağı.

NE YAPMAZ: sayfa-görüntüleme analitiği (`page_views` — reports'un işi,
aşağıdaki "page_views tutarsızlığı çözüldü" notuna bakın), driver bulk
metrikleri (`get_bulk_driver_metrics` — driver'ın işi, aşağıya bakın),
gerçek ML tahmin pipeline'ı (prediction_ml, dalga 13'te taşındı — bu
modülün `get_training_seferler` (dead) SİLİNDİ; `save_model_params`/
`get_model_params`/`get_daily_summary_for_ml` bilinçli olarak BURADA
KALDI, aşağıya bakın).

## Public API (public.py imzaları)

```python
# Fleet Efficiency Index (E.1)
gather_fvi_inputs(uow, days_back=30) -> dict            # DB read
compute_fvi(*, fuel_avg, fuel_target, ..., previous_fvi=None) -> FleetEfficiencyBreakdown  # saf

# What-if (E.2)
simulate_fleet_renewal(uow, *, max_age_years, replacement_cost_per_vehicle_tl, ...) -> WhatIfResult
simulate_training_program(uow, *, improvement_pct, training_cost_per_driver_tl, ...) -> WhatIfResult
simulate_route_portfolio(uow, *, drop_bottom_n, iterations=100, ...) -> WhatIfResult

# Carbon (E.3)
compute_fleet_carbon(uow, *, period_days=30) -> FleetCarbonReport

# Compliance (E.4)
scan_compliance(uow, *, days_horizon=90) -> list[ComplianceItem]

# Cashflow (E.5)
project_cashflow(uow, *, horizon_days=90, diesel_price_tl=50.0, ...) -> CashflowProjection

# Cross-feature (E.6)
aggregate_cross_feature(uow, *, period_days=90, diesel_price_tl=50.0) -> CrossFeatureImpact

# Bus factor (E.7)
compute_bus_factor(uow, *, n=3, diesel_price_tl=50.0) -> BusFactorReport

# Cost analytics (CostAnalyzer'dan free function'lara — B.1)
calculate_period_cost(start_date, end_date, arac_id=None) -> CostBreakdown
get_monthly_trend(months=12) -> list[dict]
get_vehicle_cost_comparison(months=3) -> list[dict]
calculate_savings_potential(target_consumption=30.0) -> dict
calculate_roi(investment, months=12, target_consumption=30.0) -> dict

# Repository
AnalizRepository, get_analiz_repo(session=None) -> AnalizRepository
```

**Önemli**: `AnalizService`/`DashboardService`/`CostAnalyzer`/`InsightEngine`
sınıfları YOK. `CostAnalyzer`/`InsightEngine` free function'lara bölündü
(B.1, location/notification/fleet/fuel/driver/auth_rbac/reports ile aynı
karar — ikisinin de constructor'ı meaningful state taşımıyordu:
`CostAnalyzer.__init__` `pass`, `InsightEngine`'in hiç constructor'ı yoktu).

## 🔴 `AnalizService`/`DashboardService` SİLİNDİ (dead code, kullanıcı kararı 2026-07-16)

Dedektif denetiminde bulundu: `container.analiz_service` property'si ve
`DashboardService`/`get_dashboard_service()` **hiçbir prod endpoint/servisten
çağrılmıyordu** — yalnız kendi ~20 test dosyaları tarafından egzersiz
ediliyordu. `AnalizService`'in delege metotları (`create_fuel_periods` vb.)
zaten fuel/anomaly modüllerine pass-through'du; kendi gerçek mantığı
(`get_fleet_average`/`calculate_moving_average`/`calculate_trend`/
`calculate_long_term_stats`) da hiçbir yerden erişilmiyordu.
`container.py`'nin `analiz_service` property'si + `_analiz_service` state'i
+ `app/core/services/analiz_service.py` + `app/core/services/
dashboard_service.py` **tamamen silindi** (dalga 1'in dead-property
kaldırma emsaliyle aynı gerekçe, ama kapsam daha geniş — bu kez 2 tam
sınıf). Etkilenen ~20 test dosyası da kaldırıldı/dönüştürüldü (bkz. test
stratejisi).

## `InsightEngine` — ✅ SİLİNDİ (aşağıdaki 2026-07-18 bölümüne bkz.)

~~`InsightEngine` free function'a bölündü ama HÂLÂ ölü kod (yanlışlıkla
silinmedi, bilinçli tutuldu)~~ — bu, 2026-07-16'da yazılan ARA bir
durumdu (`generate_all_and_save()`/`generate_fleet_insights()`/vb.
hiçbir Celery task/endpoint'ten tetiklenmiyordu, ama `AnalizService`/
`DashboardService`'ten FARKLI olarak o turda SİLİNMEMİŞTİ). ❌
**DÜZELTİLDİ (2026-07-23, bağımsız dedektif denetiminde bulundu)**: bu
bölüm AYNI DOSYANIN aşağıdaki "✅ 2026-07-18 ölü-kod temizliği" bölümüyle
çelişiyordu — `generate_insights.py` (bu sınıfın free-function hali) iki
gün sonra (2026-07-18) kullanıcı kararıyla GERÇEKTEN silindi, ama bu üst
bölüm hiç güncellenmemişti. Yukarıdaki "Public API" listesindeki
`generate_all_and_save()` satırı da aynı nedenle kaldırıldı — gerçek
`public.py`'de artık yok.

## ✅ `get_driver_comparison` (driver_metrics_queries.py) — 2026-07-18'de SİLİNDİ

Aynı sınıf ölü koddu: hiçbir prod endpoint'ten çağrılmıyordu
(`get_driver_comparison_pdf` adı benziyordu ama farklı bir fonksiyon,
`get_driver_stats`'i kullanıyor). Kullanıcı kararıyla ("ölü kod yasak")
dosyasından silindi — bkz. aşağıdaki "2026-07-18 ölü-kod temizliği"
bölümü.

## 🔴 Bulgu + düzeltme: driver bulk metrikleri hiç taşınmamıştı (dalga 5 gap'i)

Bu modülün task dosyası "`get_bulk_driver_metrics`/`get_driver_comparison`
driver dalgasında (5) zaten tamamlanmış olmalı" diyordu — kontrol edildi,
**taşınmamıştı** (driver'ın kendi CLAUDE.md'si de bunu "henüz taşınmadı,
geçici bağımlılık" olarak doğru dokümante etmişti, task dosyasının
varsayımı yanlıştı). Bu dalgada düzeltildi: `v2/modules/driver/
infrastructure/driver_metrics_queries.py` (yeni dosya) — free function
(B.1, tek-tablo CRUD değil çapraz-tablo salt-okunur agregat). Çağıranlar
(`driver/application/driver_stats.py`, `driver/application/evaluation.py`
— 2026-07-18'de `domain/`'den taşındı, domain saf/I/O'suz kuralı)
güncellendi; `v2/modules/reports/infrastructure/repo_access.py`'nin
`ReportRepos`'una `session` alanı eklendi (evaluation.py'nin `_HasAnalizRepo`
duck-type fallback'i `ReportRepos` gibi session'sız bundle'larla da
çalışabilsin diye).

## 🔴 Bulgu + düzeltme: page_views tablo-sahipliği tutarsızlığı ÇÖZÜLDÜ

reports'un CLAUDE.md'si zaten bu çelişkiyi dokümante etmişti: `page_views`
tablosu kavramsal olarak reports'a atanmıştı ama onu okuyan/yazan TÜM kod
(`app/api/v1/endpoints/analytics.py`, `app/database/repositories/
page_view_repo.py`, `app/schemas/analytics.py`, `app/workers/tasks/
analytics_tasks.py`) bu modülün (analytics_executive) dosya envanterinde
duruyordu. Karar (kullanıcı, 2026-07-16, tablo-sahipliği ilkesi): hepsi
reports'a taşındı (`v2/modules/reports/{infrastructure/page_view_repo.py,
infrastructure/analytics_tasks.py, api/page_view_routes.py}` +
`schemas.py`'ye eklendi). Bu yüzden task dosyasının "10 route" sayımı
yanlıştı (`executive.py`(8)+`analytics.py`(2)) — gerçek analytics_executive
route sayısı **8**.

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalan — 1 adet)

**DÜZELTME (2026-07-18 tam-denetim turu):** bu bölüm 2 adet diyordu —
`_UnitOfWorkContext` (`application/generate_insights.py`'de yaşıyordu)
dosyasıyla birlikte ölü-kod olarak silindiği için sayım tekrar 1'e düştü.

1. **`AnalizRepository`** (`infrastructure/executive_read_models.py`) — her
   modüldeki repository sınıfı gibi (`AracRepository`, `YakitRepository`, vb.)
   `BaseRepository[Sefer]`'den türeyen bir CRUD/query sınıfı; repo katmanı
   zaten B.1'in istisnası (bkz. root CLAUDE.md "Repository pattern").

## Yayınladığı / dinlediği event'ler (events.py)

Yok — bu modül read-only.

## Şema & tablo sahipliği

Yok — bu modül hiçbir tabloya yazmaz (`bulk_create_alerts` `anomalies`
tablosuna insight-alert yazar, ama `anomalies`'in sahibi değil — anomaly
modülünün alert deposuna best-effort bir yazma yolu, dalga 8'de
dokümante edildi).

`get_bulk_cost_stats`/`get_month_over_month_trends` BİLEREK burada kalır:
çok-CTE cross-domain JOIN (yakit_alimlari+seferler), servis-çağrısına
çevirmek N+1 üretir (heavy-split ajanının ölçülü uyarısı, task dosyası §5.6).

✅ **KISMEN ÇÖZÜLDÜ (2026-07-18, prediction_ml dalga 13)**: 4 ML-parametre
metodundan `get_training_seferler` (sıfır prod çağıran, grep ile doğrulandı)
kullanıcı onayıyla SİLİNDİ. Diğer 3'ü (`save_model_params`/`get_model_params`/
`get_daily_summary_for_ml`) BİLİNÇLİ OLARAK burada kaldı — prediction_ml'in
kendi task dosyası bunları taşımayı öneriyordu ama gerçek taşıma (çapraz-modül
repo-metod relocasyonu) davranış-değişikliği riski taşıdığından bu dalganın
"mekanik taşıma" kapsamının dışında bırakıldı; `ensemble_service.py`/
`kalman_estimator.py` bu 3 metodu hâlâ `v2.modules.analytics_executive.public.
get_analiz_repo()` üzerinden çağırıyor.

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **driver (taşındı)**: `driver/application/driver_stats.py`/`evaluation.py`
  (2026-07-18'de `domain/`'den taşındı) `AnalizRepository.
  get_filo_ortalama_tuketim` kullanır (bulk metrikler artık driver'ın
  kendi `driver_metrics_queries.py`'sinde, bkz. yukarı).
- ~~fuel (tersine)~~: `fuel/domain/consumption_prediction.py` 2026-07-18
  ölü-kod temizliğinde silindi — bu bağımlılık artık yok.
- **reports (taşındı)**: `ReportRepos.analiz_repo` = bu modülün
  `AnalizRepository`'si; `advanced_reports_routes.py` maliyet
  endpoint'leri `analyze_costs.py`'nin free function'larını çağırır.
- **fleet (taşındı, geçici)**: `project_cashflow`
  `v2.modules.fleet.application.maintenance_prediction.MaintenancePredictor`'ı
  çağırır.
- **notification (taşındı)**: `compliance_tasks.py`
  `v2.modules.notification.public.send_push_broadcast`'i çağırır
  (2026-07-18: public'e çevrildi; `generate_insights.py` aynı gün ölü kod
  olarak silindi).
- **auth_rbac (taşındı)**: `api/executive_routes.py`
  `v2.modules.auth_rbac.public.require_yetki` kullanır (public.py üzerinden).
- **prediction_ml (taşındı)**: `aggregate_cross_feature`'ın D.4 kalemi
  (bakım kaynaklı fazladan yakıt kaybı hesabı) `v2.modules.prediction_ml.
  public.compute_maintenance_factor`/`fetch_health_input_batch`'i
  (fonksiyon-içi import) çağırır. ❌ **DÜZELTİLDİ (2026-07-23, bağımsız
  dedektif denetiminde bulundu)**: bu satır eskiden "anomaly" başlığı
  altında ve `app.core.ml.vehicle_health_factor`'ın "henüz taşınmamış"
  olduğunu söylüyordu — ikisi de yanlıştı: hedef modül `anomaly` değil
  `prediction_ml`, ve bağımlılık zaten taşınmış, `prediction_ml.public`
  üzerinden gidiyor (kontrat ihlali yok).

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_{bus_factor,carbon_footprint,cashflow_projector,
  compliance_scanner,cross_feature_aggregator,executive_pdf,
  fleet_efficiency_index,what_if_engine,cost_analyzer}.py` — import path
  güncellendi, davranış aynı.
- `app/tests/api/test_executive*.py` — patch hedefi
  `v2.modules.analytics_executive.api.executive_routes.<fn>`.
- `app/tests/unit/test_insight_engine_coverage.py`/
  `test_insight_serious_push.py` — class-mock'tan free-function-mock'a
  çevrildi.
- `AnalizService`/`DashboardService`'e özgü test dosyaları (`test_analiz_
  service*.py`, `test_service_optimizations.py`'nin dashboard kısmı)
  kaldırıldı (sınıflar silindi).

## ✅ 2026-07-18 ölü-kod temizliği (tam-denetim düzeltme turu)

- `application/generate_insights.py` (InsightEngine'in free-function
  hali — "bilinçli tutuldu" notuyla bekliyordu) kullanıcı kararıyla
  SİLİNDİ: `Insight`/`generate_all_and_save` public export'ları,
  `executive_read_models.bulk_create_alerts` (tek çağıranı buydu) ve
  testleri (`test_insight_engine_coverage.py`, `test_insight_serious_push.py`)
  birlikte kaldırıldı. `get_recent_unread_alerts` CANLI kalıyor
  (AIService._build_context okuyor).
- driver'daki aynı-sınıf ölü `get_driver_comparison`
  (`driver/infrastructure/driver_metrics_queries.py`) da silindi.
- `infrastructure/pdf_export.py` artık `PDFReportGenerator`'ı
  `reports.public`'ten alıyor.

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-analytics_executive` kontratı:
`application/` diğer modüllerin yalnız `public`/`events`'ini import
edebilir (2026-07-18'den beri KEPT). Diğer modüller bu modüle yalnız
`v2.modules.analytics_executive.public` üzerinden erişir (`get_analiz_repo`
dahil — container.py/repositories/__init__.py composition-root istisnası
hariç, proje-geneli desen).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`filo verimlilik endeksi`=fleet efficiency index, `nakit akışı`=cashflow,
`karbon ayak izi`=carbon footprint, `uyum/denetim`=compliance,
`ne-olur-eğer`=what-if, `otobüs faktörü`=bus factor,
`maliyet kırılımı`=cost breakdown, `içgörü`=insight (silindi),
`yönetici kokpiti`=executive cockpit.

## Modüle özel iş kuralları & gotcha'lar

- Read-model modülüdür: `AnalizRepository` cross-domain SELECT'lerin tek
  meşru evi (seferler/araclar/yakit_alimlari üzerinde raw-SQL agregasyon)
  — FAZ2'de SELECT-only grant'lerle şemalara bölünecek.
- `_UnitOfWorkContext` (application/generate_insights.py'deydi) dosyayla
  birlikte silindi — artık 1 sınıf istisnası var (`AnalizRepository`).
