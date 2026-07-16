# Modül Görevi: reports (dalga 10/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/reports/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** import-excel dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

**Kapsam notu (MEMORY §2 düzeltmesi):** `fleet_comparison.py` + `endpoints/fleet_insights.py` + `schemas/fleet_insights.py` bu modüle — ilk taramada analytics_executive'e atanmıştı, bağımsız doğrulama ajanı içerik okuyarak düzeltti: üçü de Reports-v2 (`REPORTS_V2_ENABLED` flag + `module="reports_v2"` audit etiketi, `fleet_insights.py:44,58` doğrulandı), Feature-E executive cockpit'in (`EXECUTIVE_ENABLED`) parçası değil.

---

## 1. Dosya envanteri (12 dosya, 2.519 LOC — düzeltme 2026-07-16: görev
dosyası ilk yazımda 2.404 diyordu, `git show 6251b49~1` ile gerçek toplam
2.519 olduğu doğrulandı, dedektif denetimde bulundu)
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

## 2. Route envanteri (16 route)
`reports.py`(2) + `advanced_reports.py`(11) + `reports_studio.py`(1) + `today_triage.py`(1) + `fleet_insights.py`(1) = 16.

**Düzeltme (2026-07-16, dedektif denetimde bulundu):** bu madde eskiden
"15 route (advanced_reports.py 10)" diyordu — `git show 6251b49~1:app/api/v1/
endpoints/advanced_reports.py | grep -c "^@router\."` ile doğru sayı 11
olduğu (dolayısıyla toplam 16) doğrulandı. Taşımada hiçbir route
kaybolmadı, yalnız bu görev dosyasının kendi ön-taraması yanlıştı.

## 3. Tablo sahipliği (1 tablo)
`page_views` — analytics_executive'te DEĞİL, reports'ta (kendi read-model'i page_views'i besliyor).

## 4. Bağlaşıklık karnesi
- **out:** reports→driver 5 (en yoğun), reports→analytics_executive 4, reports→fleet 3, reports→import_excel 2, reports→trip 2, reports→fuel 2
- **in:** ai_assistant→reports 1, import_excel→reports 1, analytics_executive→reports 2 (analiz_repo'nun bulk_cost_stats/month_over_month sorguları — bu KALIR analytics_executive'te, bilinçli çok-CTE kararı)
- Bu modül feature-flag gated: `REPORTS_V2_ENABLED` — flag'in gerçek kod-sınırı YAPMADIĞI (yalnız endpoint-seviyesinde) not edilir; modül sınırı flag'den bağımsız çalışır.

## 5. Taşıma adımları
1. İskelet oluştur.
2. `report_service.py` (5 repo bağımlısı: analiz, arac, sofor, sefer, yakit — MEMORY §2.1) → tek bir `application/generate_report.py` DEĞİL, B.1 gereği 7 bağımsız use-case dosyasına bölündü (`generate_fleet_summary.py`/`generate_vehicle_report.py`/`generate_driver_report.py`/`generate_monthly_trend.py`/`get_dashboard_summary.py`/`get_monthly_comparison.py`/`get_daily_consumption_trend.py`, bkz. `v2/modules/reports/CLAUDE.md`) — görev dosyası ilk yazımda tek dosya öngörüyordu, gerçek taşıma B.1'e sadık kaldı; her repo bağımlılığı ilgili modülün public.py'sine döner.
3. `triage_aggregator.py` (raw-SQL: anomalies+seferler+araclar+fuel_investigations) → `application/aggregate_today_triage.py` (görev dosyası ilk yazımda `infrastructure/triage_read_model.py` öngörüyordu; gerçek taşıma sırasında `application/`'a alındı çünkü bu bir use-case'tir, ham SQL içermesi onu FAZ2'nin "read-model" kategorisine sokmuyor — davranış aynı, yalnız dosya konumu planla farklı, bağımsız denetimde bulunup burada düzeltildi) — 4 modülden okuyor, read-model rolü FAZ2'de SELECT-only.
4. `fleet_comparison.py` + `fleet_insights.py` (endpoint+schema) → birlikte taşınır (aynı Reports-v2 özelliği, ayrılmaz).
5. `report_generator.py` → `infrastructure/pdf_export.py` (dosya üretimi).
6. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [x] 12 dosya taşındı (fleet_comparison + fleet_insights ikilisi birlikte) — bkz. `v2/modules/reports/`
- [ ] triage_aggregator'ın 4-modül raw-SQL erişimi FAZ2 read-model grant listesine eklendi (FAZ2 kapsamı, bu dalgada yapılmadı)
- [x] REPORTS_V2_ENABLED flag davranışı REGRESYONSUZ (mekanik taşıma, `settings.REPORTS_V2_ENABLED` kontrolleri aynen korundu)

**Not (2026-07-16):** page_views tablo-sahipliği görev dosyasının madde 3'ü
ile gerçek kod-sahipliği arasında tutarsızlık bulundu — detay
`v2/modules/reports/CLAUDE.md` + `TASKS/STATUS.md` DALGA 10 bölümü.
