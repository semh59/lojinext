# BUG — 8 modülde route handler'ları `application/` katmanını atlayıp doğrudan repo/ORM çağırıyor

> ✅ **TAMAMEN ÇÖZÜLDÜ (2026-07-15)** — kullanıcı onayı alındı ("8 dalga
> tam temiz olana kadar durma"). İlk turda bulunan 5 handler (notification
> ×2, fleet ×2, auth_rbac) + ikinci "sıfır-context ajanlarla yeniden
> denetle" turunda bulunan 4 modül daha (driver, anomaly ×2, fuel ×2,
> route_simulation) — toplam 8 modül, ~20 endpoint/handler düzeltildi.
> Tüm commit'ler main'de, CI Hard Gates (OpenAPI drift dahil) TAM YEŞİL.
> Detay aşağıda "Çözüm" bölümünde.

**Bu bir modül taşıma görevi DEĞİL.** FAZ1'in 17 dalga sırasının dışında,
bağımsız bir katman-disiplini temizliği. 3 modül (notification/dalga 2,
fleet/dalga 3, auth_rbac/dalga 6) zaten taşınmış ve main'de yeşil; bu
görev o modüllerin İÇİNDE `route (`api/`) → application/ → repo` akış
disiplinini tamamlıyor. Herhangi bir oturumda, dalga sırası beklenmeden
ele alınabilir.

**Giriş kriteri:** yok (bağımsız). **Çıkış kriteri:** aşağıdaki 5
handler'ın hepsi yalnız `application/`'daki bir use-case fonksiyonunu
çağırıyor; hiçbiri doğrudan `uow.<repo>`/`db.get`/`select(...)` çalıştırmıyor.

---

## Bulgu (2026-07-15, dalga-1-6-detaylı dedektif denetiminde bulundu — dalga 8/anomaly'nin kendi denetimi tamamlandıktan sonra, kullanıcı talebiyle "ilk 8 dalga"yı kapsayan 6 bağımsız-ajan taraması)

Bu 3 modülün geri kalanı (`>90%` dosya) `api/` katmanının **yalnızca**
`application/` fonksiyonlarını çağırdığı disiplinine sıkı uyuyor —
aşağıdaki 5 handler bu deseni bozan istisna:

### a) `v2/modules/notification/api/notification_routes.py:50-142`
`list_rules`/`create_rule`/`update_rule`/`delete_rule` — `uow.notification_repo`'yu
doğrudan çağırıyor, `application/` katmanında karşılık gelen bir
`{list,create,update,delete}_notification_rule.py` yok.

### b) `v2/modules/notification/api/push_routes.py:61-121`
`subscribe`/`unsubscribe` — `uow.session`/`uow.notification_repo`'ya
doğrudan erişiyor + upsert iş kararını (satır ~75-78, synthetic-admin
id≤0 guard'ı dahil) route içinde barındırıyor.

### c) `v2/modules/fleet/api/admin_maintenance_routes.py:214-231`
`download_ics` — `UnitOfWork` açıp `select(AracBakim)`/`select(Arac)`
ORM sorgularını route içinde doğrudan çalıştırıyor.

### d) `v2/modules/fleet/api/vehicle_routes.py:312-322,325-348` ve
`v2/modules/fleet/api/trailer_routes.py:242-252,255-280`
`read_arac`/`update_arac`/`read_dorse`/`update_dorse` — tekil-kayıt
GET/refresh işlemleri `db.get(Arac,...)`/`select(Arac)` ile doğrudan ORM
üzerinden yapılıyor; `public.py`'de zaten mevcut olan `get_vehicle_by_id`
gibi use-case'ler kullanılmıyor.

### e) `v2/modules/auth_rbac/api/admin_role_routes.py` (tüm dosya)
`RolRepository`'yi doğrudan örnekliyor (satır 23, 34, 62, 108, 142);
`application/role_service.py` diye bir dosya hiç yok — modülün diğer 5
route dosyası (`auth_routes.py`, `admin_user_routes.py`,
`preference_routes.py`, `user_routes.py`, `ws_ticket_routes.py`) her
zaman `application/*_service.py`'ye delege ederken bu dosya delege
etmiyor. Ayrıca privilege-escalation guard iş kuralı
(`_assert_no_privilege_escalation`, satır 82-97) `create_role` içinde
(satır 48-60) neredeyse birebir TEKRARLANMIŞ — küçük bir DRY ihlali de
var, aynı düzeltmede ele alınmalı.

## Neden önemli

B.1'in "her dosya tek görev" ilkesi teknik olarak ihlal edilmiyor (repo
sınıfları hâlâ tek sorumluluk taşıyor) ama modüllerin kendi CLAUDE.md'lerinde
dokümante edilen "route → application → repo" akış sözleşmesi bu 5
handler'da tutmuyor. FAZ1'in import-linter/davranışsal-mimari-test gate'i
(henüz aktif değil, "çatı görevleri" listesinde) devreye girdiğinde bu
muhtemelen otomatik yakalanacak bir ihlal sınıfı — şimdiden dokümante
edilmesi o gate'in kurulumunu kolaylaştırır.

## Düzeltme taslağı (öneri, kesinleştirilmemiş)

- (a)/(b): `v2/modules/notification/application/{manage_notification_rules,manage_push_subscription}.py` gibi 1-2 yeni dosya.
- (c): `v2/modules/fleet/application/get_maintenance_ics_data.py` yeni dosya.
- (d): mevcut `public.py` export'larını (`get_vehicle_by_id` vb.) kullanacak şekilde route'ları düzelt — muhtemelen yeni dosya gerekmez.
- (e): `v2/modules/auth_rbac/application/role_service.py` yeni dosya (diğer `*_service.py` free-function deseniyle tutarlı), `_assert_no_privilege_escalation`'ı tek yerden kullanacak şekilde `create_role`'daki tekrarı kaldır.

Her değişiklik davranış-değiştirmeden (mekanik taşıma) yapılmalı, gerçek
DB'ye karşı ilgili modülün mevcut test suite'i (0 regresyon) + OpenAPI
drift kontrolü ile doğrulanmalı.

## Çözüm (2026-07-15)

Tüm 5 handler taslakta önerildiği gibi düzeltildi:

- **(a)** `v2/modules/notification/application/manage_notification_rules.py`
  yeni dosya (`list_rules`/`create_rule`/`update_rule`/`delete_rule`) —
  `notification_routes.py` artık bunlara delege ediyor.
- **(b)** `v2/modules/notification/application/manage_push_subscription.py`
  yeni dosya (`subscribe_push`/`unsubscribe_push`) — `push_routes.py`
  artık bunlara delege ediyor. 🔴 **Bu taşıma sırasında GERÇEK bir bug
  bulundu ve düzeltildi** (B.1'in ötesinde): eski `subscribe`/`unsubscribe`
  hiçbir zaman `uow.commit()` çağırmıyordu — `UnitOfWork`'ün
  ghost-transaction guard'ı ORM identity-map'i kontrol ettiği için
  Core-tarzı `delete()`/attribute-mutasyonlarını farklı şekillerde
  tetikliyor ama HER İKİ durumda da sessiz rollback'e yol açıyordu. Sonuç:
  push subscribe/unsubscribe endpoint'leri başarı dönüyordu ama hiçbir
  satır kalıcı olmuyordu. Taşımadan ÖNCE de vardı (regresyon değil), tek
  satırlık `await uow.commit()` eklenerek düzeltildi. Detay:
  `v2/modules/notification/CLAUDE.md` "Modüle özel iş kuralları" bölümü.
- **(c)** `v2/modules/fleet/application/get_maintenance_ics_data.py` yeni
  dosya — `admin_maintenance_routes.py::download_ics` artık buna delege
  ediyor.
- **(d)** `v2/modules/fleet/application/list_vehicles.py::get_vehicle_by_id`
  ve `list_trailers.py::get_trailer_by_id`'ye `include_inactive: bool =
  False` parametresi eklendi (varsayılan davranışları DEĞİŞMEDİ — diğer
  tüm çağıranlar etkilenmedi); `vehicle_routes.py`/`trailer_routes.py`'nin
  tekil-GET/PUT handler'ları artık bu fonksiyonları `include_inactive=True`
  ile çağırıyor (eski `db.get(...)` ham PK lookup'ının aktif/pasif ayrımı
  yapmama davranışını birebir koruyarak).
- **(e)** `v2/modules/auth_rbac/application/role_service.py` yeni dosya —
  `admin_role_routes.py` artık buna delege ediyor;
  `assert_no_privilege_escalation` tek fonksiyona indirgendi (DRY
  düzeltmesi de dahil).

**Doğrulama:** `ruff check --select E,F,W,I` temiz; `python -m py_compile`
temiz; gerçek `app.api.v1.api` + tüm 4 modülün `public.py`'si local Python
ortamında hatasız import edildi (tam DB/Docker koşumu CI'da doğrulanacak).
Davranış değişikliği yalnız (b)'deki bug fix'i — geri kalanı saf mekanik.

CI: commit 72769a0 (bu 5 bulgunun tamamı) → hard-gates ✓ yeşil.

## İkinci tur — "sıfır-context ajanlarla dedektif denetim" (2026-07-15)

Kullanıcı "8 DALGA TAM TEMİZ OLANA KADAR DURMA" talimatıyla, ilk turun
kapsamadığı kalan modülleri (driver, anomaly, fuel, route_simulation)
sıfırdan context'siz ajanlarla ayrıca taradı. 4 modülde daha aynı sınıf
ihlal bulundu:

### f) `v2/modules/driver/api/{driver_routes.py,coaching_routes.py}`
`get_driver_fleet_stats`, `read_sofor`, `get_driver_performance`,
`get_driver_score_breakdown`, `get_driver_route_profile`, `delete_sofor`,
`get_coaching_insights`, `send_coaching`, `get_coaching_effectiveness` —
hepsi `db: SessionDep` alıp doğrudan repo/raw-SQL çağırıyordu; ayrıca
`send_coaching` içinde inline `UnitOfWork()` açıp `CoachingDelivery` INSERT
eden gerçek bir WRITE operasyonu route içinde barınıyordu.

**Çözüm**: `application/list_sofor.py::get_by_id`'ye `include_inactive`
eklendi + yeni `get_driver_fleet_stats()`; yeni
`application/record_coaching_delivery.py` (coaching INSERT'i route'tan
çıkardı); yeni `application/get_coaching_effectiveness.py`. Tüm route'lar
`db: SessionDep`'i bıraktı, use-case'lere delege ediyor. CI: commit
f818446 (ilk push, kırmızı) → `test_response_shape_standard.py`'de gözden
kaçan bir doğrudan-çağrı test'i (`db=` kwarg'ı kaldırılan imzayla) fix'lendi
→ commit c62b6fc → hard-gates ✓ yeşil (31m32s).

### g) `v2/modules/anomaly/api/investigation_routes.py` (tüm dosya)
B.2 Yakıt Hırsızlığı Soruşturmaları — `create_investigation`,
`list_investigations`, `get_investigation_detail`, `update_investigation`,
`soft_delete_investigation`, `reclassify_investigation`, `get_patterns`
hepsi `db: SessionDep` ile doğrudan `select(...)`/raw SQL/FOR-UPDATE lock
çalıştırıyordu; `application/` katmanında karşılığı yoktu.

**Çözüm**: yeni `application/manage_investigations.py` — bilinçli olarak
`db: AsyncSession`'ı parametre olarak alıyor (kendi `UnitOfWork()`'unu
AÇMIYOR) çünkü `update_investigation`'daki FOR-UPDATE lock + sonraki
`db.commit()` aynı transaction'da kalmak zorunda (root CLAUDE.md'deki
"FOR-UPDATE concurrency invariant" kuralı). Route dosyası artık yalnız
delege ediyor; Telegram alarm broadcast + audit logging (route'un asıl
sorumluluğu değil ama proje konvansiyonunda route'ta kalması kabul edilen
kısımlar: `_build_theft_alarm_text`/`_resolve_alarm_context`/
`_maybe_broadcast_alarm`) route'ta bırakıldı.

Ayrıca `api/anomaly_routes.py::get_fleet_insights` için yeni
`application/get_fleet_insights.py` (not: trip/fleet tablolarını okuyor,
muhtemelen yanlış modülde ama bu görevin kapsamı yalnız katman-disiplini —
taşıma ayrı bir karar).

🔴 **Süreç içi regresyon + düzeltme (bug DEĞİL, benim hatam)**: `/patterns`
route handler'ı `get_patterns` → `get_patterns_route` olarak yeniden
adlandırıldı (import edilen use-case fonksiyonuyla isim çakışmasını önlemek
için) — bu FastAPI'nin otomatik ürettiği `operationId`'yi değiştirdi ve CI
"OpenAPI schema drift check" adımını kırdı (commit fc2c1bf). Düzeltme: route
fonksiyon adı `get_patterns`'e geri alındı, import bunun yerine
`get_patterns as get_patterns_uc` şeklinde alias'landı. Bu vesileyle TÜM
dokunulan route dosyalarında (anomaly/fleet/driver/notification/auth_rbac/
fuel/route_simulation) fonksiyon-adı driftı olmadığı `diff <(git show
0b17d07:$f | grep "^async def") <(grep "^async def" $f)` ile sistematik
doğrulandı — başka hiçbir yerde drift yok.

### h) `v2/modules/fuel/api/fuel_routes.py`
`list_fuel_documents`, `get_fuel_accuracy` — doğrudan `db: SessionDep` ile
raw SQL/aggregation çalıştırıyordu.

**Çözüm**: yeni `application/list_fuel_documents.py` +
`application/get_fuel_accuracy.py`; route'lar delege ediyor; kullanılmayan
`text`/`timedelta` import'ları temizlendi.

### i) `v2/modules/route_simulation/api/route_routes.py::simulate_route`/`get_route_simulation`
~90 satırlık ORM persist/query mantığı (lokasyon/araç çözümü,
`RouteSimulation`/`RouteSegment` INSERT, `selectinload` eager-reload) route
içinde doğrudan çalışıyordu — bu modülde `route_simulations`/
`route_segments` için hiç repository yoktu.

**Çözüm**: yeni `infrastructure/simulation_repository.py`
(`SimulationRepository.create_with_segments`/`get_by_id_with_segments`) +
yeni `application/create_route_simulation.py`
(`create_route_simulation`/`get_route_simulation_by_id`). MissingGreenlet
gotcha'sını önleyen commit-sonrası eager-reload deseni birebir korundu.
Mekanik taşıma, davranış değişikliği yok.

(g)+(i), OpenAPI drift fix'iyle birlikte commit **c7666a1** olarak push
edildi → **hard-gates ✓ yeşil (34m40s)** — bu, "8 dalga tam temiz" görevinin
son commit'i.

## Genel doğrulama özeti (tüm 8 modül)

- Her modülde: `ruff check --select E,F,W,I` temiz, `python -m py_compile`
  temiz, gerçek Python import-chain (container/api.py/public.py) hatasız.
- Her push sonrası gerçek CI (GitHub Actions `hard-gates` job — 34+ backend
  unit/integration/deep-audit adımı + combined coverage gate + frontend
  build/lint/type-check + **OpenAPI schema drift check** + Playwright E2E)
  yeşile dönene kadar bir sonraki modül push edilmedi (kırmızı-CI
  disiplini).
- **Gerçek pre-existing prod bug (1 adet)**: notification push
  subscribe/unsubscribe'ın hiç commit çağırmaması (madde b) — taşımadan
  ÖNCE de vardı, taşıma sırasında keşfedilip düzeltildi.
- **Süreç-içi regresyonlar, taşıma sırasında bulunup aynı turda düzeltildi
  (2 adet)**: fleet'te `AracEntity` round-trip'inin `plaka` alanını
  bozması (madde d, `get_vehicle_raw_by_id` ile çözüldü); anomaly'de
  `get_patterns` handler'ının yeniden adlandırılmasının OpenAPI
  operationId'yi kayması (madde g).
- Kalan tüm değişiklikler saf mekanik taşıma — davranış değişikliği yok.

**Sonuç: "ilk 8 dalga" kapsamındaki TÜM modüllerde (notification, fleet,
auth_rbac, driver, anomaly, fuel, route_simulation) `api → application →
repo` katman disiplini artık tutarlı. Bu doküman kapsamındaki hiçbir açık
bulgu kalmadı.**
