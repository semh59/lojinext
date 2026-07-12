# Modül Görevi: import_excel (dalga 9/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/import_excel/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** anomaly dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

---

## 1. Dosya envanteri (11 dosya, 3.498 LOC)
```
app/api/v1/endpoints/admin_imports.py
app/core/services/import_service.py
app/core/services/excel_column_map.py
app/core/services/excel_parser.py
app/core/services/excel_exporter.py
app/core/services/excel_service.py
app/core/services/export_service.py
app/database/repositories/import_repo.py
app/services/api/sefer_import_service.py
app/services/api/__init__.py
app/workers/tasks/ocr_tasks.py
```

## 2. Route envanteri (4 route)
`admin_imports.py`(4). (`trips.py`'deki `upload_sefer_excel`/`get_task_status`/`export_seferler`/`get_excel_template` rotaları — heavy-split ajanı bunları `modules/import_excel/api/trip_import_routes.py` ve `trip_export_routes.py`'ye önerdi; bunlar trip dalgasında (14) taşınır, burada değil — trip görev dosyasında çapraz-referanslı.)

## 3. Tablo sahipliği (1 tablo) — ✅ FAZ0 KARARI UYGULANDI
`iceri_aktarim_gecmisi` bu modülde. Kanıt (MEMORY/PROGRESS.md §4.3): repository (`import_repo.py::ImportHistoryRepository`) ve tek okuyucu (`admin_imports.py`) zaten bu modülün dosya envanterinde; admin_platform'da hiç kullanım yok. FAZ2 şema tasarımında bu tablo `import_excel` şemasına gider (14 şema).

## 4. Bağlaşıklık karnesi
- **out (yüksek — orkestratör doğası):** import_excel→trip 2, import_excel→fuel 2, import_excel→location 2, import_excel→auth_rbac 1, import_excel→fleet 1, import_excel→route_simulation 1, import_excel→reports 1
- **in:** fuel→import_excel 3, location→import_excel 3, trip→import_excel 3, fleet→import_excel 3, reports→import_excel 2, driver→import_excel 2, admin_platform→import_excel 1
- **B.2 kararı:** import_excel→{trip,fleet,driver,fuel,location} SENKRON — orkestratör satır-bazlı doğrulama geri bildirimi anlık olmalı, YALNIZ public.py üzerinden (bugünkü 8 cross-module DI kablosu — container.py'de ölçülen `import_service` bağımlılıkları — bu tek yüzeye iner).

## 5. Taşıma adımları (heavy-split ajanının `import_service.py` 1.073 satır haritası — MEMORY kaynağı)
1. İskelet oluştur.
2. Domain-bazlı importer'ları önce ayır (her biri self-contained, `(count, errors)` döner):
   - `process_sefer_import` → `application/sefer_importer.py`
   - `process_yakit_import` → `application/yakit_importer.py`
   - `process_vehicle_import` → `application/vehicle_importer.py`
   - `process_driver_import` → `application/driver_importer.py`
   - `import_routes` → `application/route_importer.py`
3. Paylaşılan çözümleyiciler → `domain/entity_resolvers.py` (`_resolve_arac_id`, `_resolve_sofor_id`, `_resolve_route_id`, `_resolve_dorse_id`).
4. Alan doğrulayıcılar → `domain/field_validators.py` (`_validate_plaka`, `_validate_name`, `_validate_location`, `_normalize_text`, `_validate_numeric`, `_parse_date_flexible`).
5. **`execute_import` (249 satır, orkestratör) EN SON taşınır ve TEK UoW BLOĞU BÖLÜNMEZ:** `async with UnitOfWork() as uow` bloğu `create_import_job` + `session.flush()` (job id, commit YOK) + raw INSERT'ler + `inserted_ids` takibini TEK atomik birim olarak tutar — `rollback_import`'un kontratı budur, parçalanamaz.
6. `_validate_import_rows` (148 satır, 5 domain'e dallanıyor) split-into-5 önerisi VAR ama madde 5'teki prefetch (vehicles/drivers/trailers/routes master listesi `execute_import` satır 328-334'te yükleniyor) her split'e AYRI geçirilmeli, yoksa N+1 regresyonu olur — bu görev bunu doğrulayan bir performans testiyle kapanır.
7. `excel_column_map.py`, `excel_parser.py`, `excel_exporter.py`, `excel_service.py`, `export_service.py` → `infrastructure/` (dosya I/O + parsing).
8. `ocr_tasks.py` → `infrastructure/tasks.py` (OCR mikroservisine HTTP çağrısı yapan Celery task — `ocr_service/` kendisi taşınmaz, yalnız çağıran taraf).
9. Shim'ler + CLAUDE.md — NOT NULL tuzağı (`arac.marka` toplanmıyor, satır 361-368) CLAUDE.md'nin gotcha bölümüne taşınır.

## 6. Kabul kriterleri
- [ ] 11 dosya taşındı, `execute_import`'un UoW bloğu tek parça
- [ ] `_validate_import_rows` split'i N+1 regresyon testiyle kanıtlı (prefetch listesi paylaşıldı)
- [ ] iceri_aktarim_gecmisi kararı uygulandı
- [ ] Import senkron çağrı 5 modülün hepsinde public.py üzerinden
