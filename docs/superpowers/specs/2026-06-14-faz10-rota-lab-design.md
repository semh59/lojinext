# Faz 10 — Güzergah Simülasyon UI (Rota Lab) Tasarım (Spec)

**Tarih:** 2026-06-14
**Bağlam:** Faz 10 odak kararı (kullanıcı): segment simülasyon UI. Backend
(`POST /routes/simulate` + `route_simulations`/`route_segments` + tractive motor)
HAZIR; frontend UI YOK. İlgili: [[route-segment-simulation]], [[sefer-fuel-estimator]].

---

## 1. Problem & hedef

Kullanıcı vizyonu (2026-05-28): "arayüzde çıkış-varış koordinatı gir → o
güzergahı segment-segment simüle et → '500m'de 90 km/h, %3 eğimde 60'a düşer'
gibi her parça için hız/eğim/tüketim göster." Backend bunu üretiyor ama frontend
hiç yüzeye çıkarmıyor (`route_simulation`/segment verisi UI'da yok).

**Hedef:** Koordinat/lokasyon + yük + araç girip güzergahı simüle eden, sonucu
(a) mesafe-eksenli **profil** (hız/eğim/tüketim) ve (b) coğrafi **heatmap**
(segment rengi = L/100km) olarak gösteren bir sayfa.

**Kabul:** Kullanıcı çıkış-varış girip "simüle et" diyince segment-segment
sonuç + özet görür; profil ve heatmap gerçek backend verisini yansıtır;
backend+frontend testleri yeşil; CI gate'leri geçer.

## 2. Görselleştirme kararı (bağımlılıksız)

Harita kütüphanesi (mapbox-gl/leaflet) ve frontend Mapbox token'ı YOK; bunları
eklemek secret-yönetimi + VITE env + dep ağırlığı getirir → **YAGNI, eklenmez.**
Mevcut `recharts` (^3.7.0) yeterli:

- **Profil (birincil):** recharts — kümülatif mesafe (x) ekseninde `sim_speed_kmh`,
  `sim_l_per_100km` çizgileri + `grade_pct` alanı. Kullanıcının "şu segment X
  km/h, şu segment Y L/100km" vizyonunun tam karşılığı.
- **Heatmap (coğrafi):** Saf **SVG polyline** — segment `mid_lon/mat`'ları
  equirectangular projeksiyonla viewBox'a ölçeklenir; her segment `sim_l_per_100km`
  ile renklenir (yeşil→kehribar→kırmızı). Harici tile/token YOK; gerçek geometri
  + gerçek renk. İleride gerçek harita istenirse kolay yükseltme (kapsam dışı).

## 3. Backend değişiklikleri (küçük)

`app/api/v1/endpoints/routes.py`:

1. **`SegmentSimResponse` genişlet:** `mid_lon: Optional[float]`, `mid_lat:
   Optional[float]` (SVG heatmap için ZORUNLU — şu an response'ta koordinat yok),
   + `maxspeed_kmh`/`traffic_speed_kmh`/`congestion`/`speed_source` (zenginlik +
   coverage; Task 6'dan beri SegmentOutput taşıyor).
2. **`_serialize_simulation` doldur:** `mid_lon=s.mid_lon, mid_lat=s.mid_lat, ...`
   (mid_lon/lat zaten `route_segments`'te persist; sadece expose).
3. **Persist tutarlılığı:** routes.py `RouteSegment(...)` build'ine (line ~272)
   `maxspeed_kmh/traffic_speed_kmh/congestion` ekle (Task 6 estimator ile aynı;
   `summary.segments` artık bunları taşıyor). Eski "kayboluyor" notu (line 286)
   kalkar.

Endpoint imzası, auth (`get_current_active_user`), rate-limit (10/dk/IP),
persist akışı DEĞİŞMEZ.

## 4. Frontend mimarisi

`frontend/src/`:

- **`services/api/route-sim-service.ts`** — `axiosInstance`; `simulateRoute(req)`
  → `POST /routes/simulate`; tipler (`RouteSimRequest`, `RouteSimResponse`,
  `SegmentSim`). (axiosInstance, fetchWithAuth DEĞİL.)
- **`hooks/useRouteSimulation.ts`** — React Query `useMutation` (simülasyon
  tetik); loading/error/data.
- **`pages/RouteLabPage.tsx`** — ince orchestrator: girdi formu + sonuç bölümleri.
- **`features/route-lab/`** (ağır mantık):
  - `RouteSimForm.tsx` — lokasyon dropdown (mevcut `/locations` verisi) VEYA
    manuel çıkış/varış lat-lon + `ton` + `arac_yasi` + `segment_length_m`;
    "Simüle Et" butonu. lokasyon_id veya koordinat (endpoint ikisini destekler).
  - `RouteHeatmap.tsx` — SVG polyline, equirectangular projeksiyon, segment
    rengi `sim_l_per_100km` (eşik: <30 yeşil, 30-40 kehribar, >40 kırmızı),
    hover tooltip (segment detayı).
  - `RouteProfileChart.tsx` — recharts: hız + tüketim çizgisi, eğim alanı
    (kümülatif mesafe ekseni).
  - `RouteSimSummary.tsx` — kartlar: mesafe, süre, toplam L, avg L/100km,
    ascent/descent, elevation coverage %, speed_source kırılımı.
- **`resources/tr/routeLab.ts`** — Türkçe string'ler (CLAUDE.md: t() değil
  resource objesi).
- **Nav + route:** `App.tsx`'e `/route-lab` route; sidebar'a giriş
  (RequirePermission gerekmez — authed user; endpoint auth ile uyumlu).

## 5. Veri akışı

`RouteSimForm` (lokasyon_id|koord + ton + yas) → `useRouteSimulation.mutate` →
`POST /routes/simulate` → `RouteSimResponse {summary, segments[]}` →
`RouteSimSummary` (summary) + `RouteHeatmap` (segments mid_lon/lat + L) +
`RouteProfileChart` (segments mesafe-kümülatif + speed/grade/L).

## 6. Hata yönetimi

- 502 (Mapbox yok) → kullanıcıya "routing sağlayıcı erişilemez, tekrar dene".
- 422 (eksik koord) → form validasyonu (submit öncesi engelle).
- 429 (rate-limit 10/dk) → "çok fazla istek, biraz bekle".
- elevation_coverage < %100 → uyarı rozeti ("yükseklik verisi kısmi, eğim
  tahmini yaklaşık" — Open-Meteo quota gerçeği şeffaf).
- Boş segment listesi → empty state.

## 7. Test stratejisi

- **Backend:** `SegmentSimResponse` mid_lon/lat + maxspeed alanları serialize
  testi; persist maxspeed/traffic testi (mevcut `test_routes*`/integration'a ek).
- **Frontend (vitest):** service (mock axios), hook (mutation), RouteHeatmap
  (segment→renk eşiği + projeksiyon), RouteProfileChart (render + veri),
  RouteSimForm (lokasyon/koord toggle + validasyon), RouteLabPage (akış,
  loading/error/empty). test-utils wrapper (QueryClient+Router).
- **e2e:** quota müsaitse canlı `POST /routes/simulate` 200 + segment dolu;
  yoksa lokasyon_id ile (Mapbox 24h cache → quota-bağımsız) probe.

## 8. Kapsam dışı (YAGNI)

- Gerçek harita tile'ları (mapbox-gl/leaflet/token) — SVG heatmap yeterli.
- Simülasyon karşılaştırma (A/B rota) — ileride.
- Sefer'e dönüştürme butonu — mevcut sefer create akışı ayrı.
- Real-time/canlı trafik animasyonu.
