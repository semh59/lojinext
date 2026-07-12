# Modül Görevi: anomaly (dalga 8/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/anomaly/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** route-simulation dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

**Kapsam notu:** fraud AYRI modül DEĞİL — fuel-theft/investigation/attribution zaten tek iş akışı, anomaly ile birleşik (MEMORY §2 seed-sapma gerekçesi).

---

## 1. Dosya envanteri (12 dosya, 2.210 LOC)
```
app/api/v1/endpoints/anomalies.py
app/api/v1/endpoints/investigations.py
app/api/v1/endpoints/admin_attribution.py
app/core/services/anomaly_detection_service.py
app/core/services/anomaly_detector.py
app/core/services/attribution_service.py
app/schemas/attribution.py
app/schemas/investigation.py
app/core/ml/anomaly_clustering.py
app/core/ai/fuel_theft_classifier.py
app/workers/tasks/anomaly_cluster_tasks.py
app/workers/tasks/theft_tasks.py
```

## 2. Route envanteri (14 route)
`anomalies.py`(5) + `investigations.py`(7) + `admin_attribution.py`(2) = 14.

## 3. Tablo sahipliği (2 tablo) + analiz_repo'dan gelen ek küme
`anomalies`, `fuel_investigations` (fuel'in DEĞİL, anomalinin 1:1 çocuğu — `lock_investigation_for_update` FOR-UPDATE yazma yolu burada). **Kritik taşıma kısıtı (heavy-split ajanının tespiti):** `app/database/repositories/analiz_repo.py`'deki (1.085 satır, analytics_executive modülünde duruyor) şu 11 metod BÜTÜN halinde bu modüle taşınmalı, parçalanmamalı — pessimistic-lock scope'u bölünürse concurrency garantisi kırılır:
```
get_investigation_detail, get_investigation_patterns, list_investigations,
get_anomaly_alarm_context, get_investigation_by_anomaly_id,
create_investigation_row, lock_investigation_for_update,
get_investigation_by_id, update_investigation_fields,
close_investigation, update_investigation_classification
```
Ayrıca `bulk_create_anomalies`, `get_anomalies_filtered`, `get_anomaly_by_id`, `update_anomaly` (Anomaly CRUD) da analiz_repo'dan buraya taşınır → `modules/anomaly/infrastructure/anomaly_repo.py` + `investigation_repo.py` (2 dosya, tek dosyaya sıkıştırılmaz — CRUD ile FOR-UPDATE akışı ayrı sorumluluk).

## 4. Bağlaşıklık karnesi
- **out:** anomaly→admin_platform 2, anomaly→auth_rbac 1, anomaly→ai_assistant 1, anomaly→analytics_executive 1, anomaly→prediction_ml 1
- **in:** driver→anomaly 1, fuel→anomaly (dolaylı, fuel_theft_classifier üzerinden — MEMORY §2.3'te ölçülmedi, bu görev sırasında netleşir), analytics_executive→anomaly (analiz_repo taşınınca kesilecek, madde 3)
- Celery: `theft_tasks.py` (`theft.daily_pattern_scan`, beat 03:00) — 5 modül tablosuna raw-SQL erişiyor (fuel_investigations+anomalies+seferler+soforler+araclar); taşıma sonrası bu erişimler FAZ2'de trip/driver/fleet şemalarına SELECT-only grant gerektirecek. `anomaly_cluster_tasks.py` (`anomaly.cluster_scan`, beat 05:00).

## 5. Taşıma adımları
1. İskelet oluştur.
2. `analiz_repo.py`'den madde 3'teki 15 metodu (11 investigation + 4 anomaly CRUD) `infrastructure/anomaly_repo.py`+`infrastructure/investigation_repo.py`'ye taşı — **`lock_investigation_for_update` ile onu çağıran `update_investigation_fields`/`close_investigation` AYNI dosyada, aynı sırada kalmalı** (heavy-split ajanının uyarısı: FOR-UPDATE scope'u transaction sınırıdır).
3. `anomaly_detection_service.py`, `anomaly_detector.py` → `application/detect_anomaly.py`.
4. `anomaly_clustering.py` (ML) → `domain/clustering.py`.
5. `fuel_theft_classifier.py` (AI) → `application/classify_theft.py`; ai_assistant'a olan bağımlılığı public.py üzerinden.
6. `attribution_service.py` → `application/attribute_loss.py`.
7. Shim'ler + CLAUDE.md — bu modülün CLAUDE.md'sinde FOR-UPDATE invariant'ı özellikle dokümante edilir.

## 6. Kabul kriterleri
- [ ] 12 dosya + analiz_repo'dan 15 metod taşındı (analytics_executive görev dosyasıyla senkron — o dosyada bu 15 metod "çıkan" olarak işaretli)
- [ ] `lock_investigation_for_update` + `update_investigation_fields` + `close_investigation` AYNI dosyada (bölünmedi)
- [ ] theft_tasks'ın 5-modül raw-SQL erişimi FAZ2 rol matrisine not düşüldü
- [ ] Concurrency testi: FOR-UPDATE senaryosu 0-mock entegrasyon testinde hâlâ geçiyor (taşıma öncesi/sonrası davranış birebir)
