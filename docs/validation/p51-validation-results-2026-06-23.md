# P5.1 Real-World Validation Results

Tarih: 2026-06-23T12:07:09.212847+00:00
USE_SEFER_FUEL_ESTIMATOR=True
Yöntem: SeferFuelEstimator.predict() doğrudan çağrı (sefer create timeout bypass)

## Özet tablo

Birincil karar **koşul-nötr** tahminle (physics×araç/şoför, çevresel çarpanlar hariç) verilir — literatür bandları koşul-nötr. `Tam` sütunu koşul-uygulanmış çıktı; `Sanity` = tam çıktı ≤ band üst sınırı ×1.12.

| Rota | Mesafe (km) | Yük (kg) | Nötr (L/100km) | Tam (L/100km) | Beklenen band | Sapma % | Sonuç | Sanity |
|------|-------------|----------|----------------|---------------|---------------|---------|-------|--------|
| VAL-IST-ANK-450 | 482 | 20000 | 33.6 | 34.6 | 30.0 - 35.0 | +3.4% | ✅ GREEN | ✅ |
| VAL-IST-IZM-485 | 482 | 18000 | 31.7 | 32.6 | 29.0 - 33.0 | +2.3% | ✅ GREEN | ✅ |
| VAL-BUR-IST-155 | 215 | 12000 | 30.6 | 34.6 | 28.0 - 32.0 | +1.9% | ✅ GREEN | ✅ |
| VAL-ANK-KON-260 | 276 | 25000 | 32.2 | 35.5 | 31.0 - 36.0 | -3.7% | ✅ GREEN | ✅ |
| VAL-IST-BOL-265 | 303 | 22000 | 35.7 | 39.3 | 34.0 - 40.0 | -3.4% | ✅ GREEN | ✅ |
| VAL-IZM-AYD-130 | 170 | 14000 | 28.4 | 31.8 | 28.0 - 33.0 | -7.0% | ✅ GREEN | ✅ |
| VAL-ANK-ESK-235 | 242 | 19000 | 30.0 | 32.6 | 30.0 - 35.0 | -7.8% | ⚠️ YELLOW | ✅ |
| VAL-IST-TEK-130 | 152 | 16000 | 29.8 | 33.4 | 29.0 - 34.0 | -5.3% | ✅ GREEN | ✅ |
| VAL-KON-AKS-150 | 154 | 23000 | 28.4 | 31.8 | 32.0 - 37.0 | -17.8% | ❌ RED | ✅ |
| VAL-BUR-BAL-150 | 136 | 17000 | 30.5 | 34.6 | 30.0 - 35.0 | -6.1% | ✅ GREEN | ✅ |

**Aggregate (koşul-nötr)**: ✅ 8/10 GREEN, ⚠️ 1 YELLOW, ❌ 1 RED
**Sanity (tam çıktı ≤ band×1.12)**: 10/10 geçti

## Per-rota faktör breakdown

### VAL-IST-ANK-450
- simulation_id: 5
- Mapbox mesafe: 481.8 km (input: 450 km, Δ=+32)
- Tahmini süre: 343 dakika
- Toplam tahmini yakıt: 166.7 L
- Segment: raw=6049, resampled=964, elevation_coverage=62.2%
- **Physics baseline**: 33.59 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.0, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 33.59 (birincil karar)
- **Tam çıktı L/100km**: 34.6 (sanity: ✅)
- **Final L/100km**: 34.6

### VAL-IST-IZM-485
- simulation_id: 6
- Mapbox mesafe: 482.0 km (input: 485 km, Δ=-3)
- Tahmini süre: 346 dakika
- Toplam tahmini yakıt: 157.4 L
- Segment: raw=4935, resampled=965, elevation_coverage=79.6%
- **Physics baseline**: 31.7 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.0, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 31.7 (birincil karar)
- **Tam çıktı L/100km**: 32.65 (sanity: ✅)
- **Final L/100km**: 32.65

### VAL-BUR-IST-155
- simulation_id: 7
- Mapbox mesafe: 215.0 km (input: 155 km, Δ=+60)
- Tahmini süre: 160 dakika
- Toplam tahmini yakıt: 74.4 L
- Segment: raw=2981, resampled=430, elevation_coverage=100.0%
- **Physics baseline**: 30.56 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.1, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 30.56 (birincil karar)
- **Tam çıktı L/100km**: 34.62 (sanity: ✅)
- **Final L/100km**: 34.62

### VAL-ANK-KON-260
- simulation_id: 8
- Mapbox mesafe: 276.0 km (input: 260 km, Δ=+16)
- Tahmini süre: 210 dakika
- Toplam tahmini yakıt: 98.1 L
- Segment: raw=2184, resampled=552, elevation_coverage=100.0%
- **Physics baseline**: 32.25 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.07, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 32.25 (birincil karar)
- **Tam çıktı L/100km**: 35.54 (sanity: ✅)
- **Final L/100km**: 35.54

### VAL-IST-BOL-265
- simulation_id: 9
- Mapbox mesafe: 303.2 km (input: 265 km, Δ=+38)
- Tahmini süre: 224 dakika
- Toplam tahmini yakıt: 119.1 L
- Segment: raw=3364, resampled=607, elevation_coverage=100.0%
- **Physics baseline**: 35.73 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.067, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 35.73 (birincil karar)
- **Tam çıktı L/100km**: 39.27 (sanity: ✅)
- **Final L/100km**: 39.27

### VAL-IZM-AYD-130
- simulation_id: 10
- Mapbox mesafe: 170.1 km (input: 130 km, Δ=+40)
- Tahmini süre: 132 dakika
- Toplam tahmini yakıt: 54.1 L
- Segment: raw=1672, resampled=341, elevation_coverage=100.0%
- **Physics baseline**: 28.37 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.045, wind=1.074, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 28.37 (birincil karar)
- **Tam çıktı L/100km**: 31.84 (sanity: ✅)
- **Final L/100km**: 31.84

### VAL-ANK-ESK-235
- simulation_id: 11
- Mapbox mesafe: 242.0 km (input: 235 km, Δ=+7)
- Tahmini süre: 187 dakika
- Toplam tahmini yakıt: 78.8 L
- Segment: raw=1474, resampled=484, elevation_coverage=100.0%
- **Physics baseline**: 29.97 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.055, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 29.97 (birincil karar)
- **Tam çıktı L/100km**: 32.57 (sanity: ✅)
- **Final L/100km**: 32.57

### VAL-IST-TEK-130
- simulation_id: 12
- Mapbox mesafe: 151.8 km (input: 130 km, Δ=+22)
- Tahmini süre: 123 dakika
- Toplam tahmini yakıt: 50.7 L
- Segment: raw=2237, resampled=304, elevation_coverage=100.0%
- **Physics baseline**: 29.83 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.088, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 29.83 (birincil karar)
- **Tam çıktı L/100km**: 33.43 (sanity: ✅)
- **Final L/100km**: 33.43

### VAL-KON-AKS-150
- simulation_id: 13
- Mapbox mesafe: 153.7 km (input: 150 km, Δ=+4)
- Tahmini süre: 121 dakika
- Toplam tahmini yakıt: 48.9 L
- Segment: raw=898, resampled=308, elevation_coverage=100.0%
- **Physics baseline**: 28.36 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.0, wind=1.088, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 28.36 (birincil karar)
- **Tam çıktı L/100km**: 31.78 (sanity: ✅)
- **Final L/100km**: 31.78

### VAL-BUR-BAL-150
- simulation_id: 14
- Mapbox mesafe: 135.7 km (input: 150 km, Δ=-14)
- Tahmini süre: 101 dakika
- Toplam tahmini yakıt: 46.9 L
- Segment: raw=1171, resampled=272, elevation_coverage=100.0%
- **Physics baseline**: 30.53 L/100km
- Factors: driver=1.0, vehicle_age=1.0, maint=1.0
  - weather: temp=1.014, wind=1.1, precip=1.0, seasonal=1.03
- **Koşul-nötr L/100km**: 30.53 (birincil karar)
- **Tam çıktı L/100km**: 34.59 (sanity: ✅)
- **Final L/100km**: 34.59
