# Modül Görevi: trip (dalga 14/17 — EN KARMAŞIK SPLİT)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/trip/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** prediction-ml dalgası tamamlandı (trip'in prediction_ml'e olan 6 bağımlılığı public.py üzerinden hazır olmalı). **Çıkış kriteri:** import-linter kontratı yeşil; `out=20/in=18` — sistemin en yoğun iki-yönlü modülü.

---

## 1. Dosya envanteri (10 dosya, 5.336 LOC)
```
app/api/v1/endpoints/trips.py
app/core/services/sefer_service.py
app/core/services/sefer_read_service.py
app/core/services/sefer_write_service.py
app/core/services/sefer_analiz_service.py
app/core/services/sefer_fuel_estimator.py
app/database/repositories/sefer_repo.py
app/schemas/sefer.py
app/core/utils/sefer_status.py
app/core/utils/trip_status.py
```
+ driver dalgasında (5) NOT edilen `sefer_repo.py`'nin 6 driver-özel sorgusu → bu görevde `modules/driver/infrastructure/driver_trip_queries.py`'ye GİDER (trip'ten çıkar, driver'a girer — driver.md madde 4'te önceden işaretlendi).

## 2. Route envanteri (22 route) — 8 alt-router'a bölünüyor, 3'ü BAŞKA MODÜLE gidiyor
Heavy-split ajanının `trips.py` haritası (22 üye):
| Alt-router | Route'lar | Hedef modül |
|---|---|---|
| `trip_read_routes.py` | `read_seferler`, `read_bugunun_seferleri`, `beklemede_seferler`, `read_sefer`, `get_sefer_timeline` | **trip** |
| `trip_write_routes.py` | `create_sefer`, `create_return_trip`, `update_sefer`, `delete_sefer` | **trip** |
| `trip_bulk_routes.py` | `bulk_update_trip_status`, `bulk_cancel_trips`, `bulk_delete_trips` | **trip** |
| `trip_approval_routes.py` | `sefer_onayla`, `sefer_reddet` | **trip** |
| `trip_export_routes.py` | `export_seferler`, `get_excel_template` | **import_excel** (import_excel dalgasında zaten tamamlanmış olmalı) |
| `trip_import_routes.py` | `upload_sefer_excel`, `get_task_status` | **import_excel** |
| `trip_analytics_routes.py` | `get_trip_stats`, `get_fuel_performance_analytics`, `analyze_trip_costs` | **analytics_executive** (o dalgada tamamlanmış olmalı) |
| `plan_routes.py` (route_simulation) | `plan_wizard` | **route_simulation** (o dalgada tamamlanmış olmalı) |

**Sıra kontrolü şart:** import_excel(9), analytics_executive(11), route_simulation(7) dalgaları bu dalgadan (14) ÖNCE tamamlanmış olduğu için, o 3 alt-router'ın hedef dosyaları zaten var — trip dalgası yalnız kaynak route'u oraya TAŞIR, yeni modül oluşturmaz.

## 3. Tablo sahipliği (3 tablo)
`seferler`, `seferler_log`, `sefer_belgeler`. `seferler` 9 outbound FK ile 6 modüle bağlı (MEMORY §2.2) — sistemin en yoğun tekil tablo bağlaşıklığı.

## 4. Bağlaşıklık karnesi
- **out:** trip→prediction_ml 6, trip→route_simulation 4, trip→import_excel 3, trip→ai_assistant 2, trip→fleet 1, trip→auth_rbac 1, trip→driver 1, trip→admin_platform 1, trip→notification 1
- **in:** prediction_ml→trip 4, route_simulation→trip 2, driver→trip 2, ai_assistant→trip 2, reports→trip 2, analytics_executive→trip 2, fuel→trip 1, import_excel→trip 2, admin_platform→trip 1

## 5. Taşıma adımları (heavy-split ajanının `sefer_write_service.py` 1.590 satır haritası — 28 üye, 13 hedef dosya)
1. İskelet oluştur.
2. Sırayla (bağımlılık az→çok):
   - Saf yardımcılar (I/O'suz) → `domain/trip_validation.py`: `_safe_durum`(16L), `_validate_sefer_create`(22L), `_sync_weight_fields`(24L)
   - `domain/sla.py`: `_check_sla_delay`(35L)
   - `domain/return_trip.py`: `_handle_round_trip_on_update`(70L), `_create_return_trip`(96L), `create_return_trip`(59L)
   - Tahmin-zenginleştirme kümesi → `application/trip_prediction_enrichment.py` (prediction_ml'e TEK köprü): `_build_route_details_snapshot`(21L), `_build_prediction_quality_flags`(17L), `_build_prediction_route_analysis`(19L), `_extract_prediction_values`(51L), `_check_reprediction_needed`(14L), `_repredikt_for_update`(121L), `_resolve_route`(17L), `_predict_via_estimator`(86L), `_predict_outbound`(99L)
   - CRUD use-case'leri (her biri ayrı dosya): `application/add_trip.py`(`add_sefer` 140L), `application/update_trip.py`(`update_sefer`+`_update_sefer_uow` 159L), `application/delete_trip.py`(`delete_sefer`+`_delete_sefer_uow` 21L)
   - `application/bulk_trip_ops.py`: `bulk_update_status`(51L), `bulk_cancel`(46L), `bulk_delete`(34L)
   - `application/bulk_add_trips.py`: `bulk_add_sefer`(248L, **CC=58** — import_excel'in tükettiği use-case)
3. **KRİTİK invariant — bölünmez:** `bulk_add_sefer`'ın `net_kg` CHECK enforcement'ı (satır 1479-1487) `arac_bos_map` prefetch'ine (satır 1305-1311) bağlı; `dolu=max(dolu,bos)` → `net=dolu-bos` sırası korunmalı. Bu küme extraction'da BİRLİKTE taşınır (`arac_bos_map`, `route_map`, `active_arac`/`sofor` setleri, `seen sefer_no` dedup).
4. `sefer_repo.py` (1.076 satır) — driver'a giden 6 sorgu ÇIKAR (madde 1); kalan `get_all`, `get_by_id`, `count_all`, `add`, `get_by_sefer_no`, vb. → `infrastructure/repository.py`. `refresh_stats_mv` → `shared_kernel/infrastructure/mv_refresh.py` (MV tüm sistem geneli, trip'e özel değil). `get_fuel_performance_analytics`(143L) → analytics_executive'e (madde 2'deki `trip_analytics_routes.py` ile birlikte).
5. `sefer_repo.py`'deki byte-aynı `joinedload(arac,sofor,dorse,guzergah)` zinciri (3 kopya: 83-86/287-290/844-847) → TEK `_with_relations()` yardımcısına indirgenir (models.py bölünmesinden ÖNCEKİ ara adım — D.1/1 riskinin mitigasyonu).
6. `trips.py` router → madde 2'deki 8 alt-router'a bölünür; RBAC `Depends()` her route ile birlikte taşınır.
7. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] 28 üye 13 hedef dosyaya dağıtıldı (sayı sağlaması: kaynak LOC toplamı ≈ hedef LOC toplamı, kod kısalığı kuralı madde 4)
- [ ] `bulk_add_sefer`'ın net_kg/arac_bos_map invariantı test edildi (0-mock entegrasyon, bulk import senaryosu)
- [ ] 22 route 8 alt-router'a bölündü, 3'ü doğru hedef modüle taşındı (import_excel/analytics_executive/route_simulation ile senkron)
- [ ] joinedload zinciri `_with_relations()`'a indirgendi, 3 kopya → 1
- [ ] driver'a giden 6 sorgu driver_trip_queries.py'de (driver dalgasıyla çapraz-doğrulandı)
