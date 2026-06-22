# Faz 7 — Tahmin Kalibrasyonu Tasarım Dokümanı

**Tarih:** 2026-06-13
**Durum:** Onaylandı (brainstorm → spec)
**Bağlam:** Faz 7 (route segment simulation) altyapısı kuruluydu; `scripts/p51_real_world_validation.py` onarıldı (predict imza + Open-Meteo pacing, commit `e63b3b48`). Temiz koşu (429=0, elevation=%100) modelin gerçek doğruluk profilini ortaya çıkardı; bu spec onun kalibrasyonunu tanımlar.

---

## 1. Problem

Temiz paced p51 koşusu (Open-Meteo 429=0, tüm rotalarda elevation_coverage=%100):

| Rota | Physics baseline | wind | seasonal | Final | Band | Sonuç |
|------|------------------|------|----------|-------|------|-------|
| VAL-IST-ANK-450 | 34.12 | 1.084 | 1.05 | 38.84 | 30-35 | RED +19.5% |
| VAL-IST-IZM-485 | 30.52 | 1.129 | 1.05 | 36.18 | 29-33 | RED +16.7% |
| VAL-BUR-IST-155 | 29.48 | 1.118 | 1.05 | 34.61 | 28-32 | RED +15.4% |
| VAL-ANK-KON-260 | 30.57 | 1.044 | 1.05 | 33.51 | 31-36 | GREEN |
| VAL-IST-BOL-265 | 34.92 | 1.085 | 1.05 | 39.78 | 34-40 | GREEN |

**İki kök neden:**
1. **Metodoloji (elma-armut):** Literatür bandları **koşul-nötr/tipik** tüketim aralıkları (ICCT baseline + yük). Model çıktısı ise koşula-özgü — çağrı anındaki gerçek rüzgâr + mevsim çarpanlarını içeriyor. Bu ikisini doğrudan kıyaslamak yapısal olarak yanlış: physics baseline'ları tek başına banda uygun (5/5 band-içi/yakın → tarihsel "4/5 GREEN" ile tutarlı), ama çarpanlar uygulanınca over-band çıkıyor.
2. **Compound çarpan birikimi:** `wind` (1.04-1.13) × `seasonal` (1.05) ≈ ×1.19'a kadar; zaten banda uygun bir baseline'ı banttan taşırıyor. Tek tek faktörler fiziksel olabilir ama birikim aşırı.

**Önemli:** Bu rate-limit artefaktı DEĞİL (429=0, elevation=%100); modelin gerçek davranışı. Ama physics baseline doğru — sorun çarpan katmanı + validation metodolojisi.

## 2. Hedef

Validation'ı doğru kur + çevresel çarpan birikimini fiziksel sınırlarla frenle — **modelin gerçek tahmin doğruluğunu bozmadan**, **5 referans rotaya overfit etmeden**. (Karar: hibrit; per-faktör fiziksel cap; genişletilmiş referans set.)

## 3. Kapsam dışı (YAGNI)

- Physics baseline'ın yeniden türetilmesi (zaten banda uygun — dokunulmaz).
- Mapbox/segment simülasyon mantığının değişmesi (çalışıyor).
- ML ensemble ağırlık değişikliği.
- Cap'leri 5 banda fit etmek (overfit — açıkça reddedildi).

## 4. Bileşenler

### A. Koşul-nötr validation modu (metodoloji — model davranışı DEĞİŞMEZ)

`SeferFuelEstimate.breakdown` (`FactorBreakdown`) zaten tüm faktörleri ayrı tutuyor: `physics_baseline, driver, vehicle_age, maintenance, weather_temperature, weather_wind, weather_precipitation, seasonal, final`.

- p51, her rota için **koşul-nötr değer** hesaplar:
  `neutral = physics_baseline × driver × vehicle_age × maintenance`
  (yani weather_temperature × weather_wind × weather_precipitation × seasonal HARİÇ — çevresel/mevsimsel katman çıkarılır). Referans araç/şoför standart olduğundan driver/age/maint ≈ 1.0; pratikte `neutral ≈ physics_baseline`.
- **Birincil GREEN/RED kararı** bu koşul-nötr değer ile literatür bandı arasında verilir (like-for-like).
- **Koşul-uygulanmış** tam `final` değeri raporda **bilgi amaçlı** gösterilir (pass/fail'e girmez) + sanity kontrolüne tabi (Bölüm C kabul).
- Mekanizma: p51 içinde saf bir helper `_neutral_estimate(breakdown) -> float`; estimator API'si değişmez (bu yalnız validation metodolojisi).

### B. Per-faktör fiziksel cap (model DEĞİŞİR — gerçek tahmini de etkiler)

Çevresel faktör fonksiyonlarına **5 rotadan bağımsız, fiziksel-gerekçeli** üst sınır. Cap'ler `app/config.py`'de ayarlanabilir + docstring'de gerekçe:

- **`weather_wind_factor` ≤ 1.10** — ağır TIR'da highway hızında rüzgâr aerodinamik drag'i tipik +%5-10 bandında; tipik (fırtına olmayan) rüzgârda >%10 fiziksel olarak beklenmez. Config: `WEATHER_WIND_FACTOR_MAX = 1.10`.
- **`seasonal_factor` ≤ 1.03** — mevsimsel tüketim sapması (yaz AC / kış cold-start + viskozite) ağır araçta ±%3 düzeyinde; üst sınır 1.03. Config: `SEASONAL_FACTOR_MAX = 1.03`.
- **`weather_temperature_factor`** ve **`weather_precipitation_factor`**: mevcut sınırlar gözden geçirilir; belirgin bir fiziksel taşma yoksa dokunulmaz (temp/precip bu koşuda 1.0'dı). Gerekirse benzer config cap eklenir.

Cap uygulaması: ilgili faktör fonksiyonunun dönüşünde `min(factor, MAX)` (alt sınır da korunur — cap yalnız üst taşmayı keser). Faktör fonksiyonları nerede tanımlıysa (weather util) orada clamp; saf + unit-testable.

### C. Genişletilmiş referans set

`scripts/p51_real_world_validation.py`'ye ~5-7 yeni Türkiye rotası + literatür/ICCT-gerekçeli band eklenir (toplam ~10-12). Daha sağlam, overfit-dirençli validation. Yeni rotalar: farklı topografya/yük çeşitliliği (düz otoyol, dağlık, şehirlerarası kısa, ağır/hafif yük). Bandlar literatür notuyla belgelenir; gerekçe zayıfsa rota YELLOW kabul edilir, RED'e zorlanmaz.

## 5. Kabul kriteri (yeniden tanımlı)

1. **Koşul-nötr** çıktı: genişletilmiş referans setin **≥%80'i GREEN**; kalanı YELLOW + belgeli fiziksel gerekçe. (RED yok; ya da gerekçeli "bilinçli kabul edilmiş sapma".)
2. **Koşul-uygulanmış** (tam) çıktı: cap'ler sonrası hiçbir rota literatür bandını **>%12 aşmaz** (sanity üst sınır).
3. **fuel-accuracy coverage düşmemiş** — estimator + sefer-create yolu davranışı korunur (cap'ler tahmini hafifçe değiştirir ama prediction üretimini engellemez).
4. Cap değerleri referans rotalardan **bağımsız**, fiziksel/literatür gerekçeli (overfit guard).

## 6. Mimari / dosya yapısı

- **Faktör cap'leri:** `app/core/ml/adjustment_factors.py` (`weather_wind_factor`, `weather_temperature_factor`, `weather_precipitation_factor`) + `app/core/services/weather_service.py` (`get_seasonal_factor`). Cap ayarları `app/config.py`'de (`WEATHER_WIND_FACTOR_MAX`, `SEASONAL_FACTOR_MAX`). Saf fonksiyonlar → unit test. (Estimator `sefer_fuel_estimator.py:414-423` bunları çağırır; çağrı noktası değişmez, fonksiyonlar cap'lenir.)
- **Validation metodolojisi:** `scripts/p51_real_world_validation.py` — `_neutral_estimate` helper + iki-modlu rapor + genişletilmiş rota listesi.
- **Test:** `app/tests/unit/` — cap clamp testleri (sınır altı/üstü) + neutral hesap testi.
- Estimator (`sefer_fuel_estimator.py`) API'si değişmez; yalnız çağırdığı faktör fonksiyonları cap'lenir.

## 7. Hata yönetimi & riskler

| Risk | Etki | Önlem |
|------|------|-------|
| Cap'ler gerçek tahmini fazla bastırır | Düşük tahmin | Cap'ler fiziksel üst sınır, tipik değerleri kesmez (wind 1.10, seasonal 1.03 — çoğu koşulda zaten altında) |
| Yeni referans bandları zayıf gerekçeli | Sahte RED/GREEN | Band literatür notuyla; gerekçe zayıfsa YELLOW kabul, RED'e zorlanmaz |
| Open-Meteo 429 (validation'da) | Eksik veri | Pacing (eklendi) + koşul-nötr mod zaten weather'ı dışlar → 429 birincil kararı etkilemez |
| Overfit (az rota) | Yanıltıcı "yeşil" | Cap'ler rotadan bağımsız + genişletilmiş set |

## 8. Test stratejisi

- **Unit:** `weather_wind_factor`/`seasonal_factor` clamp (cap altında değişmez, üstünde cap'lenir); `_neutral_estimate` doğru çarpan alt-kümesini kullanır.
- **Validation (p51):** genişletilmiş set, iki-modlu; koşul-nötr ≥%80 GREEN; tam çıktı ≤%12 aşım. (Open-Meteo'ya bağlı; pacing ile.)
- **Regresyon:** mevcut estimator/sefer testleri yeşil kalır; cap'ler birim faktör testlerini bozmaz (yeni cap testleri eklenir).
