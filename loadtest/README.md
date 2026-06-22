# LojiNext Yük Testi (GO harekatı gate #4)

Bu klasör, prod-readiness gate #4'ü (yük testi + observability kanıtı) kapatmak
için hazır bir [Locust](https://locust.io) senaryosu içerir. **Bu sandbox'ta
çalıştırılamaz** — gerçek bir staging/pre-prod deployment'a karşı çalıştırın.

## Neden Locust (k6 değil)
Proje Python ağırlıklı; Locust ekibin diliyle aynı, web UI'ı var, senaryo
gerçek Python (mevcut endpoint contract'larıyla aynı). k6 (JS) da geçerli bir
alternatif ama ek bir dil/araç getirir.

## Kurulum
```bash
pip install -r loadtest/requirements.txt
```

## Çalıştırma

### Etkileşimli (web UI — keşif için)
```bash
LOAD_USER=<admin> LOAD_PASS=<***> \
  locust -f loadtest/locustfile.py --host https://staging.lojinext.example
# Tarayıcı: http://localhost:8089 → user sayısı + spawn rate gir
```

### Headless (pilot trafiğinin 3-5x'i — gate kanıtı)
Pilot eş-zamanlı operatör sayısını tahmin et (örn. ~30-50), 3-5x ile çarp:
```bash
LOAD_USER=<admin> LOAD_PASS=<***> \
  locust -f loadtest/locustfile.py \
  --host https://staging.lojinext.example \
  --headless -u 150 -r 15 -t 10m \
  --csv loadtest/results
# -u 150  : 150 eş-zamanlı sanal kullanıcı (pilotun ~3-5x'i)
# -r 15   : saniyede 15 kullanıcı rampa
# -t 10m  : 10 dakika
# --csv   : loadtest/results_*.csv özet/detay
```

## Senaryo
`locustfile.py` tipik bir operatör oturumunu taklit eder (READ-ağırlıklı):
giriş → sefer listesi/stats/today (yüksek frekans) → araç/şoför/yakıt listeleri
(orta) → executive KPI + anomaliler (düşük, ağır) → observability probe'ları.

- **Yazma görevleri default KAPALI.** `ENABLE_WRITES=1` ile sefer create de koşulur
  (DİKKAT: hedef DB'de veri üretir — sadece disposable/staging'de aç).

## Gate #4 geçme kriterleri (3-5x yük altında)
| Metrik | Eşik |
|---|---|
| p95 latency (read) | < 800 ms |
| Hata oranı (5xx) | < %1 |
| Unhandled exception | 0 (Sentry'de doğrula) |
| `/system/silent-fallbacks` sayaçları | yük altında patlamıyor |

## Observability kanıtı (gate #4'ün ikinci yarısı)
Yük sırasında **eş zamanlı izle**:
1. **Sentry** (`de.sentry.io`, proje `lojinext`) — yeni unhandled exception
   gelmemeli. Bilerek bir hata tetikle (örn. geçersiz payload) → Sentry'de
   göründüğünü doğrula (alarm zincirinin canlı olduğunun kanıtı).
2. `GET /api/v1/system/silent-fallbacks` — sefer estimator timeout /
   Open-Meteo fail sayaçları. Yük altında hızlı artıyorsa upstream darboğaz var.
3. `GET /api/v1/admin/fuel-accuracy` → `coverage_pct` — tahmin yapılmış sefer
   oranı düşüyorsa estimator yük altında timeout'a düşüyor demektir.

## Çıktı / rapor
`--csv loadtest/results` ile `results_stats.csv` (endpoint başına p50/p95/p99,
RPS, fail%) üretilir. Gate kararını bu dosya + Sentry ekran görüntüsü ile
`docs/sefer_release_candidate_checklist.md` §5 Gate #4'e işle.
