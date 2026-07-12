# Modül Görevi: route_simulation (dalga 7/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/route_simulation/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** auth-rbac dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

---

## 1. Dosya envanteri (21 dosya, 4.787 LOC — en çok dosyalı 2. modül)
```
app/api/v1/endpoints/routes.py
app/api/v1/endpoints/weather.py
app/api/v1/endpoints/admin_calibration.py
app/core/services/route_simulator.py
app/core/services/route_calibration_service.py
app/core/services/route_validator.py
app/core/services/openroute_service.py
app/core/services/weather_service.py
app/core/services/segment_resampler.py
app/core/ml/segment_simulator.py
app/core/ml/route_similarity.py
app/domain/services/route_analyzer.py
app/database/repositories/route_repo.py
app/services/route_service.py
app/infrastructure/routing/mapbox_client.py
app/infrastructure/routing/openroute_client.py
app/infrastructure/routing/__init__.py
app/infrastructure/elevation/__init__.py
app/infrastructure/elevation/open_meteo_client.py
app/core/utils/polyline.py
app/scripts/backfill_route_pairs.py
```
`app/domain/services/route_analyzer.py` — mevcut kod tabanındaki TEK `app/domain/` sakini (minimal/terk edilmiş DDD denemesi, MEMORY kaynağı ajanının tespiti); bu modüle taşınınca `app/domain/` dizini tamamen boşalır ve silinir.

## 2. Route envanteri (8 route)
`routes.py`(3) + `weather.py`(3) + `admin_calibration.py`(2) = 8.

## 3. Tablo sahipliği (4 tablo)
`route_paths`, `route_simulations`, `route_segments`, `guzergah_kalibrasyonlari`. Rate-limit uyarısı: `open_meteo_client.py` — free tier dar minutely limit, 429 retry pattern zorunlu (proje hafızası `open_meteo_rate_limit`) — bu modülün taşınmasında davranış DEĞİŞTİRİLMEZ, yalnız dosya konumu.

## 4. Bağlaşıklık karnesi
- **out:** route_simulation→prediction_ml 4, route_simulation→admin_platform 4, route_simulation→trip 2, route_simulation→auth_rbac 1, route_simulation→location 1
- **in:** location→route_simulation 7 (en yoğun — pilot modülün ilk bağımlılığı), trip→route_simulation 4, prediction_ml→route_simulation 3, ai_assistant→route_simulation 1, import_excel→route_simulation 1
- `route_analyzer.py::analyze_segments` CC=56 (radon ölçümü, MEMORY §1) — bu modülün en kompleks fonksiyonu; FAZ1 dosya-kalite gate'inde baseline'a alınır (yeni ihlal sayılmaz), ama bölünmesi bu görevin bir parçası (madde 5.4).

## 5. Taşıma adımları
1. İskelet + `route_repo.py` → `infrastructure/repository.py`.
2. `mapbox_client.py`, `openroute_client.py`, `open_meteo_client.py` → `infrastructure/clients/` (dış API istemcileri, davranış değişmez — 429 retry pattern korunur).
3. `route_simulator.py`, `route_validator.py`, `segment_resampler.py` → `application/simulate_route.py` vb. use-case dosyaları.
4. `route_analyzer.py::analyze_segments` (CC=56): baseline'a alınır, split GEREKMİYOR bu FAZ'da (ölçülü — kod kısalığı kuralı "5 satırlık işi 50 yapma" der, ama "58 satırlık işi zorla 6 parçaya böl" demez; CC azaltımı ayrı, gerekçesiz bir iş olur — bu görev kapsamı dışında, yalnız baseline'a donuyor).
5. `route_calibration_service.py` → `application/calibrate_route.py`.
6. `route_similarity.py`, `segment_simulator.py` (ML) → `domain/` (prediction_ml'e olan 4 bağımlılık `public.py` üzerinden).
7. `backfill_route_pairs.py` script'i → `infrastructure/scripts/` (dış yazar değil, app içi script — `scripts/` kökünden modül-içine taşınabilir, opsiyonel).
8. `app/domain/` dizini bu adımdan sonra boşalır, silinir (git ile takip edilir, "unfamiliar directory" değil — bu planın kendi kararı).
9. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] 21 dosya taşındı, `app/domain/` boşaldı ve silindi
- [ ] `analyze_segments` CC=56 baseline'a alındı (yeni ihlal DEĞİL)
- [ ] Open-Meteo 429 retry davranışı REGRESYONSUZ (mevcut testler geçiyor)
- [ ] location↔route_simulation 7 kenarlık bağımlılık public.py üzerinden çözüldü
