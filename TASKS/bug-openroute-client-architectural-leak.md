# BUG — `OpenRouteClient` mimari sızıntısı: 3 ilgisiz sorumluluk + tablo-sahipliği ihlali

> ✅ **ÇÖZÜLDÜ (2026-07-18, tam-denetim düzeltme turu).** Aşağıdaki
> "Önerilen çözüm"ün 1-2. maddeleri uygulandı: `geocode`/`_call_geocode_api`
> ve `update_route_distance` silindi (3. implementasyon — `app.core.services.
> openroute_service` — ayrı, henüz taşınmamış bir görev, bu kapsamda
> DOKUNULMADI, madde 3'ün dediği gibi ayrı bırakıldı). `scripts/
> enrich_existing_data.py` `location.public.geocode_location` kullanacak
> şekilde güncellendi. Test dosyaları (`test_openroute_client_coverage.py`/
> `_more.py`, `test_infrastructure/test_openroute_client.py`,
> `test_route_api.py`) ilgili ölü-kod testleri kaldırılarak güncellendi.
> `OpenRouteClient` artık yalnız ORS distance+cache sorumluluğu taşıyor.
> Kabul kriterlerinin 1-2-4-5-6. maddeleri karşılandı; 3. madde (üçüncü
> geocode implementasyonunun da birleştirilmesi) bilinçli olarak kapsam
> dışı bırakıldı — ayrı bir görev gerektirir.

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Bu bir modül taşıma görevi DEĞİL.** FAZ1'in 17 dalga sırasının dışında,
bağımsız bir bug/cleanup görevidir. `v2/modules/route_simulation/`
dalga 1'de zaten taşınmış durumda; bu görev o modülün İÇİNDE bir
mimari-borç temizliği. Herhangi bir oturumda, dalga sırası beklenmeden
ele alınabilir.

**Giriş kriteri:** yok (bağımsız). **Çıkış kriteri:** `OpenRouteClient`
yalnız ORS distance-client sorumluluğunu taşıyor; `geocode`/
`update_route_distance` ya silinmiş ya da doğru modüle/dosyaya taşınmış;
`lokasyonlar` tablosuna route_simulation'dan hiçbir yazma yolu kalmamış.

---

## 1. Bulgu (2026-07-14, dalga1-5 gerçek-DB + gerçek-yük denetiminde bulundu)

`v2/modules/route_simulation/infrastructure/openroute_client.py`'deki
`OpenRouteClient` sınıfı (satır 32-616) B.1 kuralını ("bir dosya/sınıf =
bir sorumluluk") üç ayrı yerde ihlal ediyor:

### a) Meşru kısım (dokunulmamalı)
`get_distance`/`_call_api`/`_get_from_cache`/`_save_to_cache`
(satır 94-436, 245-436, 367-436) — ORS Directions API ikincil sağlayıcı
istemcisi + cache. Bu modülün gerçek sorumluluğu, prod'da
`application/get_route_details.py` üzerinden aktif kullanılıyor.

### b) `geocode`/`_call_geocode_api` (satır 169-227) — DRY ihlali + modül sınırı bulanıklığı
`location` modülünün **kendi** geocode akışını (`v2/modules/location/
infrastructure/geocode_providers.py::geocode_via_openroute`) tekrarlıyor
— ki O da ayrıca `app/core/services/openroute_service.py`'ye (henüz
route_simulation'a taşınmamış eski kod, route_simulation CLAUDE.md'de
"geçici bağımlılık" olarak zaten not düşülmüş) sarılı üçüncü bir
implementasyon. Yani aynı "OpenRoute geocode" işi için **üç** kod yolu
var: (1) bu dosyadaki `geocode()`, (2) `location`'ın
`geocode_via_openroute()`, (3) eski `app.core.services.openroute_service`.

Prod route'larından (`api/route_routes.py`) hiç çağrılmıyor. Tek çağıran:
`scripts/enrich_existing_data.py:88,98` (bağımsız, ad-hoc bir script).
Testler (`app/tests/unit/test_openroute_client_coverage.py`,
`test_openroute_client_more.py`) da bu path'i kapsıyor.

### c) `update_route_distance` (satır 509-616) — EN CİDDİ: tablo-sahipliği ihlali
`lokasyonlar` tablosuna doğrudan ham SQL `UPDATE` atıyor (repository
pattern bypass). Root `CLAUDE.md` VE hem `location/CLAUDE.md` hem
`route_simulation/CLAUDE.md` `lokasyonlar` tablosunun **tek sahibinin
`location` modülü** olduğunu açıkça belirtiyor — route_simulation yalnız
`route_paths`/`route_simulations`/`route_segments` sahibi.

**Hiçbir prod route'undan çağrılmıyor** — sıfır non-test caller
doğrulandı (`grep -rn "update_route_distance" app/ v2/ scripts/` →
yalnız `app/tests/integration/test_route_api.py`,
`app/tests/unit/test_infrastructure/test_openroute_client.py`,
`app/tests/unit/test_openroute_client_more.py`). Tamamen ölü/legacy kod.

## 2. Neden şimdi bulundu, neden daha önce yakalanmadı

Dalga 1 (location+route_simulation) taşımasında bu sınıf **birebir
taşındı** (davranış değiştirmeden) — taşıma disiplini gereği (mevcut
davranışı korumak) bu mimari borç de olduğu gibi taşındı, o dalganın
kapsamı "yer değiştirme", "yeniden mimarlaştırma" değildi. 2026-07-14'te
dalga1-5'in TÜMÜ için yapılan bağımsız B.1 denetiminde (gerçek dosya
içerikleri karşılaştırılarak) ortaya çıktı.

## 3. Önerilen çözüm (araştırma gerektirir, önceden karara bağlanmadı)

1. `update_route_distance` — kullanılmadığı kesinleşirse (script/doküman
   taraması ile bir kez daha doğrulanmalı) SİLİNMELİ. Kalması gerekiyorsa
   `location` modülünün `public.py` API'si üzerinden `LokasyonRepository`
   kullanacak şekilde yeniden yazılmalı (raw SQL değil).
2. `geocode`/`_call_geocode_api` — `location/infrastructure/
   geocode_providers.py`'deki mevcut `geocode_via_openroute` ile
   birleştirilmeli (üç implementasyon bire indirilmeli); route_simulation
   tarafında yalnız `get_distance` kalmalı. `scripts/enrich_existing_data.py`
   güncellenmiş import'a taşınmalı.
3. Üçüncü implementasyon (`app.core.services.openroute_service.py`, eski
   app/) route_simulation'ın kendi kalan-taşınmamış parçası — bu görevle
   AYNI ANDA ele alınabilir ya da route_simulation'ın ikinci dilimine
   (henüz planlanmadı, `route_simulation/CLAUDE.md`'de not var) bırakılabilir,
   karar kullanıcıya bırakılmalı.
4. Test dosyaları (`test_openroute_client_coverage.py`,
   `test_openroute_client_more.py`, `test_route_api.py`'nin ilgili testi,
   `test_infrastructure/test_openroute_client.py`'nin ilgili testi) yeni
   dosya konumuna göre bölünmeli/taşınmalı.

## 4. Doğrulama planı

- `grep -rn "\.geocode(\|update_route_distance" app/ v2/ scripts/` — taşıma
  sonrası eski import path'i kalmamalı.
- Gerçek DB'ye karşı route_simulation + location testleri (bkz.
  `docs/superpowers/audits/2026-07-14-dalga1-5-real-db-real-load-audit.md`
  §1'deki `-k` filtreleri) yeşil kalmalı.
- OpenAPI schema drift kontrolü (route sözleşmesi değişmemeli, bu saf
  bir iç-mimari temizlik).
- `scripts/enrich_existing_data.py`'nin hâlâ çalıştığı manuel doğrulanmalı
  (güncellenen import'la).

## Kabul kriterleri
- [ ] `OpenRouteClient` yalnız `get_distance`/cache sorumluluğunu taşıyor
- [ ] `lokasyonlar` tablosuna route_simulation'dan hiçbir yazma yolu kalmadı
- [ ] Tek bir OpenRoute-geocode implementasyonu kaldı (üç değil)
- [ ] `scripts/enrich_existing_data.py` güncellendi, manuel doğrulandı
- [ ] Test dosyaları yeni konuma taşındı, gerçek DB'ye karşı yeşil
- [ ] `TASKS/STATUS.md`'deki ilgili not kaldırıldı
