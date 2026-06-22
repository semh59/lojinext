# GO Harekatı — Prod-Readiness Gate'leri

> CTO kararı (2026-06-04): proje pilot seviyesinde; GA prod için 5 gate gerekli.
> Bu plan kod-seviyesinde yürütülebilir gate'leri uygular; altyapı/karar gerektirenler işaretli.

**Hedef:** LojiNext'i kontrollü pilottan → güvenilir prod'a taşıyacak gate'leri kapatmak.

---

## Faz 1 — Bağımsız Bug Audit (gate #1) ✅ DONE
Geçmiş sahte raporlar nedeniyle: test yan ürünü olarak bulunan bug'lar + sistematik tarama.

### 1.1 Doğrulanmış 3 latent bug'ı düzelt
- [ ] `fuel.py` async upload: `get_background_job_manager()` yok → doğru fonksiyon/job_manager
- [ ] `redis_cache.py` `get_stats()`: `_fallback_cache` → `_fallback` (AttributeError)
- [ ] `vehicles.py` upload: try/except eksik → domain-aware error handling
- [ ] Her biri için regression testi (gerçek assertion)

### 1.2 Sistematik tarama (benzer pattern'ler)
- [ ] `patch(...)` / çağrı hedefi var olmayan fonksiyonlar (grep + import doğrulama)
- [ ] Endpoint'lerde try/except olmadan dış servis/DB çağrısı (silent 500 riski)
- [ ] `except: pass` / bare except (sessiz yutma)
- [ ] Bulunanları düzelt + test

## Faz 2 — Frontend Coverage %46 → %70+ (gate #2) 🟡 KISMI (+59 gerçek test; dikkatli sprint gerek)
- [ ] vitest coverage gerçek ölçüm + en düşük modüller
- [ ] Subagent batch'leri ile servis/hook/component testleri
- [ ] Kritik akışlar (auth, sefer listesi, dashboard) — gerçek assertion
- [ ] Gate'i gerçek değere çek

## Faz 3 — Sessiz Fallback Görünürlüğü (gate #3) ✅ DONE
- [ ] Sefer estimator NULL-tahmin oranı + Open-Meteo elevation coverage metrikleri
- [ ] `GET /admin/fuel-accuracy` zaten coverage_pct veriyor → alarm eşiği ekle
- [ ] Sentry/log: silent fallback'ler için WARNING + sayaç

## Faz 4 — Yük Testi + Observability Kanıtı (gate #4) 🟡 SCRIPT HAZIR (loadtest/), koşu bekliyor
- [ ] Araç seçimi (locust/k6) — KULLANICI KARARI
- [ ] Pilot trafiğinin 3-5x senaryosu
- [ ] Sentry'nin gerçek hata yakaladığının kanıtı

## Faz 5 — Release Checklist + Bağımsız Doğrulama (gate #5) ✅ DONE
- [ ] `docs/sefer_release_candidate_checklist.md` güncelle
- [ ] Her madde bağımsız doğrulanabilir komut
- [ ] CI tam suite yeşil + coverage gate + alembic check kanıtı
