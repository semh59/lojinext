# Modül: import_excel

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Excel/CSV import orkestrasyonu (arac/surucu/sefer/yakit/guzergah toplu
yükleme), admin generic bulk import + rollback (job takibi + inserted_ids),
Excel export + şablon üretimi, OCR belge işleme Celery task'ı.
`iceri_aktarim_gecmisi` tablosunun tek sahibi.

NE YAPMAZ: hiçbir domain entity'sinin (arac/surucu/sefer/yakit/lokasyon)
gerçek CRUD iş kuralını uygulamaz — yalnız Excel'i parse edip ilgili
modülün `bulk_add_*`/`create_*` fonksiyonunu çağırır. `SeferService`
(trip, henüz taşınmadı) hâlâ gerçek sefer create iş kuralının sahibi.

## Public API (public.py imzaları)

```python
# Preview / admin generic bulk import + rollback (job/rollback ZORUNLU)
parse_and_preview(file: UploadFile, aktarim_tipi: str) -> dict
execute_import(file, aktarim_tipi, user_id, mapping: dict) -> dict   # TEK UoW bloğu, bkz. aşağı
rollback_import(job_id: int, user_id: int) -> bool

# Domain-özel import (Pydantic bulk_add_* yolu, job/rollback YOK — ARCH-002)
process_sefer_import(content: bytes) -> tuple[int, list]     # prod'da çağrılmıyor, test-covered legacy
process_yakit_import(content: bytes) -> tuple[int, list]
process_vehicle_import(content: bytes) -> tuple[int, list]
process_driver_import(content: bytes) -> tuple[int, list]
import_routes(content: bytes) -> tuple[int, list]             # güzergah/lokasyon

# Trip'in canlı sefer-upload yolu (B.2: trip→import_excel senkron, bu üzerinden)
import_sefer_excel_upload(content: bytes, current_user_id: int) -> tuple[int, list[dict]]

# Export / template (diğer modüllerin kendi domain export'u için çağırdığı yol)
export_data(data: list[dict], type: str = "generic") -> bytes
generate_template(type: str) -> bytes
parse_dorse_excel(content: bytes) -> list[dict]

# Disk'e PDF/Excel export + cleanup (sınıf istisnası, aşağıya bkz.)
ExportService, get_export_service() -> ExportService
  .export_to_excel(data: dict, filename, title="Rapor") -> str | None
  .export_fleet_summary_pdf(start_date, end_date, data, filename) -> str | None
  .export_vehicle_report_pdf(arac_id, month, year, data, filename) -> str | None
  .generate_template(entity_type: str) -> str | None   # ExcelService.generate_template'ten FARKLI: dosya yolu döner, bytes değil
  .cleanup_old_exports(max_age_days=7) -> int

# Repository (uow.import_repo)
ImportHistoryRepository  # infrastructure/repository.py

# OCR Celery task (infrastructure/tasks.py; internal.py'nin belge-upload akışı .delay() ile çağırır)
process_belge_ocr(belge_id: int) -> dict   # task adı: "ocr.process_belge"
```

**B.1 sınıf istisnaları — DÜRÜST NOT (2026-07-15 dedektif denetimi
bulgusu):** aşağıdaki 2 sınıf ilk yazımda `RouteSimulator`/`LokasyonHydrator`
ile "aynı gerekçe" diye tanımlanmıştı — bağımsız denetim bu iddianın
YANLIŞ olduğunu gösterdi (o emsallerin gerçek istisna sebebi
constructor-injected client bağımlılığı/mutable eğitilmiş-model state'i;
aşağıdaki 2 sınıfta bu YOK). İkisi de dalga 9'da MEKANİK taşındı (davranış
değişikliği yapılmadı) — B.1'in "gerçek gerekçesiz sınıf" kısıtına göre
teknik borç olarak burada dürüstçe işaretleniyor, free-function'a
çevrilmeleri ayrı bir refactor kapsamı (bu dalganın taşıma-only sınırını
aşar):

- **`SafeColumnMapper`** (`infrastructure/column_mapper.py`) — hiç
  `__init__` yok, hiç instantiate edilmiyor (her çağrı
  `SafeColumnMapper.map_columns(...)` classmethod'u), `COLS` class-level
  sabit dict. Gerçekte constructor-state'i olmadığı için `map_columns`
  trivially bir free function'a, `COLS` bir modül sabitine çevrilebilirdi
  — bu B.1'in tam olarak önlemeye çalıştığı "gereksiz sınıf" örüntüsü.
  Taşımadan ÖNCE de (eski `excel_column_map.py`'de) sınıftı, dalga 9
  yalnız yerini değiştirdi.
- **`ExportService`** (`infrastructure/report_export.py`) — `EXPORT_DIR`
  class-level bir sabit (instance-özel mutable state değil), constructor
  yok, ve sınıf gerçekte 5 BİRBİRİNDEN BAĞIMSIZ use-case barındırıyor
  (`export_to_excel`, `export_fleet_summary_pdf`, `export_vehicle_report_pdf`,
  `generate_template`, `cleanup_old_exports`) — `RouteSimulator`'ın "tek
  cohesive pipeline" gerekçesindeki gibi TEK bir iş akışı değil. Excel
  export'un bytes-döndüren `infrastructure/exporters.py::export_data`/
  `generate_template`'inden FARKLI bir API yüzeyi (biri dosya yoluna
  yazar, diğeri bytes döner, aynı isimli metotlar karıştırılmamalı).
  Taşımadan ÖNCE de (eski `export_service.py`'de) sınıftı, dalga 9 yalnız
  yerini değiştirdi.

## İMPORT MİMARİSİ (ARCH-002, execute_import.py docstring'inde de var)

İki AYRI, KASITLI import akışı var, merge EDİLMEMELİ:
- `execute_import` — admin generic bulk import (arac/surucu/sefer/yakit),
  import-job kaydı + `inserted_ids` ile satır-bazlı `rollback_import`.
  Raw `INSERT ... RETURNING id` rollback için ZORUNLU.
- `process_*_import` (vehicle/driver/yakit) + `import_sefer_excel_upload` —
  domain endpoint'lerinin kullandığı Pydantic `bulk_add_*` yolu (job/rollback yok).
  `process_sefer_import` prod'da çağrılmıyor (test-covered legacy yol);
  canlı sefer importu `import_sefer_excel_upload` (trip'in
  `POST /trips/upload`'ı) üzerinden yapılır.

DURUM (status) sözleşmesi: tüm yollar canonical `SEFER_STATUS_PLANLANDI`
sabitini kullanır (literal kopyalama yasak — BUG-002 bu drift'ten çıktı).

## KRİTİK İNVARYANT — execute_import'un TEK UoW bloğu bölünmez

`application/execute_import.py`'deki `async with UnitOfWork() as uow` bloğu
`create_import_job` + `session.flush()` (job id, commit YOK) + raw
INSERT'ler (her biri kendi SAVEPOINT'inde) + `inserted_ids` takibini TEK
atomik birim olarak tutar — `rollback_import`'un kontratı budur, parçalanamaz.

## `_validate_import_rows` → `domain/row_validators.py` (B.1 split)

Eskiden tek metod 4 `aktarim_tipi`'ne (arac/surucu/sefer/yakit) dallanıyordu
(görev dosyası "5'e dallanıyor" diyordu — gerçek kod 4 dal, task dosyası
bu noktada yanlıştı). `validate_arac_row`/`validate_surucu_row`/
`validate_sefer_row`/`validate_yakit_row`'a bölündü; prefetch edilen master
listeler (`vehicles`/`drivers`/`trailers`/`routes`) **execute_import
tarafından TEK seferde çekilip parametre olarak paylaşılıyor** — her split
kendi SELECT'ini atsaydı N+1 regresyonu olurdu.

## Senkron konuştuğu modüller (yön: import_excel → X, B.2 kararı: hepsi public.py üzerinden)

- **trip (henüz taşınmadı)**: `process_sefer_import`/`import_sefer_excel_upload`
  `get_container().sefer_service.bulk_add_sefer(...)` çağırır (container
  üzerinden geçici erişim, trip taşınınca doğrudan `v2.modules.trip.public`
  olacak). `execute_import`'un sefer dalı ayrıca `EventType.SEFER_UPDATED`
  publish eder (trip'in event'i, bu modülün sahibi olmadığı — events.py'de not).
- **fuel (taşındı)**: `process_yakit_import` → `bulk_add_yakit` +
  `recalculate_vehicle_periods`.
- **fleet (taşındı)**: `process_vehicle_import` → `v2.modules.fleet.public.
  bulk_add_vehicles` + `AracCreate` (2026-07-18 düzeltmesi — eskiden
  `application`/`schemas`'tan doğrudandı);
  `export_trailers.py::import_trailers`/`get_trailer_template`/
  `export_all_trailers` bu modülün `public.py`'sini (`parse_dorse_excel`/
  `generate_template`/`export_data`) çağırır (YÖN TERSİ: fleet tüketici).
- **driver (taşındı)**: `process_driver_import` → `v2.modules.driver.public.
  bulk_add_sofor` (2026-07-17 dedektif denetimi düzeltmesi — eskiden
  `application.add_sofor`'dan doğrudan import ediyordu).
- **location (taşındı)**: `import_routes` → `v2.modules.location.public.
  create_location`/`route_key`/`LokasyonCreate` (2026-07-17 düzeltmesi —
  eskiden `domain/`/`application/`/`schemas`'tan doğrudan import ediyordu,
  bu dosyanın kendi CLAUDE.md iddiası "hepsi public.py üzerinden" o zaman
  yanlıştı, şimdi doğru; N+1 önleme için `existing_index` tek seferde
  prefetch edilip geçirilir).

**Ters yön (X → import_excel, bu modül sağlayıcı):** fuel/fleet/driver/
location/reports (`advanced_reports.py`) kendi Excel export/template/
import ihtiyaçları için bu modülün `public.py`'sini çağırır (`export_data`/
`generate_template`/`get_export_service`/`process_*_import`).

## Bilinen açık notlar

- **`arac` importunda `marka` (NOT NULL) toplanmıyor** (`execute_import.py`)
  — uydurma marka yazmak yanlış olur; mapping genişletme veya `marka`'yı
  nullable yapma ürün kararı bekliyor (taşımadan önce de böyleydi).
- **`SeferImportService._resolve_master_id` dead code olarak DÜŞÜRÜLDÜ**
  (B.1 free-function geçişinde) — `process_excel_import`/
  `import_sefer_excel_upload` hiçbir zaman çağırmıyordu (`_build_lookup`
  dict'leri kullanıyor), yalnız kendi unit testi tarafından egzersiz
  ediliyordu. Test dosyası buna göre güncellendi.
- **YAKIT_ADDED/SOFOR_ADDED/ARAC_ADDED/LOKASYON_ADDED event'leri bu modülün
  SAHİBİ OLMADIĞI** event'ler — ilgili domain modülleri zaten kendi
  `@publishes` decorator'larını taşıyor (çoğu ölü kod, her modülün kendi
  CLAUDE.md'sinde dokümante).
- **`ocr_tasks.py`'nin taşınması bu modülün "Excel import" sorumluluğuyla
  gevşek ilişkili** — orijinal dosya envanterinde vardı (`app/workers/
  tasks/ocr_tasks.py`), OCR belge-işleme akışı Excel'le ilgisiz ama görev
  dosyasının 11 dosyalık listesinde açıkça yer alıyordu, taşındı.
- ✅ **DÜZELTİLDİ (2026-07-15, dedektif denetiminde bulundu)** —
  `api/import_routes.py`'nin `GET /history` endpoint'i `application/`'ı
  atlayıp doğrudan `UnitOfWork`+`ImportHistoryRepository` çağırıyordu
  (`bug-route-layer-bypasses-application.md` sınıfının bu dalgadaki
  taşıma sırasında üretilen YENİ bir tekrarı — eski `admin_imports.py`'den
  mekanik kopyalanmış, hiç application katmanına taşınmamıştı). Yeni
  `application/get_import_history.py` eklendi, route artık yalnız onu
  çağırıyor.
- **`infrastructure/parsers.py`/`infrastructure/exporters.py` — 6+ bağımsız
  entity-tipi (sefer/yakit/route/vehicle/driver/dorse) parse/export
  mantığı tek dosyada** (dedektif denetiminde işaretlendi). Eski
  `excel_parser.py`/`excel_exporter.py`'den DEĞİŞTİRİLMEDEN taşındı — bu
  yapı taşımadan önce de böyleydi, dalga 9'un ürettiği bir regresyon değil.
  Application katmanındaki importer dosyalarının (`driver_importer.py` vb.)
  tersine burada entity-başına ayrı dosyaya bölünmedi; ileride ele
  alınabilecek bir B.1 temizlik kalemi olarak işaretli, bu dalgada
  kapsam dışı bırakıldı (mekanik taşıma kararına sadık kalmak için).
- **`execute_import`'un `surucu` dalı (`ad_soyad`/`telefon` PII şifreleme +
  trigram) driver modülünün repository'sini bypass edip ham SQL
  INSERT/DELETE yazıyor** — `v2/modules/driver/CLAUDE.md`'nin kendi notu
  bunun "import-excel dalga 9'da ele alınacak (driver repository'sinin
  bulk-insert path'ini kullanacak şekilde refactor edilebilir)" olduğunu
  söylüyor ama bu, `TASKS/modules/import-excel.md`'nin kabul kriterlerinde
  YOKTU — davranış değişikliği + driver'ın bulk-insert path'ine yeni bir
  yetenek eklenmesi gerektirdiği için bu dalgada kapsam dışı bırakıldı
  (taşımadan önce de aynı ham-SQL deseni vardı, regresyon değil). Ayrı bir
  bug-fix görevi olarak açılabilir.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_import_service*.py` → domain importer
  + execute_import/rollback_import testlerine bölündü.
- `app/tests/unit/test_excel_column_mapper.py`, `test_excel_parser*.py`,
  `test_excel_exporter_coverage.py`, `test_export_service*.py` — infra
  testleri, patch hedefi tüketen modül değil (bunlar saf fonksiyon/sınıf
  testleri, DI yok).
- `app/tests/unit/test_sefer_import_service.py` → `test_sefer_upload_importer.py`
  (dosya adı + import path güncellendi, `_resolve_master_id` testi kaldırıldı).
- `app/tests/unit/test_workers/test_ocr_tasks_coverage.py` → import path güncellendi.
- Kök `tests/` klasörü (dalga 1/3/4/8 gotcha'sı) — `test_import_pipeline.py`,
  `test_excel_export*.py`, `test_export.py` tarandı ve dönüştürüldü.

## Yayınladığı / dinlediği event'ler (events.py)

Kendi event'i yok (`events.py` docstring'i): `execute_import`'un sefer
dalı trip'in sahibi olduğu `EventType.SEFER_UPDATED`'ı publish eder
(orada dokümante); OCR Celery task'ı event-bus kullanmaz (Celery
`.delay()` senkron kuyruğu).

## İzin verilen / yasak import'lar (import-linter özeti)

`.importlinter`'ın `public-surface-only-import_excel` kontratı:
`application/` diğer modüllerin yalnız `public`/`events`'ini import
edebilir (2026-07-18'den beri KEPT — `vehicle_importer.py`'nin
`fleet.schemas`+`fleet.application.bulk_add_vehicles` ve
`yakit_importer.py`'nin `fuel.schemas` doğrudan importları aynı gün
`fleet.public`/`fuel.public`'e çevrildi; `infrastructure/
report_export.py`'nin `reports.infrastructure.pdf_export` importu da
`reports.public.get_report_generator` oldu). Trip'e erişim container
üzerinden (geçici, trip taşınınca `trip.public`).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`içeri aktarma`=import, `dışa aktarma`=export, `önizleme`=preview,
`geri alma`=rollback, `sütun eşleme`=column mapping, `şablon`=template,
`satır doğrulama`=row validation, `belge`=document (OCR).
