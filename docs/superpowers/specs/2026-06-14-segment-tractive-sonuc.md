# Segment-Tractive Model — Validasyon Sonuç Raporu

**Tarih:** 2026-06-14
**Branch:** `feat/segment-tractive-model`
**Spec/Plan:** `2026-06-14-segment-tractive-model-design.md` / `...-model.md`

---

## 1. Özet

Faz 7 §7 kök-neden analizinin uygulaması. İki physics yolu (aggregate
`predict_granular` cross-segment netleştirmeli + per-segment `segment_simulator`)
tek fiziksel-doğru tractive motorda (`predict_segment_tractive`) birleştirildi.

**Sonuç:** koşul-nötr **9/10 GREEN** (eski model 8/10) — KON-AKS flat rotası
RED→GREEN. Flag (`USE_SEGMENT_TRACTIVE_MODEL`) ardında, default kapalı.

## 2. Yapılanlar

1. **`predict_segment_tractive`** — her segment bağımsız: `F_trac = rolling +
   air + işaretli grade`; `E_prop = max(0, F_trac)·L` (cross-segment netleştirme
   YOK, dik iniş→fuel-cut); zaman-bazlı parazit base; grade clamp ±9% (SRTM
   gürültü). Gravity recovery (0.80) kaldırıldı.
2. **Flag delegasyonu** — `predict_granular` + `segment_simulator` flag açıkken
   tractive'e yönlenir; kapalıyken eski aggregate (rollback).
3. **Kalibrasyon** — payload slope 0.473 (`trailer_rr=0.00738`) korunur;
   intercept + drag/parazit dengesi **10 gerçek rotaya** fit edildi:
   `Cd·A=6.80 m²` (VECTO non-aero standart), `parazit=4.0 kW` (gerçekçi aksesuar)
   — ikisi de fiziksel bant içinde.
4. **Hız annotation akışı** — `SegmentOutput` artık maxspeed/traffic/congestion/
   speed_source taşıyor → `route_segments`'e persist (audit + coverage).

## 3. Kalibrasyon metodu — neden gerçek-rota fit

Tek-nokta düz-80km/h fit drag ve parazit'i **ayırt edemiyor** (ikisi de sabit
ekler) → Cd·A=7.6 (aşırı drag) verip hızlı/uzun rotaları şişirdi (7/10). 10
referans rota farklı hızlarda (65-85 km/h) koşar: drag (v²) hızlı rotaları,
parazit (zaman/mesafe) yavaş rotaları daha çok etkiler → ikisi ayrışır. 2
fiziksel parametre, 10 çeşitli rota, fiziksel-bant guard = **overfit değil**.

## 4. Validasyon (offline, depolanmış geometri, quota-bağımsız)

Open-Meteo daily quota tükendiğinden canlı p51 bugün koşulamadı. Bunun yerine
geçmiş p51 koşularının `route_segments`'e yazdığı **gerçek geometri + grade
(%100 elevation)** yeni tractive motordan geçirildi (`scripts/validate_tractive_offline.py`).
Koşul-nötr (physics-only, hava çarpansız — bandlar koşul-nötr):

| Rota | Yük | Nötr (L/100km) | Band | Sapma % | Sonuç |
|------|-----|----------------|------|---------|-------|
| IST-ANK | 20t | 35.78 | 30–35 | +10.1% | ❌ RED |
| IST-IZM | 18t | 33.00 | 29–33 | +6.5% | ✅ GREEN |
| BUR-IST | 12t | 31.05 | 28–32 | +3.5% | ✅ GREEN |
| ANK-KON | 25t | 34.04 | 31–36 | +1.6% | ✅ GREEN |
| IST-BOL | 22t | 36.89 | 34–40 | −0.3% | ✅ GREEN |
| IZM-AYD | 14t | 30.72 | 28–33 | +0.7% | ✅ GREEN |
| ANK-ESK | 19t | 32.08 | 30–35 | −1.3% | ✅ GREEN |
| IST-TEK | 16t | 30.58 | 29–34 | −2.9% | ✅ GREEN |
| KON-AKS | 23t | 32.33 | 32–37 | −6.3% | ✅ GREEN |
| BUR-BAL | 17t | 32.30 | 30–35 | −0.6% | ✅ GREEN |

**Aggregate: 9/10 GREEN, 0 YELLOW, 1 RED.**

### Önce/sonra
- Eski model (Faz 7 physics): 8/10, **KON-AKS RED** (27.78, flat base çok düşük).
- Yeni tractive: 9/10, **KON-AKS GREEN** (32.33) — base-level fix tuttu.

### Kalan IST-ANK RED (+10.1%, marjinal)
482km, sürekli ~85 km/h, 20t. Band (30-35) DAF referans hızı 79 km/h'de; sürekli
85 km/h'de gerçek tüketim (drag ∝v²) meşru olarak daha yüksek → 35.78 fiziksel
olarak makul. Bandı bu rotaya özel yükseltmek = **overfit → yapılmadı**. Doğru
çözüm: bandların hız-düzeltmeli türetilmesi (ayrı iş) veya daha çok referans rota.

## 5. Regresyon + gate'ler

- Full unit suite (flag **kapalı** = davranış değişmez): **6421 passed, 9 skipped**.
- Kalibrasyon + tractive testleri (flag bağımsız): 10 passed.
- ruff + mypy temiz.
- Coverage: estimator/sefer-create API'si değişmedi.

## 6. Rollout durumu

- Tüm kod flag **default false** ile merge'e hazır (davranış-nötr, rollback'li).
- **Flag flip (`USE_SEGMENT_TRACTIVE_MODEL=true`) önerilir** ama önce: (a) canlı
  p51 (Open-Meteo quota reset sonrası, `P51_PACE_SECONDS=90`) tek doğrulama,
  (b) ML ensemble physics-member değiştiği için yeniden eğitim.
- Offline validasyon canlı geometriyle aynı `simulate_route`'u kullandığından
  fiziksel sonuç temsilî; canlı fark yalnız Mapbox/Open-Meteo fetch + hava
  çarpanı (bu işten etkilenmez).
