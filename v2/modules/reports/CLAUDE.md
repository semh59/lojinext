# Modül: reports

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Dashboard/filo/araç/şoför rapor üretimi (JSON + PDF + Excel export), aylık
trend karşılaştırması, Reports-v2 üç özelliği (Today/Triage, Fleet İçgörü
period-karşılaştırma, Reports Studio 6 statik şablon listesi). Salt-okunur
— hiçbir varlığı yaratmaz/değiştirmez, yalnız diğer modüllerin repo'larını
okuyup rapor şekline sokar.

NE YAPMAZ: maliyet analizi (`cost_analyzer.py` — analytics_executive'in
işi, henüz taşınmadı, bu modülün geçici bağımlılığı), sayfa-görüntüleme
analitiği (`page_view_repo.py`/`GET /analytics/*` — ayrıntı için aşağıdaki
"page_views tablo-sahipliği tutarsızlığı" notuna bakın), Excel
parse/import (import_excel'in işi — bu modül yalnız onun `export_data`/
`get_export_service`'ini tüketir).

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
TrendReport                                            # domain/report_metrics.py dataclass

aggregate_today_triage(uow, *, limit=50, lookback_days=7) -> TodayTriage
TodayTriage, TriageItem, TriageAction

compute_fleet_comparison(uow, *, period="week"|"month", diesel_price_tl=50.0) -> FleetComparison
FleetComparison, PeriodMetrics, PeriodType

PDFReportGenerator, get_report_generator() -> PDFReportGenerator
```

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

- **driver (taşındı)**: `generate_driver_report` → `v2.modules.driver.domain.evaluation.evaluate_driver`
  (public.py yerine `domain/`'dan doğrudan import — driver henüz kendi
  `evaluate_driver`'ını public.py'de yayınlamıyor, mimari borç); PDF
  route'ları `v2.modules.driver.domain.driver_stats.get_driver_stats`
  çağırır. `ReportRepos.sofor_repo` = `v2.modules.driver.infrastructure.repository`.
- **fleet (taşındı)**: `ReportRepos.arac_repo` = `v2.modules.fleet.infrastructure.vehicle_repository`.
- **fuel (taşındı)**: `ReportRepos.yakit_repo` = `v2.modules.fuel.infrastructure.repository`.
- **import_excel (taşındı)**: `advanced_reports_routes.py`'nin Excel
  export/template endpoint'leri `v2.modules.import_excel.public.export_data`/
  `get_export_service`'i çağırır.
- **auth_rbac (taşındı)**: `fleet_insights_routes.py`
  `v2.modules.auth_rbac.domain.permission_checker.require_yetki` kullanır.
- **fleet (taşındı, geçici)**: `aggregate_today_triage`
  `v2.modules.fleet.domain.maintenance_prediction.MaintenancePredictor`'ı
  çağırır.
- **analytics_executive (henüz taşınmadı, geçici)**: `ReportRepos.analiz_repo`
  = `app.database.repositories.analiz_repo` (bulk fleet/vehicle/driver
  istatistikleri) ve `advanced_reports_routes.py`'nin maliyet endpoint'leri
  `app.core.services.cost_analyzer.get_cost_analyzer()` çağırır — ikisi de
  analytics_executive dalgasına (11) taşınınca `public.py` üzerinden
  geçilecek.
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
  `executive_pdf_generator.py` (analytics_executive henüz taşınmadı) font
  kaydı reuse için `PDFReportGenerator()` instantiate eder.

## Şema & tablo sahipliği

Bu modül hiçbir tabloya YAZMAZ (salt-okunur). `page_views` tablosunun
kavramsal sahibi olarak dokümante edilmişti (FAZ2 şema-per-module planı
için) — ama **bu tutarsız çıktı, aşağıya bakın.**

### 🔴 Bulgu: page_views tablo-sahipliği notu ile gerçek kod-sahipliği uyuşmuyor

`TASKS/modules/reports.md` madde 3 "page_views — analytics_executive'te
DEĞİL, reports'ta" diyordu, ama bu modülün 12 dosyalık envanterinde
`page_view_repo.py` YOKTU ve gerçek tüketicileri (`app/api/v1/endpoints/
analytics.py::GET /analytics/*`, `app/workers/tasks/analytics_tasks.py`
prune task'ı) analytics_executive'in (dalga 11, henüz taşınmadı) alanında
yaşıyor — reports'un bu dalgada dokunmadığı dosyalar. Yani: `page_views`
tablosu kavramsal olarak reports'a atanmış ama onu okuyan/yazan TÜM kod
bugün analytics_executive'in dosya sınırında. Bu dalgada `page_view_repo.py`
taşınmadı (görev dosyasının 12 dosyalık envanterinin dışında, mekanik
taşıma kararına sadık kalmak için) — analytics_executive (dalga 11)
taşınırken bu çelişki çözülmeli: ya `page_views` gerçekten reports'a
taşınır (o zaman `page_view_repo.py` + `analytics.py`'nin page-view
endpoint'leri + prune task'ı buraya gelir), ya da FAZ2 planı
analytics_executive'in sahipliğini onaylayacak şekilde düzeltilir.

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
- **`dashboard_service.py`/`context_builder.py` (app/core/, bu dalganın
  dosya envanterinin dışı) `_ReportsFacade` adaptörü** kullanıyor —
  `self.report_service.get_dashboard_summary()` çağrı şeklini koruyan
  küçük bir köprü sınıfı (testlerin `AsyncMock` override'ı bunu
  bekliyor). Reports'un kendi `ReportService` sınıfı yok, ama bu
  TÜKETİCİ modüllerin (dashboard/AI context) eski instance-method
  çağrı şeklini bu dalgada değiştirmek kapsam dışı bırakıldı.
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
