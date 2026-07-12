# Modül Görevi: reports (dalga 10/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/reports/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** import-excel dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

**Kapsam notu (MEMORY §2 düzeltmesi):** `fleet_comparison.py` + `endpoints/fleet_insights.py` + `schemas/fleet_insights.py` bu modüle — ilk taramada analytics_executive'e atanmıştı, bağımsız doğrulama ajanı içerik okuyarak düzeltti: üçü de Reports-v2 (`REPORTS_V2_ENABLED` flag + `module="reports_v2"` audit etiketi, `fleet_insights.py:44,58` doğrulandı), Feature-E executive cockpit'in (`EXECUTIVE_ENABLED`) parçası değil.

---

## 1. Dosya envanteri (12 dosya, 2.404 LOC)
```
app/api/v1/endpoints/reports.py
app/api/v1/endpoints/advanced_reports.py
app/api/v1/endpoints/reports_studio.py
app/api/v1/endpoints/today_triage.py
app/api/v1/endpoints/fleet_insights.py
app/core/services/report_service.py
app/core/services/report_generator.py
app/core/services/triage_aggregator.py
app/core/services/fleet_comparison.py
app/schemas/report_template.py
app/schemas/today.py
app/schemas/fleet_insights.py
```

## 2. Route envanteri (15 route)
`reports.py`(2) + `advanced_reports.py`(10) + `reports_studio.py`(1) + `today_triage.py`(1) + `fleet_insights.py`(1) = 15.

## 3. Tablo sahipliği (1 tablo)
`page_views` — analytics_executive'te DEĞİL, reports'ta (kendi read-model'i page_views'i besliyor).

## 4. Bağlaşıklık karnesi
- **out:** reports→driver 5 (en yoğun), reports→analytics_executive 4, reports→fleet 3, reports→import_excel 2, reports→trip 2, reports→fuel 2
- **in:** ai_assistant→reports 1, import_excel→reports 1, analytics_executive→reports 2 (analiz_repo'nun bulk_cost_stats/month_over_month sorguları — bu KALIR analytics_executive'te, bilinçli çok-CTE kararı)
- Bu modül feature-flag gated: `REPORTS_V2_ENABLED` — flag'in gerçek kod-sınırı YAPMADIĞI (yalnız endpoint-seviyesinde) not edilir; modül sınırı flag'den bağımsız çalışır.

## 5. Taşıma adımları
1. İskelet oluştur.
2. `report_service.py` (5 repo bağımlısı: analiz, arac, sofor, sefer, yakit — MEMORY §2.1) → `application/generate_report.py`; her repo bağımlılığı ilgili modülün public.py'sine döner.
3. `triage_aggregator.py` (raw-SQL: anomalies+seferler+araclar+fuel_investigations) → `infrastructure/triage_read_model.py` — 4 modülden okuyor, read-model rolü FAZ2'de SELECT-only.
4. `fleet_comparison.py` + `fleet_insights.py` (endpoint+schema) → birlikte taşınır (aynı Reports-v2 özelliği, ayrılmaz).
5. `report_generator.py` → `infrastructure/pdf_export.py` (dosya üretimi).
6. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] 12 dosya taşındı (fleet_comparison + fleet_insights ikilisi birlikte)
- [ ] triage_aggregator'ın 4-modül raw-SQL erişimi FAZ2 read-model grant listesine eklendi
- [ ] REPORTS_V2_ENABLED flag davranışı REGRESYONSUZ
