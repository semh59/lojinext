# Modül: reports

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Dashboard/filo/araç/şoför rapor üretimi (JSON + PDF + Excel export), aylık
trend karşılaştırması, Reports-v2 üç özelliği (Today/Triage, Fleet İçgörü
period-karşılaştırma, Reports Studio 6 statik şablon listesi). Salt-okunur
— hiçbir varlığı yaratmaz/değiştirmez, yalnız diğer modüllerin repo'larını
okuyup rapor şekline sokar.

NE YAPMAZ: maliyet analizi (`analyze_costs.py` — analytics_executive'in
işi, dalga 11'de taşındı), Excel parse/import (import_excel'in işi — bu
modül yalnız onun `export_data`/`get_export_service`'ini tüketir).

Sayfa-görüntüleme analitiği (`page_view_repo.py`/`GET /analytics/*`)
**BU modülün işi** — dalga 11'de analytics_executive'ten buraya taşındı
(aşağıdaki "page_views tablo-sahipliği" notuna bakın, artık ÇÖZÜLDÜ).

## Public API (public.py imzaları)

```python
generate_fleet_summary(repos: ReportRepos, start_date=None, end_date=None, days=30) -> dict
generate_vehicle_report(repos: ReportRepos, arac_id: int, month=None, year=None, days=30) -> dict
generate_driver_report(repos: ReportRepos, sofor_id: int, days=30) -> dict
generate_monthly_trend(repos: ReportRepos, year=None, month=None) -> dict
get_dashboard_summary(repos: ReportRepos, days=30) -> dict
get_monthly_comparison(repos: ReportRepos, year=None, month=None) -> dict
get_daily_consumption_trend(repos: ReportRepos, days=30) -> list

ReportRepos, resolve_repos(uow: UnitOfWork | None = None) -> ReportRepos

aggregate_today_triage(uow, *, limit=50, lookback_days=7) -> TodayTriage
TodayTriage, TriageItem, TriageAction

compute_fleet_comparison(uow, *, period="week"|"month", diesel_price_tl=50.0) -> FleetComparison
FleetComparison, PeriodMetrics, PeriodType

PDFReportGenerator, get_report_generator() -> PDFReportGenerator
```

Ayrıca sayfa-görüntüleme analitiği (dalga 11'de analytics_executive'ten
taşındı, public.py'de YOK — `api/page_view_routes.py` doğrudan
`infrastructure/page_view_repo.py::PageViewRepository`'yi kullanır, diğer
route dosyalarıyla aynı desen):
`PageViewRepository`, `PageViewCreate`/`RouteCount`/`PageViewStats`
(`schemas.py`), `analytics.prune_page_views` Celery task'ı
(`infrastructure/analytics_tasks.py`).

Ayrıca yalnız `dashboard_routes.py`'nin kendi kullandığı 2 use-case (public.py'de
YOK, tek tüketicisi kendi route dosyası — bkz. "Modüle özel iş kuralları"):
`get_consumption_trend(session, months=6) -> list[dict]`,
`get_dashboard_counters(uow, today_utc) -> dict`.

**Önemli**: `ReportService` sınıfı YOK. Her use-case bağımsız bir fonksiyon
(B.1, location/notification/fleet/fuel/driver ile aynı karar — orijinal
sınıfın 7 metodu birbirinden bağımsız use-case'lerdi, `RouteSimulator`/
`LokasyonHydrator` gibi tek-cohesive-pipeline değil, bu yüzden istisna
uygulanmadı). Pre-migration `ReportService.__init__`'in session-mi-yoksa-
singleton-mi ayrımı `ReportRepos`/`resolve_repos(uow)` ile korundu: `uow`
verilirse `uow.<repo>` (aynı transaction, request-scoped session), verilmezse
her repo'nun modül-seviyeli singleton getter'ı kullanılır — driver'ın
`domain/driver_stats.py::_repos` ile aynı desen.

## Sınıf istisnaları (B.1'e rağmen sınıf olarak kalan — 1 adet)

**`PDFReportGenerator`** (`infrastructure/pdf_export.py`) — 4 bağımsız
rapor-üretim use-case'i barındırıyor (`generate_fleet_summary`,
`generate_vehicle_report`, `generate_driver_comparison`,
`generate_vehicle_comparison`, + 2 async wrapper) ama `ReportService` ile
AYNI GEREKÇEYLE bölünmedi — `RouteSimulator`/`LokasyonHydrator`/driver'ın
`DriverCoachingEngine` istisnalarındaki gerçek gerekçe: constructor
(`__init__`/`_register_fonts`) font kaydını (ReportLab `pdfmetrics`
global registry'sine TTF font yükleme, dosya I/O) BİR KEZ yapıp
`self.font_name`/`self.font_bold`/`self._styles` olarak instance state'te
tutuyor; her `generate_*` metodu bu paylaşılan state'i okuyor. Free
function'lara bölünseydi ya her çağrıda font yeniden kaydedilir (gereksiz
I/O, `pdfmetrics.registerFont` idempotent değil — ikinci kayıt hataya
düşebilir) ya da font state'i modül-global değişkenlere taşımak gerekirdi
(driver'ın `DriverPerformanceML` istisnasındaki "daha kötü tasarım"
gerekçesiyle aynı). Taşımadan ÖNCE de (eski `report_generator.py`'de)
sınıftı, dalga 10 yalnız yerini değiştirdi (mekanik) — bu istisna
gerekçesi ilk yazımda dokümante edilmemişti, bağımsız denetimde
(2026-07-16) eksik bulunup buraya eklendi.

## Yayınladığı / dinlediği event'ler (events.py)

Yok — bu modül read-only, hiçbir CRUD/lifecycle event'i yayınlamıyor
(kaynak dosyalarda `@publishes`/`event_bus.publish(...)` grep'i sıfır
sonuç verdi, taşıma bunu değiştirmedi).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **driver (taşındı)**: `generate_driver_report` → `v2.modules.driver.public.evaluate_driver`
  (2026-07-17 dedektif denetimi düzeltmesi — eskiden `domain/`'dan doğrudan
  import ediyordu, driver'ın public.py'si zaten `evaluate_driver`'ı
  yayınlıyordu, "henüz yayınlamıyor" iddiası bayattı); PDF
  route'ları `v2.modules.driver.public.get_driver_stats` çağırır.
  `ReportRepos.sofor_repo` = `v2.modules.driver.infrastructure.repository`
  (repo-bundle wiring, container.py'deki sistemik desenle aynı — bkz.
  `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md` madde 2 notu).
- **fleet (taşındı)**: `ReportRepos.arac_repo` = `v2.modules.fleet.infrastructure.vehicle_repository`.
- **fuel (taşındı)**: `ReportRepos.yakit_repo` = `v2.modules.fuel.infrastructure.repository`.
- **import_excel (taşındı)**: `advanced_reports_routes.py`'nin Excel
  export/template endpoint'leri `v2.modules.import_excel.public.export_data`/
  `get_export_service`'i çağırır.
- **auth_rbac (taşındı)**: `fleet_insights_routes.py`
  `v2.modules.auth_rbac.domain.permission_checker.require_yetki` kullanır.
- **fleet (taşındı, geçici)**: `aggregate_today_triage`
  `v2.modules.fleet.application.maintenance_prediction.MaintenancePredictor`'ı
  çağırır.
- **analytics_executive (taşındı, geçici)**: `ReportRepos.analiz_repo`
  = `v2.modules.analytics_executive.infrastructure.executive_read_models`
  (bulk fleet/vehicle/driver istatistikleri, `ReportRepos`'a artık `session`
  alanı da eklendi) ve `advanced_reports_routes.py`'nin maliyet endpoint'leri
  `v2.modules.analytics_executive.application.analyze_costs`'un free
  function'larını (`calculate_period_cost`/`get_monthly_trend`/
  `get_vehicle_cost_comparison` as `analyze_vehicle_cost_comparison`/
  `calculate_savings_potential`/`calculate_roi`) doğrudan çağırır —
  `public.py` üzerinden değil, henüz mimari borç.
- **trip (henüz taşınmadı, geçici)**: `ReportRepos.sefer_repo` yok
  (`generate_fleet_summary`'nin kendisi sefer_repo'ya ihtiyaç duymuyor) —
  `application/get_dashboard_counters.py::get_dashboard_counters(uow, ...)`
  `uow.sefer_repo.count_today(...)`'u doğrudan `app.database.repositories.
  sefer_repo`'dan kullanır (`aggregate_today_triage`/`compute_fleet_comparison`
  ile aynı desen: `ReportRepos`'a sığmayan, `uow` alan use-case).
- **Ters yön (X → reports, bu modül sağlayıcı):** driver'ın
  `SoforSeferPDFService` (`infrastructure/pdf_export.py`)
  `PDFReportGenerator`'dan miras alır; import_excel'in `ExportService`
  (`infrastructure/report_export.py`) `get_report_generator()`'ı çağırır;
  analytics_executive'in `infrastructure/pdf_export.py::generate_executive_pdf`
  font kaydı reuse için `PDFReportGenerator()` instantiate eder.

## Şema & tablo sahipliği

Bu modül hiçbir tabloya YAZMAZ (salt-okunur), `page_views` istisna —
bkz. aşağı.

### ✅ ÇÖZÜLDÜ (2026-07-16, dalga 11) — page_views tablo-sahipliği tutarsızlığı

`TASKS/modules/reports.md` madde 3 "page_views — analytics_executive'te
DEĞİL, reports'ta" diyordu ama bu modülün (dalga 10) 12 dosyalık
envanterinde `page_view_repo.py` YOKTU — gerçek tüketicileri
(`app/api/v1/endpoints/analytics.py::GET /analytics/*`, `app/workers/
tasks/analytics_tasks.py` prune task'ı) analytics_executive'in dosya
sınırında yaşıyordu. Kullanıcı kararıyla (tablo-sahipliği ilkesi) dalga
11'de hepsi buraya taşındı: `infrastructure/page_view_repo.py`,
`infrastructure/analytics_tasks.py` (prune task), `api/page_view_routes.py`
(eski `app/api/v1/endpoints/analytics.py`), `schemas.py`'ye eklenen
`PageViewCreate`/`RouteCount`/`PageViewStats`. `app/api/v1/api.py`
router include'ları güncellendi (`page_view_router`/`page_view_admin_router`).

## İzin verilen / yasak import'lar

FAZ1'in import-linter gate'i henüz aktif değil (rapor modu). Hedef kontrat:
diğer modüller yalnız `v2.modules.reports.public`/`.events`'i import eder;
`application/`/`domain/`/`infrastructure/`'a doğrudan erişim yasak.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`rapor`=report, `filo`=fleet, `tuketim`=consumption, `donem`=period,
`karsilastirma`=comparison, `oncelik`=priority, `bakim`=maintenance,
`sorusturma`=investigation.

## Modüle özel iş kuralları & gotcha'lar

- **`ReportRepos.analiz_repo`/`.sefer_repo` cross-module, geçici** — bkz.
  yukarıdaki "senkron konuştuğu modüller".
- **`generate_driver_report`, `_AnalizRepoProxy` gerektirmiyor artık**:
  eski `report_service.py`'de `evaluate_driver`'ın `uow`-fallback'ine
  minimal bir proxy sınıfı (`_AnalizRepoProxy`) geçiriliyordu (yalnız
  `.analiz_repo` okuyordu); `ReportRepos` zaten aynı attribute'u taşıdığı
  için proxy'siz doğrudan geçirilebiliyor — mekanik sadeleşme, davranış
  değişikliği yok.
- **`get_daily_consumption_trend` prod'da hiçbir yerden çağrılmıyor**
  (yalnız `test_business_flows.py`/`test_report_service_coverage.py`
  tarafından egzersiz ediliyor) — taşımadan önce de böyleydi, dead-ish
  kod olarak korundu (test edilen davranış silinmedi).
- ✅ **DÜZELTİLDİ (dalga 11, 2026-07-16)** — `app/core/services/
  dashboard_service.py` (`DashboardService`, `_ReportsFacade` adaptörü
  dahil) tamamen silindi: dedektif denetiminde hiçbir prod endpoint/
  servisten çağrılmadığı doğrulandı (dead code, kullanıcı kararı) —
  `context_builder.py` bu sınıfı hiç kullanmıyordu (grep sıfır sonuç),
  önceki bulgu yanlış varsayımdı.
- **PDF font kaydı** (`infrastructure/pdf_export.py::_register_fonts`):
  repo kökü artık `dirname()` 4 kez uygulanarak hesaplanıyor (eskiden
  `app/core/services/`den 2 kez yeterliydi) — `app/assets/fonts/DocFont*.ttf`
  yolu bu ortamda mevcut değil (dizin hiç yok), pratikte her zaman sistem
  fontuna/Helvetica'ya düşer; taşımadan önce de aynı fallback zinciriydi.
- ✅ **DÜZELTİLDİ (2026-07-16, bağımsız denetimde bulundu)** —
  `api/dashboard_routes.py`'nin 2 handler'ı `application/`'ı atlayıp
  doğrudan repo/UoW'a erişiyordu (`bug-route-layer-bypasses-application.md`
  sınıfı — dalga 2/3/5/6/9'da bulunan aynı desenin bu dalgadaki tekrarı,
  ama **dalga 10'un getirdiği bir regresyon değil**: `git show
  6251b49~1:app/api/v1/endpoints/reports.py` ile doğrulandı, taşımadan
  ÖNCE de bu şekildeydi — mekanik taşıma sırasında fark edilmemişti).
  `get_dashboard_stats`'in `uow.arac_repo.count_active()`/
  `uow.sofor_repo.count_active()`/`uow.sefer_repo.count_today()`/
  `uow.analiz_repo.get_month_over_month_trends()` çağrıları yeni
  `application/get_dashboard_counters.py::get_dashboard_counters(uow, ...)`'a,
  `get_consumption_trend`'in ham SQLAlchemy `select(YakitAlimi...)` sorgusu
  yeni `application/get_consumption_trend.py::get_consumption_trend(session, ...)`'a
  taşındı. Mekanik, davranış değişikliği yok (aynı sorgular, aynı sıra).

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_report_service_coverage.py` →
  `application/` use-case fonksiyon testlerine bölünecek (patch hedefi
  TÜKETEN modül — `v2.modules.reports.api.*` veya
  `v2.modules.reports.application.*` — kaynak modül değil).
- `app/tests/unit/test_services/test_report_generator_coverage.py` →
  `infrastructure/pdf_export.py` testi, import path güncellendi.
- `app/tests/unit/test_triage_aggregator.py`, `test_fleet_comparison.py`,
  `test_reports_studio.py` → import path güncellendi, davranış aynı.
- `app/tests/api/test_advanced_reports*.py` → patch hedefi
  `v2.modules.reports.api.advanced_reports_routes.<fn>`.
- `app/tests/unit/test_container_comprehensive.py`/`test_container.py` —
  `container.report_service` assertion'ları kaldırıldı (property artık yok).
