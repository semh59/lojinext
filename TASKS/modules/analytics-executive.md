# Modül Görevi: analytics_executive (dalga 11/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/analytics_executive/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** reports dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

**Ayrım gerekçesi (MEMORY §2):** Feature-E "Strategic Cockpit" — `EXECUTIVE_ENABLED` flag + `module="executive"` audit etiketi. `reports.md`'deki Reports-v2'den (`REPORTS_V2_ENABLED`) AYRI; flag+endpoint kanıtıyla doğrulandı, tema benzerliğine değil.

---

## 1. Dosya envanteri (20 dosya, 4.883 LOC — `fleet_comparison.py`+`fleet_insights.py`(endpoint+schema) çıkarıldı → reports)
```
app/api/v1/endpoints/executive.py
app/api/v1/endpoints/analytics.py
app/core/services/analiz_service.py
app/core/services/dashboard_service.py
app/core/services/insight_engine.py
app/core/services/cross_feature_aggregator.py
app/core/services/what_if_engine.py
app/core/services/cashflow_projector.py
app/core/services/compliance_scanner.py
app/core/services/cost_analyzer.py
app/core/services/executive_pdf_generator.py
app/core/ml/bus_factor.py
app/core/ml/carbon_footprint.py
app/core/ml/fleet_efficiency_index.py
app/database/repositories/analiz_repo.py
app/database/repositories/page_view_repo.py
app/schemas/analytics.py
app/schemas/executive.py
app/workers/tasks/analytics_tasks.py
app/workers/tasks/compliance_tasks.py
```
`page_view_repo.py` burada DURUYOR ama `page_views` tablosu reports'ta (§3, reports.md) — bu bilinçli bir okuma-yazma ayrımı DEĞİL, taşıma sırasında netleştirilecek bir açık nokta: repo dosyasının konumu ile tablo sahipliğinin modülü uyuşmuyor. **Karar bu görev sırasında verilir:** page_view_repo.py reports'a taşınır (tablo-sahibi ilkesiyle tutarlı) VEYA analytics_executive'te SELECT-only read-model olarak kalır.

## 2. Route envanteri (10 route)
`executive.py`(8) + `analytics.py`(2, hem `router` hem `admin_router` — MEMORY §2.1'deki 46/47 farkının kaynağı) = 10.

## 3. Tablo sahipliği
Yok — bu modül **saf read-model**, kendi tablosuna yazmaz (page_view_repo istisnası madde 1'de netleşiyor). `analiz_repo.py` 7 modülün tablosuna raw-SQL SELECT yapıyor (56 `text()`/`.execute()` çağrısı — dosya bazında sistemin en yoğun raw-SQL kaynağı).

## 4. Bağlaşıklık karnesi
- **out:** analytics_executive→auth_rbac 2, analytics_executive→fuel 2, analytics_executive→trip 2, analytics_executive→fleet 2, analytics_executive→reports 2, analytics_executive→notification 2, analytics_executive→anomaly 1
- **in:** prediction_ml→analytics_executive 3, reports→analytics_executive 4, driver→analytics_executive 1, fuel→analytics_executive 1, anomaly→analytics_executive 1
- **B.2 kararı (çok-kaynaklı okuyucu, MEMORY §2.3):** event-projeksiyon ŞİMDİ DEĞİL; FAZ2'de bu modülün PG rolü diğer 7 modülün şemasına yalnız SELECT grant alır — yazma fiziken imkânsız hale gelir.

## 5. Taşıma adımları (`analiz_repo.py` 1.085 satır bölünmesi — heavy-split ajanının haritası)
1. İskelet oluştur.
2. `analiz_repo.py`'den ANOMALY görev dosyasındaki 15 metod (11 investigation + 4 anomaly CRUD) `anomaly` modülüne GİDER (bu görevin parçası DEĞİL — anomaly dalgasında zaten tamamlandı, burada yalnız kalan metodlar işlenir).
3. Kalan metodlar `infrastructure/executive_read_models.py`'ye toplanır: `get_filo_ortalama_tuketim`, `get_dashboard_stats`, `get_month_over_month_trends` (102L, split-into-2: sorgu+delta helper), `get_all_vehicles_consumption_stats`, `get_period_stats`, `get_vehicle_summary_stats`, `get_fleet_performance_stats`, `get_top_routes_by_vehicle`, `get_heatmap_data`, `get_daily_consumption_series`, `get_top_performing_vehicles`, `get_bulk_cost_stats` (72L).
4. ML-parametre metodları (`get_training_seferler`, `save_model_params`, `get_model_params`, `get_daily_summary_for_ml`) → **prediction_ml/infrastructure/model_params_repo.py**'YE GİDER (bu dosyanın parçası, ama hedef modül prediction_ml — o dalgada tamamlanır, burada NOT edilir).
5. Driver-metrik metodları (`get_bulk_driver_metrics`, `get_driver_comparison`) → **driver/infrastructure/driver_metrics_queries.py**'YE GİDER (driver dalgasında zaten tamamlanmış olmalı — sıra kontrolü şart).
6. `get_bulk_cost_stats` ve `get_month_over_month_trends` **BİLEREK burada kalır** — çok-CTE cross-domain JOIN, servis-çağrısına çevirmek N+1 üretir (heavy-split ajanının ölçülü uyarısı).
7. `cross_feature_aggregator.py`, `triage_aggregator.py`(reports'a gitti — burada YOK), `what_if_engine.py`, `cashflow_projector.py`, `compliance_scanner.py`, `cost_analyzer.py`, `fleet_comparison.py`(reports'a gitti) → kalanlar `application/` use-case'leri.
8. `bus_factor.py`, `carbon_footprint.py`, `fleet_efficiency_index.py` (ML metrikleri) → `domain/`.
9. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] `analiz_repo.py`'nin 1.085 satırı 4 hedefe (anomaly/prediction_ml/driver/burada-kalan) doğru dağıtıldı — hiçbir metod kaybolmadı (sayı sağlaması: 36 metod)
- [ ] page_view_repo.py konumu kararlaştırıldı
- [ ] `get_bulk_cost_stats`+`get_month_over_month_trends` BİLEREK burada, gerekçe CLAUDE.md'de
- [ ] FAZ2 read-model SELECT-only rol talebi 7 modül için not düşüldü
