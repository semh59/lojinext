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

**B.1 sınıf istisnaları (2 adet):**

- **`SafeColumnMapper`** (`infrastructure/column_mapper.py`) —
  `RouteSimulator`/`LokasyonHydrator`/`DriverPerformanceML` ile aynı
  gerekçe: tek cohesive fuzzy-match algoritması (exact-match + skorlu
  substring/`SequenceMatcher` iki-geçişli strateji), constructor state'i
  yok.
- **`ExportService`** (`infrastructure/report_export.py`) — disk'e
  PDF/Excel yazan, `EXPORT_DIR` çözümü + `cleanup_old_exports` yaşam
  döngüsü olan stateful orkestratör (Excel export'un bytes-döndüren
  `infrastructure/exporters.py::export_data`/`generate_template`'inden
  FARKLI bir API yüzeyi — biri dosya yoluna yazar, diğeri bytes döner,
  aynı isimli metotlar (`generate_template`) karıştırılmamalı).

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
- **fleet (taşındı)**: `process_vehicle_import` → `bulk_add_vehicles`;
  `export_trailers.py::import_trailers`/`get_trailer_template`/
  `export_all_trailers` bu modülün `public.py`'sini (`parse_dorse_excel`/
  `generate_template`/`export_data`) çağırır (YÖN TERSİ: fleet tüketici).
- **driver (taşındı)**: `process_driver_import` → `bulk_add_sofor`.
- **location (taşındı)**: `import_routes` → `create_location` (N+1 önleme
  için `existing_index` tek seferde prefetch edilip geçirilir).

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
