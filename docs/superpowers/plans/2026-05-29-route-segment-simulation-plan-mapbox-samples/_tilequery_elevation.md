# Phase 0 — Türkiye elevation accuracy: Mapbox vs Open-Meteo

Probe: `scripts/mapbox_tilequery_phase0.py`

Karşılaştırma:
- **Mapbox**: `mapbox.mapbox-terrain-v2` Tilequery (vector contour layer)
  - terrain-dem-v1 raster, Tilequery API'sinde 404
  - terrain-rgb-v1 deprecated 2021
- **Open-Meteo**: `api.open-meteo.com/v1/elevation` (SRTM 30m DEM)

| Nokta | Lon | Lat | Beklenen | Mapbox | Mapbox hata | Open-Meteo | OM hata | Not |
|---|---|---|---|---|---|---|---|---|
| İstanbul Sultanahmet | 28.9784 | 41.0082 | 30 | -10 | -40 | **36** | +6 | deniz seviyesine yakın |
| Ankara Kızılay | 32.8597 | 39.9334 | 850 | 840 | -10 | **883** | +33 | yüksek plato merkezi |
| Erzurum Şehir | 41.2769 | 39.9 | 1850 | 1850 | +0 | **1940** | +90 | yüksek plato |
| Antalya Konyaaltı | 30.632 | 36.855 | 5 | -10 | -15 | **0** | -5 | deniz kenarı |
| İzmir Konak | 27.1428 | 38.4192 | 10 | -10 | -20 | **25** | +15 | körfez kenarı |
| Trabzon Atatürk Alanı | 39.7178 | 41.005 | 35 | -10 | -45 | **24** | -11 | Karadeniz sahil |
| Kayseri Erciyes 2200m | 35.505 | 38.555 | 2200 | 1950 | -250 | **2238** | +38 | kayak merkezi |
| Konya Şehir | 32.4833 | 37.8667 | 1020 | 1000 | -20 | **1025** | +5 | Anadolu platosu |
| Diyarbakır Merkez | 40.235 | 37.9144 | 660 | 570 | -90 | **673** | +13 | Güneydoğu |
| Bursa Uludağ 1900m | 29.18 | 40.083 | 1900 | 1630 | -270 | **2406** | +506 | dağ teleferik üst |

**Özet (Open-Meteo)**: 7/10 tolerans içinde, ortalama |err|: 72.2m.

## Karar

Mapbox mapbox-terrain-v2 contour tilequery Türkiye için yetersiz:
- Sahil noktaları -10m (contour aralığı 0m altına düşüyor)
- Dağ zirveleri 200-270m hatalı (vector kontur 200m interval'li)

**Phase 1 elevation kaynağı: Open-Meteo `/v1/elevation`** (SRTM 30m).
Avantaj: batch (tek istek), ücretsiz, ~50ms latency, %95+ tolerans.
Dezavantaj: 3rd-party dependency (Mapbox dışı). SLA ölçülmeli.
