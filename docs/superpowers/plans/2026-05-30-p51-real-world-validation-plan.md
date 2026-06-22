# P5.1 — Real-World Validation: Bilinen Rotalarla Sefer Testi

**Tarih**: 2026-05-30
**Hedef**: Pilot 4 hafta beklemeden, literatürle doğrulanmış 5 Türkiye rotasında SeferFuelEstimator (Phase 4) tahminlerinin makul bantta olduğunu **aynı gün** doğrula.
**Sahip**: Production deploy sonrası ilk validasyon (Phase 5.0 sonrası)

---

## 1. Neden bu plan

Phase 4-5 boyunca yapılan testler MagicMock üzerinden geçti. **Mapbox + Open-Meteo + physics + adjustment factors** kombinasyonu gerçek koşulda hiç çalışmadı.

4 haftalık pilot beklemenin riskleri:
1. **Operasyonel bağımlılık**: Operatörlerin tablete sefer girmesi + tamamlanması + gerçek tüketim girmesi
2. **Sessiz hata penceresi**: SecretStr bug'ı gibi production-only fail'ler 4 hafta boyunca tahmin "0" döndürebilir, fark edilmez
3. **Erken kalibrasyon sinyali kaybı**: Bandın çok dışındaysa Phase 4 parametre düzeltmesi pilot başlamadan yapılabilirdi

**Bu çalışmanın amacı kalibrasyon değil — sağlık kontrolü**:
- Kalibrasyon: gerçek tüketim vs tahmin → katsayı ayarı (pilot lazım, 30+ sefer)
- Sağlık kontrolü: tahmin literatür bandında mı? → evet/hayır kararı

---

## 2. Literatür baseline

### 2.1 Avrupa HDV referans verileri

| Kaynak | Konu | Değer |
|--------|------|-------|
| [ICCT 2018 Fact Sheet](https://theicct.org/wp-content/uploads/2021/06/HDV-EU-fuel-consumption_ICCT-Fact-Sheet_08042018_vF.pdf) | 2015 40-ton 4×2 tractor-trailer long-haul cycle | **33.1 L/100km** baseline |
| [Webfleet 2024](https://www.webfleet.com/en_gb/webfleet/blog/how-much-diesel-does-a-truck-use-per-mile/) | Modern Volvo FH / Mercedes Actros otoyol | **28-32 L/100km** |
| [ECOLOW](https://www.ecolow.fr/en/truck-consumption/) | Genel TIR otoyol bandı | **30-40 L/100km** |
| [Lamiro24 / Transpoco](https://transpocodirect.com/blogs/news/what-is-the-diesel-consumption-per-kilometer-for-trucks-2024-guide) | Yük etkisi | **+1-2 L/100km per ton** |

### 2.2 Türkiye rotaları için mesafe referansları

| Rota | Mesafe (km) | Kaynak |
|------|-------------|--------|
| İstanbul → Ankara (TEM/O-4) | 447 | [Kmhesaplama](https://kmhesaplama.com/istanbul-ankara-arasi-kac-km/) |
| İstanbul → İzmir (O-5+O-31) | 480-490 | Yandex Maps / Google Maps |
| Bursa → İstanbul (Köprü/O-5) | 155 | Yandex Maps |
| Ankara → Konya (O-21) | 260 | Yandex Maps |
| İstanbul → Bolu (TEM/O-4) | 265 | Yandex Maps |

### 2.3 Eğim etkisi (literatür kombine)
- Düz otoyol: baseline
- 500-1000m ascent: **+%5-10**
- >1000m ascent (Bolu, Toros): **+%10-20**
- Şehir içi stop-and-go: **+%30**

---

## 3. Test seti (5 rota)

| # | Rota | Mesafe | Net yük | Profil | Beklenen tahmin L/100km |
|---|------|--------|---------|--------|--------------------------|
| 1 | İST → ANK | 450 km | 20 t | TEM otoyol, hafif eğim | **30-35** |
| 2 | İST → İZM | 485 km | 18 t | O-5+O-31 düz | **29-33** |
| 3 | BUR → İST | 155 km | 12 t | Köprü+otoyol | **28-32** |
| 4 | ANK → KON | 260 km | 25 t | Düz step otoyol | **31-36** |
| 5 | İST → BOL | 265 km | 22 t | Bolu dağı ~800m ascent | **34-40** |

### 3.1 Koordinatlar (lojistik bölgeler)

| Şehir | Lat | Lon |
|-------|-----|-----|
| İstanbul (Hadımköy) | 41.110 | 28.732 |
| Ankara (Esenboğa OSB) | 39.985 | 32.789 |
| İzmir (Aliağa OSB) | 38.802 | 26.984 |
| Bursa (Nilüfer OSB) | 40.232 | 28.910 |
| Konya (Selçuklu OSB) | 37.911 | 32.464 |
| Bolu (Otogar) | 40.736 | 31.606 |

---

## 4. Test data setup

### 4.1 Araç (1 adet — Mercedes Actros 1851 muadili)
- `plaka`: `34 VAL 2026`
- `marka`: `Mercedes-Benz`
- `model`: `Actros 1851`
- `yil`: 2022
- `tank_kapasitesi`: 600
- `hedef_tuketim`: 32.0
- `bos_agirlik_kg`: 8800
- `hava_direnc_katsayisi`: 0.55 (modern aerodinamik)
- `on_kesit_alani_m2`: 8.5
- `motor_verimliligi`: 0.40 (Euro VI)
- `lastik_direnc_katsayisi`: 0.006
- `maks_yuk_kapasitesi_kg`: 26000
- `dingil_sayisi`: 4

### 4.2 Sürücü (1 adet — norm)
- `ad_soyad`: `Validasyon Sürücüsü`
- `score`: 1.0 (nötr, sapma sürücü kaynaklı değil)
- `manual_score`: 1.0
- `ehliyet_sinifi`: `CE`

### 4.3 Lokasyonlar (5 adet)
Yukarıdaki 5 rota için `LokasyonCreate` ile insert. `cikis_lat/cikis_lon/varis_lat/varis_lon` set. `mesafe_km` literatürden. Hidrasyon otomatik (POST /locations veya manuel script).

---

## 5. Adım adım execution

`scripts/p51_real_world_validation.py` — backend container içinde direkt UoW kullanarak çalışacak:

```
1. Setup phase
   1.1 get_or_create_arac(plaka="34 VAL 2026", ...)
   1.2 get_or_create_sofor(ad_soyad="Validasyon Sürücüsü", ...)

2. Lokasyon phase (5 rota)
   2.1 LokasyonService.add_lokasyon(LokasyonCreate(...))
   2.2 (opsiyonel) LokasyonHydrator.hydrate() — sefer create de gerekirse re-fetch eder
   2.3 lokasyon_id'leri topla

3. Sefer phase (5 sefer)
   3.1 her rota için SeferCreate(arac_id, sofor_id, guzergah_id, ...)
   3.2 SeferService.add_sefer(data) — USE_SEFER_FUEL_ESTIMATOR=True olduğu için
       SeferFuelEstimator pipeline tetiklenir:
         - Mapbox Directions (live call, 24h cache)
         - Open-Meteo elevation + weather
         - PhysicsBasedFuelPredictor
         - adjustment factors (weather temp/wind/precip, driver, vehicle_age, seasonal)
   3.3 sefer'leri DB'den geri çek, tahmini_tuketim + tahmin_meta + route_simulation_id oku

4. Karşılaştırma phase
   4.1 Her sefer için: tahmin literatür bandında mı? (expected_low ≤ tahmin ≤ expected_high)
   4.2 Sapma yüzdesi: (tahmin - band_mid) / band_mid × 100
   4.3 Markdown tablo hazırla

5. Rapor phase
   5.1 5/5 yeşil → "Production hazır, MAPE 30 günde ölç"
   5.2 3-4/5 → "Sapan rotanın breakdown'ına bak (factors), kalibrasyon notu"
   5.3 ≤2/5 → "Phase 4 parametre rebalans, USE_SEFER_FUEL_ESTIMATOR=false (acil geri al)"
```

---

## 6. Beklenen risk noktaları

| Risk | Tezahür | Mitigasyon |
|------|---------|------------|
| Mapbox 401/403 | Tahmin tüm rotalarda fail | API key + SecretStr fix doğrula |
| Open-Meteo rate limit | Bazı rotalarda tahmin yok | Retry pattern, gerekirse rotaları seri çalıştır |
| Mapbox mesafe ≠ literatür | %5 sapma normal, %15+ şüpheli | Mapbox'ın çıkışını override etmiyoruz, kabul |
| Bolu rotasında ascent yetersiz | Tahmin 32 çıkar (35-40 beklenir) | Open-Meteo elevation kalitesi sorgula |
| Şehir merkezi koord → kent içi süre yüksek | Mapbox süre fazla, breakdown'da gör | OSB koordinatları kullan (yukarıdaki seçildi) |
| Tüm rotalarda fazla rüzgar | Headwind factor abartılı | breakdown.weather_wind'i incele |

---

## 7. Karar matrisi

| Sonuç | Yeşil rota | Sarı (band ±%10) | Kırmızı (band ±>%20) | Karar |
|-------|------------|------------------|----------------------|-------|
| **A** | 5 | 0 | 0 | ✅ Üretim hazır |
| **B** | 3-4 | 1-2 | 0 | ⚠️ Pilot et, breakdown logla |
| **C** | ≥3 | ≥1 | ≥1 | ⚠️ Sapan rota parametre review |
| **D** | ≤2 | herhangi | herhangi | ❌ Acil geri al + Phase 4 rebalans |

---

## 8. Çıktı artefaktları

1. `docs/superpowers/plans/2026-05-30-p51-real-world-validation-plan.md` (bu dosya)
2. `scripts/p51_real_world_validation.py` (executor)
3. `docs/p51-validation-results-2026-05-30.md` (sonuç raporu — script çıktısından)
4. DB'de: 1 araç + 1 sürücü + 5 lokasyon + 5 sefer (gerçek tahminlerle, validation_ prefix'i ile filtrelenebilir)

---

## 9. Bilinçli olarak kapsam dışı

- Gerçek tüketim girip MAPE hesaplama (pilot işi, bu plan değil)
- Birden fazla araç tipi (1 referans araç yeter — validasyon, varyans değil)
- Birden fazla sürücü skoru (score=1.0 sabit, faktör hata payı izole edilsin)
- Dönüş seferi (one-way yeter — physics simetrik)
- Stress test (bu validation, performance değil)
