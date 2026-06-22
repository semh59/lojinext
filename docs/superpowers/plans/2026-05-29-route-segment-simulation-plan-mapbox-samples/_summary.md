# Mapbox Directions Phase 0 — canlı API özeti

Bu rapor `scripts/mapbox_phase0_probe.py` tarafından üretildi. Raw JSON dosyaları bu klasörde (`{route}-raw.json`).

## İstanbul → Ankara (450 km, otoyol-ağırlıklı)
- Distance: **443.5 km**, Duration: **251.6 min**
- Annotation keys present: `['congestion', 'congestion_numeric', 'distance', 'duration', 'maxspeed', 'speed']`
- **road_class annotation present**: `False`  ← mapbox_client.py:146 bug teyit göstergesi
- Segment count: **5400** (avg length: **82.1 m**)
- speed annotation present: **100.0%** of segments
- maxspeed total: 5400, unknown/none: 572
- maxspeed top values: `{'130km/h': 1962, '120km/h': 1613, '140km/h': 723, 'unknown': 572, '80km/h': 158, '70km/h': 100, '50km/h': 93, '82km/h': 78, '90km/h': 72, '30km/h': 29}`
- congestion breakdown: `{'unknown': 675, 'low': 4605, 'moderate': 91, 'heavy': 29}`
- congestion_numeric range: 0 .. 91
- step count: 38
- intersections with mapbox_streets_v8.class: **99.9%** (road_class reconcile fallback için kritik)
- mapbox_streets_v8.class breakdown: `{'street': 7, 'tertiary': 8, 'tertiary_link': 3, 'primary': 75, 'primary_link': 8, 'trunk': 153, 'trunk_link': 10, 'motorway': 496, 'motorway_link': 14, 'secondary_link': 2, 'secondary': 17}`

## Maslak → Kadıköy (İstanbul içi, şehir)
- Distance: **18.9 km**, Duration: **31.7 min**
- Annotation keys present: `['congestion', 'congestion_numeric', 'distance', 'duration', 'maxspeed', 'speed']`
- **road_class annotation present**: `False`  ← mapbox_client.py:146 bug teyit göstergesi
- Segment count: **571** (avg length: **33.1 m**)
- speed annotation present: **100.0%** of segments
- maxspeed total: 571, unknown/none: 119
- maxspeed top values: `{'70km/h': 206, '90km/h': 186, 'unknown': 119, '50km/h': 28, '30km/h': 17, '80km/h': 15}`
- congestion breakdown: `{'unknown': 27, 'low': 418, 'moderate': 103, 'heavy': 23}`
- congestion_numeric range: 0 .. 90
- step count: 16
- intersections with mapbox_streets_v8.class: **99.3%** (road_class reconcile fallback için kritik)
- mapbox_streets_v8.class breakdown: `{'street': 17, 'tertiary': 7, 'tertiary_link': 1, 'primary': 74, 'primary_link': 10, 'motorway': 36}`

## Bursa → Antalya (~700 km, dağlık karışım)
- Distance: **547.9 km**, Duration: **355.0 min**
- Annotation keys present: `['congestion', 'congestion_numeric', 'distance', 'duration', 'maxspeed', 'speed']`
- **road_class annotation present**: `False`  ← mapbox_client.py:146 bug teyit göstergesi
- Segment count: **5177** (avg length: **105.8 m**)
- speed annotation present: **100.0%** of segments
- maxspeed total: 5177, unknown/none: 1201
- maxspeed top values: `{'110km/h': 2249, 'unknown': 1201, '70km/h': 776, '50km/h': 413, '90km/h': 344, '80km/h': 116, '82km/h': 74, '30km/h': 4}`
- congestion breakdown: `{'unknown': 2813, 'low': 2343, 'moderate': 21}`
- congestion_numeric range: 0 .. 54
- step count: 28
- intersections with mapbox_streets_v8.class: **99.9%** (road_class reconcile fallback için kritik)
- mapbox_streets_v8.class breakdown: `{'primary': 72, 'secondary': 25, 'tertiary_link': 14, 'trunk': 1360, 'trunk_link': 4, 'primary_link': 3, 'secondary_link': 1, 'tertiary': 11, 'street': 2}`
