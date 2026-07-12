# Modül Görevi: fuel (dalga 4/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/fuel/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** fleet dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

---

## 1. Dosya envanteri (13 dosya, 2.756 LOC)
```
app/api/v1/endpoints/fuel.py
app/api/v1/endpoints/admin_fuel_accuracy.py
app/core/services/yakit_service.py
app/core/services/yakit_tahmin_service.py
app/core/services/fuel_coverage.py
app/core/services/period_calculation_service.py
app/database/repositories/yakit_repo.py
app/schemas/yakit.py
app/core/ml/fuel_predictor.py
app/core/integrations/fuel/__init__.py
app/core/integrations/fuel/base.py
app/core/integrations/fuel/opet.py
app/workers/tasks/fuel_coverage_check.py
```

## 2. Route envanteri (12 route)
`fuel.py`(11) + `admin_fuel_accuracy.py`(1) = 12.

## 3. Tablo sahipliği (3 tablo)
`yakit_alimlari`, `yakit_periyotlari`, `yakit_formul`. `yakit_alimlari.durum` CHECK constraint'i ['Bekliyor','Onaylandı','Reddedildi'] — Türkçe+aksanlı, FAZ3 dil geçişinin en riskli enum'u (bkz. faz3-dil-gecisi görev dosyası).

## 4. Bağlaşıklık karnesi
- **out:** fuel→admin_platform 3, fuel→import_excel 3, fuel→analytics_executive 1, fuel→fleet 1, fuel→driver 1, fuel→trip 1, fuel→notification 1
- **in:** import_excel→fuel 2, admin_platform→fuel 2, analytics_executive→fuel 2, ai_assistant→fuel 1
- **En sıkı çift (MEMORY §2.3):** trip→fuel senkron, periyot bağlama aynı transaction'da; `period_calculation_service.py`'nin trip'e olan bağımlılığı bu modülde KALIR (fuel tarafında yazılı), trip'in fuel'e bağımlılığı trip görev dosyasında ele alınır. FAZ2 sonunda bu çiftin senkron kalması yeniden değerlendirilecek.
- `fuel_investigations` tablosu bu modülde DEĞİL — anomaly'ye ait (1:1 çocuk); `core/ai/fuel_theft_classifier.py` anomaly modülünde, fuel'in ona 1 outbound bağımlılığı asenkron/senkron kararı anomaly görev dosyasında.

## 5. Taşıma adımları
1. İskelet + `yakit_repo.py` → `infrastructure/repository.py`.
2. `yakit_service.py` → CRUD use-case'leri; `@publishes` (YAKIT_ADDED/UPDATED/DELETED, satır 110/180/203) payload doğrulaması (fleet'teki gibi).
3. `period_calculation_service.py` → `application/calculate_period.py` — trip'e bağımlılığı `public.py` üzerinden (henüz trip taşınmadıysa geçici eski yol).
4. `yakit_tahmin_service.py` (fuel tahmini, prediction_ml'den FARKLI — modül-içi basit tahmin) → `domain/`.
5. `core/integrations/fuel/*` (Opet entegrasyonu) → `infrastructure/integrations/opet_client.py`.
6. `fuel_coverage_check.py` (beat task, `monitoring.fuel_coverage_check`, günlük) → `infrastructure/tasks.py`.
7. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] 13 dosya taşındı
- [ ] YAKIT_* event payload'ları DTO doğrulaması geçti
- [ ] `yakit_alimlari.durum` Türkçe enum değerleri FAZ3 sözlüğüne (CLAUDE.md madde 7) not düşüldü — bu FAZda DEĞİŞTİRİLMEDİ
- [ ] trip↔fuel senkron çiftinin public.py sınırı netleşti
