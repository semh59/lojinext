# Phase 12-18 Master Task - Verified Unresolved Plan - 2026-03-21

## Current Status

Bu dosya yalniz repo uzerinde bugun de unresolved olarak dogrulanmis maddeleri tasir.
Amac, Faz 12-18 arasindaki production-readiness calismasini tek belgede,
karar-birakmayan, agent-ready ve uygulanabilir sirada toplamaktir.

Bu dosyada uc hat birlikte zorunlu olarak yurur:

- `B-code remediation`: dogrulanmis acik sorunlarin kapatilmasi
- `Production truth cleanup`: fake/mock/prototype/simulated/hardcoded/no-op
  davranislarin temizlenmesi
- `Technical English conversion`: UI Turkish resource-only kalirken teknik yuzeyin
  English-only olmasi

Kaynaklar:

- `tmp/validation/KRITIK_HATALAR_VE_COZUM_PLANI_DOGRULAMA_2026-03-19.md`
- `docs/production-foundation/frozen-contracts.md`
- `docs/production-foundation/foundation-inventory-2026-03-20.md`

Bu dosyada cozulmus veya sadece tarihsel/editorial nitelikte kalan maddeler ana faz
govdesine alinmamistir. Bu bilincli bir karardir. Hedef, implementerin yalniz
bugun gercekten acik olan islerle ugrasmasidir.

Mevcut temel ilerleme:

- `reports`, `fuel`, `locations`, `admin/*`, `trips` ve `fleet` yuzeyinde
  resource-only Turkish gecisi kismen uygulanmis durumda
- bazi dormant runtime widget'lar ve non-prod script'ler daha once temizlendi
- public trip contract ve bazi persistence/training akislari uzerinden `is_real`
  buyuk olcude sokuldu
- `SeferService` testleri DB'siz unit standardina yaklastirildi
- PostgreSQL test reseti stale session terminate + schema recreate ile daha stabil
  hale getirildi

Acik kalan buyuk bloklar:

- trips API ve modal akislari
- trip table/telemetry veri dogrulugu
- locations KPI ve route analysis UX dogrulugu
- admin sayfalari veri dogrulugu ve React Query standardi
- shared UI / fuel / driver / notification yuzeyi
- orphan ML kodu, predictor truthfulness, route cache, import, dashboard ve
  reporting dogrulugu
- clean rebuild, English schema, non-route execution audit, packaging/secret
  hygiene, validation raporu yeniden uretimi

Son dogrulama sonuclari:

- `pytest app/tests/unit -q` -> `300 passed, 1 skipped`
- `pytest app/tests/integration -q` -> `42 passed, 1 skipped`
- `pytest app/tests -q` -> `479 passed, 3 skipped`
- `pytest tests -q` -> `247 passed, 1 skipped`
- `npm --prefix frontend run test -- --run` -> `74 passed`
- `npm --prefix frontend run build` -> `passed`
- `npm --prefix frontend run lint` -> `passed`
- `docker compose config` -> `passed`

Acik notlar:

- `sklearn` feature-name warning ailesi kapanmis degil
- `LLMClient.chat was never awaited` warning ailesi kapanmis degil
- `docker compose config` sentaktik olarak gecerli ama secret hygiene acigi halen
  var

## Locked Decisions + Phase Gate Standard

Bu kararlar artik tartismaya acik degildir:

- `Clean Rebuild`
- `No migration of fake operational data`
- `UI Turkish = resource-only`
- `Technical side = English-only`
- `No fake/prototype/runtime truth`
- `is_real = remove completely`
- `Phase 12+ cannot override frozen contracts`

Merkezi faz kapisi kurallari:

- Her faz once ilgili bug'i kirmizi gosteren yeni/regresyon testi yazar.
- Sonra fix yapilir.
- Faz sonunda tek kirmizi test bile varsa sonraki faza gecilmez.
- Migration iceren fazlarda `upgrade -> smoke -> downgrade -> upgrade` clean DB
  roundtrip zorunludur.
- Backend fazi icin ilgili unit + integration/API + cumulative smoke birlikte
  zorunludur.
- Frontend fazi icin ilgili interaction tests + `npm --prefix frontend run build`
  zorunludur.
- Veri akisi degisiyorsa service contract mock testi de zorunludur.

Her faz icin iki ek acceptance kriteri vardir:

- `Production truth cleanup in this phase`
- `English-only conversion in this phase`

Bu iki baslik hicbir fazda yan not degildir. O fazin kapanis kriteridir.

## Phase 12 - Trips API + Form Akislari

### Goal

- trips API hata sinirlarini dogruya cekmek
- prompt/confirm tabanli form ve status akisini production modal standardina almak
- encoding/template kalanlarini kapatmak

### Included B-codes

- Kanonik: `B-31`, `B-33`, `B-38`, `B-46`, `B-47`, `B-48`
- Destekleyici unresolved maddeler: `B-06`, `B-30`, `B-32`, `B-SAI-01`

### Current repo state

- `B-31`: `app/api/v1/endpoints/trips.py` icinde genis `except Exception` bloklari
  duruyor
- `B-33`: `TripsModule` ve bagli akislarda native dialog kullanimlari validation
  raporunda acik
- `B-38`: durum degistirme akislarinin bir kismi hala `window.prompt` sinifinda
  legacy davranis tasiyor
- `B-46`: tekil status update akisi modal standardina tam alinmamis
- `B-47`: sefer silme akisi native confirm izleri tasiyor
- `B-48`: yakit/lokasyon/surucu/veri yonetimi silme onayi native dialog ile
  gidiyor
- `B-06`: config/dev boot tarafinda required API key kokusu tamamen temizlenmis
  degil
- `B-30`: backend tarafinda mojibake kalintilari suruyor
- `B-32`: `.env.example` / setup template tam degil
- `B-SAI-01`: `smart_ai_service.py` icinde yogun mojibake duruyor

### Problem explanation

#### B-31

- Problem:
  - broad `except Exception` bloklari domain hata tiplerini duzlestiriyor
- Production etkisi:
  - client domain failure ile infrastructure failure'i ayiramiyor
  - status code davranisi bozuluyor
  - observability kalitesi dusuyor
- Kok neden:
  - endpoint seviyesinde typed exception boundary yerine blanket catch kullaniliyor
- Decision-complete fix:
  - typed exception boundary kurulacak
  - validation, not-found, permission, conflict, dependency ve unexpected infra
    hata sinirlari ayristirilacak
  - endpoint seviyesinde blanket catch kaldirilacak veya sadece controlled
    re-raise/logging icin daraltilacak
- Tests:
  - trip endpoint error mapping testleri
  - invalid payload tests
  - permission failure tests
  - not-found tests
  - business conflict tests
  - unexpected infra failure tests

#### B-33

- Problem:
  - native confirm/prompt kullanan trip action akislari ortak modal standardini
    deliyor
- Production etkisi:
  - tutarsiz UX
  - invalid input riski
- Kok neden:
  - legacy action wiring modal altyapisina tasinmamis
- Decision-complete fix:
  - trip form, status ve destructive action akislari ortak modal systemine alinacak
  - typed modal payload ve explicit action labels kullanilacak
- Tests:
  - modal interaction testleri
  - keyboard interaction tests

#### B-38

- Problem:
  - durum degisimi prompt ile yapiliyor
- Production etkisi:
  - gecersiz value girebilme
  - enum disi state riski
- Kok neden:
  - status update action'i modal/select contract'ina baglanmamis
- Decision-complete fix:
  - status secimi controlled modal + canonical enum ile yapilacak
- Tests:
  - status modal selection tests

#### B-46

- Problem:
  - tekil status update akisi bulk modal standardindan kopuk
- Production etkisi:
  - tekil ve toplu islem ayni kurali uygulamiyor
- Kok neden:
  - action orchestration duplicate ve legacy
- Decision-complete fix:
  - single-status ve bulk-status ortak service + modal contract'ina alinacak
- Tests:
  - single/bulk status parity tests

#### B-47

- Problem:
  - trip delete akisi native confirm kullaniyor
- Production etkisi:
  - inconsistent destructive action behavior
- Kok neden:
  - reusable delete modal trip akislariyla baglanmamis
- Decision-complete fix:
  - trip delete icin dedicated confirm modal + mutation flow kurulacak
- Tests:
  - trip delete modal interaction tests

#### B-48

- Problem:
  - fuel/location/driver/data-management delete akislarinda native confirm izleri var
- Production etkisi:
  - destructive actions tum urunde farkli davranis gosteriyor
- Kok neden:
  - ortak confirm modal standardi tum sayfa/modullere yayilmamis
- Decision-complete fix:
  - tum aktif delete akislari ortak destructive modal standardina alinacak
- Tests:
  - cross-module delete modal tests

#### B-06

- Problem:
  - required API key contract'i local `.env` ile maskelenmis durumda; kod seviyesi
    boot dependency kokusu suruyor
- Production etkisi:
  - config davranisi environment'a fazla bagimli
- Kok neden:
  - config fallback ve required alan sinirlari net degil
- Decision-complete fix:
  - config alanlari environment-specific template ve startup validation ile netlestir
- Tests:
  - config startup validation tests

#### B-30

- Problem:
  - backend teknik dosyalarda mojibake kalintilari var
- Production etkisi:
  - log/debug/doc okunabilirligi bozuluyor
- Kok neden:
  - encoding cleanup dalgasi tam bitmemis
- Decision-complete fix:
  - touched backend files UTF-8 ve temiz metin standardina cekilecek
- Tests:
  - mojibake scan

#### B-32

- Problem:
  - `.env.example` ve setup template eksik
- Production etkisi:
  - clean rebuild ve local bootstrap belirsizlesiyor
- Kok neden:
  - live `.env` ile calisma, template tamligini geri plana itmis
- Decision-complete fix:
  - env example, setup note ve startup requirements tek kaynakta tamamlanacak
- Tests:
  - env template completeness checks

#### B-SAI-01

- Problem:
  - `smart_ai_service.py` icinde yogun mojibake var
- Production etkisi:
  - technical readability bozuk
- Kok neden:
  - eski encoding kalintisi ve gecikmis dil temizligi
- Decision-complete fix:
  - dosya tam UTF-8 ve English-only technical metne cekilecek
- Tests:
  - targeted mojibake scan

### Production truth cleanup in this phase

- trips API hata tipleri generic `500` altinda duzlesmeyecek
- status/delete flows native prompt/confirm ile kontrolsuz veri kabul etmeyecek
- destructive actions ortak modal standardinda explicit ve audited olacak

### English-only conversion in this phase

- touched trip API, modal logic, status/delete flows ve ilgili test dosyalarinda
  technical Turkish kalmayacak
- UI Turkish yalniz resource/messages tarafinda kalacak
- mojibake kalanlari temizlenecek

### Implementation steps

1. `trips.py` blanket catch'lerini typed exception boundary ile degistir
2. trip single/bulk status ve delete akislari icin ortak modal/mutation standardi kur
3. fuel/location/driver/data management delete akislariyla ayni confirm standardini
   esitle
4. `.env.example`, setup note ve startup validation yuzeyini tamamla
5. touched backend technical files ile `smart_ai_service.py` icindeki Turkish
   technical text'i temizle

### Files/subsystems affected

- `app/api/v1/endpoints/trips.py`
- `app/services/smart_ai_service.py`
- trip status/delete modal components
- module-level delete actions
- env templates / startup config docs

### Tests

- trip endpoint error mapping testleri
- modal interaction testleri
- browser-compat regression testleri
- config startup validation tests
- mojibake scan

### Exit gate

- `B-31`, `B-33`, `B-38`, `B-46`, `B-47`, `B-48`, `B-06`, `B-30`, `B-32`,
  `B-SAI-01` kapanmis olacak
- blanket `except Exception` siniri kalmayacak
- active destructive/status flows native prompt/confirm ile calismayacak
- touched technical files English-only olacak
- tek kirmizi test kalmayacak

## Phase 13 - Trip Tablosu ve Telemetri Sunumu

### Goal

- trip table, telemetry ve progress sunumunu gercek veri kaynaklarina baglamak

### Included B-codes

- `B-34`, `B-44`, `B-45`

### Current repo state

- `B-34`: sefer tablosu tahmin/gercek yakit degerlerini gostermiyor
- `B-44`: B-34 ile ayni acik tekrar ediyor; tablo/kart uyumu yok
- `B-45`: status progress ve etiketler sabit kurala bagli, veri temelli degil

### Problem explanation

#### B-34

- Problem:
  - trip tablosu tahmin ve gercek yakit degerlerini karsilastirmali gostermiyor
- Production etkisi:
  - kullanici sapmayi goremiyor
- Kok neden:
  - tablo kolon modeli ve service DTO'su bu yuzeyi eksik tasiyor
- Decision-complete fix:
  - tahmini yakit, gercek yakit, fark ve durum kolonlari query-backed olarak
    tabloya eklenecek
- Tests:
  - `TripTable` render/snapshot testleri

#### B-44

- Problem:
  - ayni acik tablo ve kart sunumu arasinda da suruyor
- Production etkisi:
  - farkli UI yuzeyleri farkli gercek anlatiyor
- Kok neden:
  - ortak trip metrics presenter yok
- Decision-complete fix:
  - tablo, analytics ve ozet kartlari ortak trip metrics presenter ile beslenecek
- Tests:
  - trip metrics parity tests

#### B-45

- Problem:
  - status progress ve renk/etiket mantigi sabit kurala bagli
- Production etkisi:
  - veri tabanli olmayan durum algisi olusuyor
- Kok neden:
  - progress hesaplamasi gercek state, zaman ve veri mevcudiyetine dayanmiyor
- Decision-complete fix:
  - progress state, canonical status, tamamlanma kosullari ve mevcut veri alanlarina
    baglanacak
- Tests:
  - progress computation tests
  - sapma renk testi

### Production truth cleanup in this phase

- guessed/hardcoded progress kaldirilacak
- tahmin-gercek yakit ve sapma alanlari yalniz gercek veri varsa gosterilecek
- veri yoksa bos/unknown state gosterilecek

### English-only conversion in this phase

- trip table, telemetry, helper, presenter ve test yuzeyi English-only technical
  olacak
- UI Turkish yalniz resources uzerinden gelecek

### Implementation steps

1. trip DTO ve table view-model'u tahmin-gercek-yakit-sapma alanlariyla genislet
2. tablo, analytics ve telemetry icin ortak trip metrics presenter yaz
3. status progress hesabini canonical data-backed kurala cek
4. sapma renk dilini anlamsal ve source-backed hale getir

### Files/subsystems affected

- trip table
- trip telemetry / analytics presenters
- trip service DTO layer

### Tests

- `TripTable` render/snapshot testleri
- sapma renk testi
- trip module page smoke

### Exit gate

- `B-34`, `B-44`, `B-45` kapanmis olacak
- tahmin/gercek/sapma sunumu source-backed olacak
- hardcoded progress kalmayacak
- touched technical files English-only olacak
- tek kirmizi test kalmayacak

## Phase 14 - Locations UX ve Analiz Gorsellestirme

### Goal

- locations KPI, route analysis ve failure UX yuzeyini gercek veri ve acik contract
  uzerine kurmak

### Included B-codes

- Kanonik: `B-27`, `B-39`, `B-61`, `B-62`, `B-63`, `B-65`, `B-36`
- Destekleyici unresolved maddeler: `B-28`, `B-09`, `B-10`, `B-11`, `B-12`,
  `B-13`, `B-14`

### Current repo state

- `B-27`: `LocationsPage` KPI kartlari hardcoded
- `B-39`: detayli yol tipi breakdown yok
- `B-61`: canli/sebeke dili yaniltici kok tasiyor
- `B-62`: B-39 ile ayni breakdown acigi ikinci yuzde suruyor
- `B-63`: analiz isimleri karisik; 403 nedeni acik degil
- `B-65`: KPI kartlari icin yinelenen hardcoded durum suruyor
- `B-36`: `LocationsPage` ErrorBoundary/failure isolation tam degil
- `B-28`: geocode/lat-lon UX henuz manuel koordinat merkezli
- `B-09`: ORS env key davranisi tutarli degil
- `B-10`: route cache yeni kayit insert etmiyor
- `B-11`: route analysis source precedence net degil
- `B-12`: validator threshold statik/agresif
- `B-13`: zero-result/upstream handling tam truth-preserving degil
- `B-14`: geocode endpoint yok

### Problem explanation

#### B-27

- Problem:
  - locations KPI kartlari hardcoded
- Production etkisi:
  - sahte operasyonel ozet gosteriyor
- Kok neden:
  - gercek summary contract'i page shell'e bagli degil
- Decision-complete fix:
  - KPI kartlari gercek summary endpoint veya query ile beslenecek
- Tests:
  - locations page integration testleri

#### B-39

- Problem:
  - route analysis gorseli yalniz kaba breakdown sunuyor
- Production etkisi:
  - karar icin gereken detayli dagilim gorunmuyor
- Kok neden:
  - payload ve gorsellestirme kisitli
- Decision-complete fix:
  - detayli yol tipi ve egim breakdown'u source-backed sekilde sunulacak
- Tests:
  - analysis modal testleri

#### B-61

- Problem:
  - canli/ag dili veri tabanli degil
- Production etkisi:
  - gercekte olmayan live capability hissi veriyor
- Kok neden:
  - placeholder copy tamamen temizlenmemis
- Decision-complete fix:
  - live/sebeke dili kaldirilacak; yerine gercek analysis durumu gosterilecek
- Tests:
  - locations copy truthfulness tests

#### B-62

- Problem:
  - B-39 ile ayni breakdown acigi ikinci yuzde suruyor
- Production etkisi:
  - modal, kart ve liste ayni detaylari gostermiyor
- Kok neden:
  - breakdown contract'i tekil degil
- Decision-complete fix:
  - tek route-analysis presenter ile tum locations surface hizalanacak
- Tests:
  - route analysis parity tests

#### B-63

- Problem:
  - analiz, simulasyon ve 403 anlatimi net degil
- Production etkisi:
  - erisim hatasi ile veri eksikligi ayirt edilemiyor
- Kok neden:
  - error state taxonomy ve copy standardi belirsiz
- Decision-complete fix:
  - 403, unavailable, no-data ve no-analysis state'leri ayri copy ve action ile
    tanimlanacak
- Tests:
  - 403 UX testleri

#### B-65

- Problem:
  - KPI kartlarinin hardcoded olmasi yinelenen acik olarak suruyor
- Production etkisi:
  - B-27 ile ayni truthfulness sorunu devam ediyor
- Kok neden:
  - page-level summary abstraction eksik
- Decision-complete fix:
  - KPI surface tek gercek summary kaynagina baglanacak
- Tests:
  - KPI source-backed tests

#### B-36

- Problem:
  - `LocationsPage` hatayi izole etmiyor
- Production etkisi:
  - tek child hata tum sayfa deneyimini bozabiliyor
- Kok neden:
  - page shell failure isolation eksik
- Decision-complete fix:
  - `LocationsPage` icin page-level ErrorBoundary eklenecek
- Tests:
  - `LocationsPage ErrorBoundary` acceptance

#### B-28

- Problem:
  - kullanici manuel lat/lon giriyor
- Production etkisi:
  - veri kalitesi ve UX zayif
- Kok neden:
  - geocode endpoint ve assisted selection eksik
- Decision-complete fix:
  - geocode endpoint, assisted search ve coordinate autofill akisi eklenecek
- Tests:
  - geocode integration tests

#### B-09

- Problem:
  - ORS env key davranisi client ve service tarafinda tutarli degil
- Production etkisi:
  - routing provider davranisi ortama gore sapabiliyor
- Kok neden:
  - legacy fallback ve yeni key mantigi ayni anda yasiyor
- Decision-complete fix:
  - tek canonical env key ve provider resolution standardi tanimlanacak
- Tests:
  - routing env resolution tests

#### B-10

- Problem:
  - route cache yeni kayit insert etmiyor
- Production etkisi:
  - cache sessiz kayip uretir
- Kok neden:
  - update-centric save path
- Decision-complete fix:
  - upsert davranisi kurulacak
- Tests:
  - route cache integration tests

#### B-11

- Problem:
  - route analysis source precedence net degil
- Production etkisi:
  - UI ve backend farkli source gercegi okuyabilir
- Kok neden:
  - precedence contract yazili ve testli degil
- Decision-complete fix:
  - canonical source precedence tanimlanacak
- Tests:
  - analysis precedence tests

#### B-12

- Problem:
  - route validator statik/agresif esikler kullaniyor
- Production etkisi:
  - yanlis reject/accept riski
- Kok neden:
  - esikler data-driven degil
- Decision-complete fix:
  - calibrated/dynamic threshold strategy uygulanacak
- Tests:
  - route validation threshold tests

#### B-13

- Problem:
  - zero-result / upstream failure handling tam acik degil
- Production etkisi:
  - yaniltici analysis ciktilari olusabilir
- Kok neden:
  - fallback contract'i netlestirilmemis
- Decision-complete fix:
  - explicit zero-result fallback ve unavailable contract'i yazilacak
- Tests:
  - upstream zero-result tests

#### B-14

- Problem:
  - geocode endpoint yok
- Production etkisi:
  - adres/tesis bazli lokasyon akisi yarim
- Kok neden:
  - assisted geocode tamamlanmamis
- Decision-complete fix:
  - geocode endpoint ve ilgili UI akisi tamamlanacak
- Tests:
  - geocode API tests

### Production truth cleanup in this phase

- locations hardcoded KPI'lari kaldirilacak
- fake-live / simulated analysis copy tamamen temizlenecek
- 403, no-data ve unavailable state'ler birbirine karismadan gercek contract ile
  gosterilecek
- route cache / geocode / threshold fallback'leri truth-preserving olacak

### English-only conversion in this phase

- locations technical components, hooks, route/cache/geocode support files ve tests
  English-only olacak
- UI Turkish yalniz resources uzerinden gelecek

### Implementation steps

1. locations KPI kartlarini gercek summary service'e bagla
2. breakdown contract'ini backend + UI birlikte genislet
3. 403 ve analysis naming UX taxonomisini tekillestir
4. `LocationsPage` ErrorBoundary/failure isolation ekle
5. geocode, route cache, ORS env, threshold ve zero-result support aciklarini kapat

### Files/subsystems affected

- `LocationsPage`
- location list / analysis modal / route analysis card
- route service / route cache / geocode support

### Tests

- locations page integration testleri
- analysis modal testleri
- 403 UX testleri
- `LocationsPage ErrorBoundary` acceptance
- route/geocode/cache smoke

### Exit gate

- `B-27`, `B-39`, `B-61`, `B-62`, `B-63`, `B-65`, `B-36`, `B-28`, `B-09`,
  `B-10`, `B-11`, `B-12`, `B-13`, `B-14` kapanmis olacak
- hardcoded KPI kalmayacak
- fake-live analysis copy kalmayacak
- touched technical files English-only olacak
- tek kirmizi test kalmayacak

## Phase 15 - Admin Sayfalari Veri Dogrulugu

### Goal

- admin yuzeyini hardcoded/no-op/placeholder durumdan cikarip gercek veri, React
  Query ve schema-backed contract standardina tasimak

### Included B-codes

- `B-25`, `B-26`, `B-29`, `B-37`, `B-41`, `B-52`, `B-53`, `B-54`, `B-55`,
  `B-56`, `B-57`, `B-67`, `B-97`, `B-98`, `B-119`, `B-121`

### Current repo state

- `B-25`: `OverviewPage` kart degerleri hardcoded
- `B-26`: `MLYonetimPage` egitimi sabit arac `1` icin tetikliyor
- `B-29`: admin health/bakim/bildirim/veri yonetimi sayfalari hala manual loading
  pattern kullaniyor
- `B-37`: `KullanicilarPage` ust aksiyonlarindan en az biri no-op
- `B-41`: bakim ve bildirimler alt yuzeyi manual fetch ve yari bitmis akislara
  dayaniyor
- `B-52`: kullanici yonetimi butonlari islevsiz ve build-riskli UI borcu tasiyor
- `B-53`: bildirim kurali olusturma akisi tamamlanmamis
- `B-54`: bakim uyarilari plaka yerine ham `Arac #id` formatina dusuyor
- `B-55`: bildirim hedef/rol goruntulemesi ham rol kimligi basiyor
- `B-56`: konfigurasyon boolean alanlari tip-guvensiz text input ile render ediliyor
- `B-57`: admin sayfalari genel olarak React Query standardinda degil
- `B-67`: `SistemSaglikPage` de manual loading pattern devam ediyor
- `B-97`: admin health reset/backup endpointleri placeholder/no-op
- `B-98`: `health_service` backup/circuit-breaker alanlarini mock/hardcoded uretiyor
- `B-119`: `admin_roles.py` `yetkiler` icin schema validation uygulamiyor
- `B-121`: `FleetInsights` trend ve verimlilik yuzdeleri hardcoded

### Problem explanation

#### B-25

- Problem:
  - overview kartlari statik degerlerle render ediliyor
- Production etkisi:
  - admin kullaniciya uydurma operasyon ozeti gosteriyor
- Kok neden:
  - overview summary gercek service/query contract'ina baglanmamis
- Decision-complete fix:
  - overview kartlari gercek backend summary query'sine baglanacak
- Tests:
  - admin overview query-backed render testleri

#### B-26

- Problem:
  - ML management butonu secili arac yerine sabit arac `1` uzerinden calisiyor
- Production etkisi:
  - admin UI gercek secimi yansitmiyor
- Kok neden:
  - selection state mutation payload'ina bagli degil
- Decision-complete fix:
  - egitim aksiyonu secili arac veya secili scope ile calisacak
- Tests:
  - ML management action selection tests

#### B-29

- Problem:
  - admin sayfalarinda `useEffect + setLoading` paternleri yaygin
- Production etkisi:
  - stale cache, duplicate fetch ve zor invalidation davranisi uretiyor
- Kok neden:
  - sayfa katmani React Query standardina gecmemis
- Decision-complete fix:
  - page-level data akislari React Query query/mutation modeline tasinacak
- Tests:
  - admin page loading-state integration tests

#### B-37

- Problem:
  - `Yeni Kullanici` butonu islevsiz
- Production etkisi:
  - admin sayfasi bitmis gorunse de kritik aksiyon calismiyor
- Kok neden:
  - create/edit akisi ya baglanmamis ya da yari birakilmis
- Decision-complete fix:
  - create/edit modal ve mutation akisi tam baglanacak
- Tests:
  - users page action interaction tests

#### B-41

- Problem:
  - bakim ve bildirimler sayfalari manual fetch ve yari bitmis aksiyonlara dayaniyor
- Production etkisi:
  - admin akislarinda refresh/loading tutarsiz
- Kok neden:
  - sayfa veri katmani standardize degil
- Decision-complete fix:
  - maintenance/notifications sayfalari query hooks altinda tekillestirilecek
- Tests:
  - maintenance/notifications page query smoke

#### B-52

- Problem:
  - kullanici yonetimi butonlari eksik/yarim
- Production etkisi:
  - admin yuzeyi gercek user lifecycle yonetemiyor
- Kok neden:
  - button wiring ve modal orchestration tam degil
- Decision-complete fix:
  - create, edit, enable/disable ve role assignment akislari eksiksiz baglanacak
- Tests:
  - users page component interaction suite

#### B-53

- Problem:
  - `Yeni Kural` butonu islevsiz
- Production etkisi:
  - bildirim kurali olusturma akisina girilemiyor
- Kok neden:
  - notification rule create/edit workflow eksik
- Decision-complete fix:
  - notification rule CRUD akisi query/mutation standardina alinacak
- Tests:
  - notification rules workflow tests

#### B-54

- Problem:
  - bakim uyarisi plaka yerine `Arac #id` gosteriyor
- Production etkisi:
  - admin karar vermek icin anlamsiz kimlik goruyor
- Kok neden:
  - display contract vehicle label resolver kullanmiyor
- Decision-complete fix:
  - plaka-first display standardi uygulanacak
- Tests:
  - maintenance alert rendering tests

#### B-55

- Problem:
  - bildirim hedefleri rol adi yerine rol ID basiyor
- Production etkisi:
  - teknik veri kullanici UI'sine siziyor
- Kok neden:
  - role label mapping eksik
- Decision-complete fix:
  - role metadata query veya enum mapping ile label gosterilecek
- Tests:
  - notification role-label tests

#### B-56

- Problem:
  - boolean config alanlari text input ile render ediliyor
- Production etkisi:
  - type-guvensiz ve hataya acik admin formu olusuyor
- Kok neden:
  - field metadata renderer'a yansimiyor
- Decision-complete fix:
  - type-aware config form renderer kurulacak
- Tests:
  - configuration form type-render tests

#### B-57

- Problem:
  - admin sayfalarinin genelinde React Query standardi yok
- Production etkisi:
  - B-29/B-41/B-67 gibi aciklar tekrarliyor
- Kok neden:
  - ortak admin data access standardi kurulmamis
- Decision-complete fix:
  - admin pages icin ortak query key, stale time, invalidation ve mutation standardi
    kurulacak
- Tests:
  - admin page query contract tests

#### B-67

- Problem:
  - `SistemSaglikPage` manual loading pattern kullaniyor
- Production etkisi:
  - diger admin sayfalariyla ayni veri standardini bozuyor
- Kok neden:
  - page-specific legacy implementation
- Decision-complete fix:
  - system health page query-backed hale getirilecek
- Tests:
  - system health page query tests

#### B-97

- Problem:
  - admin health reset/backup endpointleri placeholder/no-op
- Production etkisi:
  - operasyonel aksiyon varmis gibi gorunuyor ama gercek degil
- Kok neden:
  - endpoint/service orkestrasiyonu gercek is akisi yerine stub ile kalmis
- Decision-complete fix:
  - gercek operation orchestration kurulacak veya explicit non-success contract'i
    tanimlanacak
- Tests:
  - admin health action API tests

#### B-98

- Problem:
  - health service backup/circuit-breaker verilerini hardcoded uretiyor
- Production etkisi:
  - admin health ekrani sahte operasyon durumu gosteriyor
- Kok neden:
  - service source-backed metric yerine mock veri tasiyor
- Decision-complete fix:
  - gercek kaynaklardan okumak veya unavailable state donmek
- Tests:
  - health service truthfulness tests

#### B-119

- Problem:
  - `admin_roles.py` permission payload'i schema validation olmadan kabul ediyor
- Production etkisi:
  - bozuk permission konfigurasyonu sisteme girebilir
- Kok neden:
  - strict request schema yok
- Decision-complete fix:
  - request schema, enum ve permission validation eklenecek
- Tests:
  - admin roles validation API tests

#### B-121

- Problem:
  - `FleetInsights` trend ve verimlilik yuzdeleri hardcoded
- Production etkisi:
  - dashboard dogrulugu bozuluyor
- Kok neden:
  - summary/trend service'e bagli degil
- Decision-complete fix:
  - fleet insights gercek query'ye baglanacak; veri yoksa unavailable state donecek
- Tests:
  - fleet insights truthfulness component tests

### Production truth cleanup in this phase

- admin overview ve fleet insights hardcoded kartlari kaldirilacak
- placeholder/no-op health, backup, reset, bildirim-kurali ve kullanici aksiyonlari
  production contract'ina alinacak
- gercek veri yoksa admin yuzeyi bos ama durust state gosterecek

### English-only conversion in this phase

- admin technical pages, hooks, services, query keys, DTO names ve test
  descriptions English-only olacak
- UI Turkish yalniz resource katmaninda kalacak
- backend admin validation/health/roles/notifications technical strings English
  olacak

### Implementation steps

1. admin sayfalari icin aktif data flow matrisi cikar
2. manual fetch sayfalarini React Query query/mutation standardina tasi
3. hardcoded kart ve placeholder action yuzeylerini gercek service contract'lariyla
   bagla
4. admin health endpoint/service zincirini no-op olmaktan cikar
5. role/permission validation ve config form type-safety aciklarini kapat
6. touched admin/fleet technical files icindeki Turkish technical text'i temizle

### Files/subsystems affected

- `frontend/src/pages/admin/*`
- `frontend/src/components/fleet/FleetInsights.tsx`
- `app/api/v1/endpoints/admin_*.py`
- `app/core/services/health_service.py`
- `app/api/v1/endpoints/admin_roles.py`

### Tests

- admin page component testleri
- page-level integration smoke
- admin health action API testleri
- admin roles validation API testleri
- fleet insights truthfulness tests
- `npm --prefix frontend run build`

### Exit gate

- `B-25`, `B-26`, `B-29`, `B-37`, `B-41`, `B-52`, `B-53`, `B-54`, `B-55`,
  `B-56`, `B-57`, `B-67`, `B-97`, `B-98`, `B-119`, `B-121` kapanmis olacak
- admin ve fleet insight yuzeyinde hardcoded trend/KPI kalmayacak
- placeholder/no-op admin action kalmayacak
- touched technical files English-only olacak
- tek kirmizi test kalmayacak

## Phase 16 - Shared UI, Fuel, Driver, Notification

### Goal

- shared UI token/class borclarini, fuel/driver truthfulness problemlerini,
  notification fetch/WS davranisini ve deterministic UI standardini kapatmak

### Included B-codes

- `B-07`, `B-08`, `B-50`, `B-51`, `B-58`, `B-68`, `B-69`, `B-90`, `B-100`,
  `B-101`, `B-105`, `B-113`

### Current repo state

- `B-07`: bazi eski class token kalintilari duruyor
- `B-08`: `custom-scrollbar` ve `animate-stagger-fade` gibi tanimlar eksik
- `B-50`: driver grid/table rating hesaplari `DriverCard` ile tutarsiz
- `B-51`: suruculer icin delete modal standardi eksik
- `B-58`: notification dropdown manual fetch/useEffect kullaniyor
- `B-68`: fuel maliyet karti yesil tonlu anlamsal hata tasiyor
- `B-69`: toast duration merkezi tanimli degil
- `B-90`: `VehicleDetailModal` manual loading kullaniyor
- `B-100`: `TrailerModal` Zod/RHF standardinda degil
- `B-101`: driver rating sunumu grid/table tarafinda yine tutarsiz
- `B-105`: websocket URL localhost icin `:8000` hardcoded
- `B-113`: production path'te debug log kalintilari var

### Problem explanation

#### B-07

- Problem:
  - token/class migration'i tam tamamlanmamis
- Production etkisi:
  - UI contract drift ve styling regression riski suruyor
- Kok neden:
  - eski utility isimleri tam temizlenmemis
- Decision-complete fix:
  - shared token cleanup yapilacak; yalniz tanimli utility/class'lar kalacak
- Tests:
  - shared UI class/token scan

#### B-08

- Problem:
  - kullanilan bazi animasyon/scrollbar utility'leri tanimli degil
- Production etkisi:
  - silent styling failure
- Kok neden:
  - Tailwind/config ve component kullanimi ayrismis
- Decision-complete fix:
  - eksik tanimlar eklenecek veya kullanim kaldirilacak
- Tests:
  - shared UI style contract tests

#### B-50

- Problem:
  - surucu puani farkli bilesenlerde farkli hesaplanıyor
- Production etkisi:
  - kullanici ayni surucu icin farkli puan goruyor
- Kok neden:
  - ortak rating presenter yok
- Decision-complete fix:
  - tek rating helper/presenter kurulacak
- Tests:
  - driver rating consistency tests

#### B-51

- Problem:
  - surucu silme akisi modal standardina alinmamis
- Production etkisi:
  - delete UX araclarla tutarsiz
- Kok neden:
  - shared destructive modal surucu moduluyle baglanmamis
- Decision-complete fix:
  - driver delete icin reusable confirm modal ve mutation flow kurulacak
- Tests:
  - driver delete modal interaction tests

#### B-58

- Problem:
  - notification dropdown veri akisi manual fetch ile yurutuluyor
- Production etkisi:
  - cache/refetch/WS koordinasyonu bozuk
- Kok neden:
  - query standardi notification surface'e yayilmamis
- Decision-complete fix:
  - notification data flow query cache + websocket invalidation standardina alinacak
- Tests:
  - notification context tests

#### B-68

- Problem:
  - fuel maliyet karti yesil guven tonu ile anlamsal hata tasiyor
- Production etkisi:
  - maliyet bilgisi dusus/yukselis anlamindan bagimsiz guvenli gibi algilaniyor
- Kok neden:
  - semantic color policy uygulanmamis
- Decision-complete fix:
  - neutral/warning/success ayrimi semantic contract'a gore duzeltilecek
- Tests:
  - fuel semantic color tests

#### B-69

- Problem:
  - toast duration politikalari merkezi degil
- Production etkisi:
  - hata ve bilgi toasts rastgele surelerle gorunuyor
- Kok neden:
  - centralized toaster config yok
- Decision-complete fix:
  - toast turune gore merkezi sure politikasi tanimlanacak
- Tests:
  - toaster duration tests

#### B-90

- Problem:
  - `VehicleDetailModal` React Query standardi disinda manuel yukleme yapiyor
- Production etkisi:
  - stale cache/refetch davranisi uyumsuz
- Kok neden:
  - legacy modal data flow query katmanina alinmamis
- Decision-complete fix:
  - modal query key, loading, error ve refetch davranisi query-backed olacak
- Tests:
  - vehicle detail modal query tests

#### B-100

- Problem:
  - `TrailerModal` ortak form validation standardindan kopuk
- Production etkisi:
  - form validasyonu ve error handling zayif
- Kok neden:
  - Zod/RHF migration uygulanmamis
- Decision-complete fix:
  - trailer formu Zod + RHF standardina tasinacak
- Tests:
  - trailer modal validation tests

#### B-101

- Problem:
  - `DriverGrid` ve `DriverTable` rating sunumu ayni hesaplayiciyi kullanmiyor
- Production etkisi:
  - driver rating dogrulugu bozuluyor
- Kok neden:
  - B-50'nin ikinci yuzeyi
- Decision-complete fix:
  - grid/table/card ayni presenter ile beslenecek
- Tests:
  - driver grid/table parity tests

#### B-105

- Problem:
  - localhost websocket URL'i env yerine sabit `:8000` kullaniyor
- Production etkisi:
  - local/staging baglanti davranisi environment'la uyumsuz
- Kok neden:
  - special-case config yolu kalmis
- Decision-complete fix:
  - websocket base URL tek config kaynagindan turetilecek
- Tests:
  - websocket config resolution tests

#### B-113

- Problem:
  - uretimde kalmis debug log kalintilari var
- Production etkisi:
  - log gürultusu ve gereksiz teknik sizma riski
- Kok neden:
  - debug-only path'ler production path'ten tamamen ayrilmamis
- Decision-complete fix:
  - debug satirlari silinecek veya controlled debug flag altina alinacak
- Tests:
  - debug log guard scan

### Production truth cleanup in this phase

- fuel kartlarinda ve driver ekranlarinda anlamsal olarak sahte guven ureten renk,
  rating ve delete UX tutarsizliklari kaldirilacak
- notification akisi manual fetch yerine gercek cache + websocket standardina
  alinacak
- prod'a ait olmayan debug sinyalleri ve token/class kalintilari temizlenecek

### English-only conversion in this phase

- shared UI, fuel, driver, trailer, notification, websocket config ve debug/log
  technical strings English-only olacak
- UI Turkish yalniz resource katmanindan gelecek

### Implementation steps

1. shared token/class envanteri cikar ve tanimsiz utility kullanimlarini kapat
2. driver rating hesaplarini tek helper'a indir
3. driver delete, trailer form ve vehicle detail modal yuzeylerini ortak standarda
   tasi
4. notification dropdown/context akisini query + websocket invalidation modeline al
5. websocket base URL cozumlemesini env-first hale getir
6. touched technical files icindeki Turkish technical text ve debug kalintisini temizle

### Files/subsystems affected

- `frontend/src/components/ui/*`
- `frontend/src/components/fuel/*`
- `frontend/src/components/drivers/*`
- `frontend/src/components/trailers/*`
- `frontend/src/components/vehicles/VehicleDetailModal.tsx`
- `frontend/src/context/NotificationContext.tsx`
- `frontend/src/components/layout/NotificationDropdown.tsx`
- websocket/config helpers
- backend debug-log kalan servisler

### Tests

- shared component tests
- notification context tests
- fuel/driver page smoke
- trailer modal validation tests
- driver rating parity tests
- websocket config tests
- `npm --prefix frontend run build`

### Exit gate

- `B-07`, `B-08`, `B-50`, `B-51`, `B-58`, `B-68`, `B-69`, `B-90`, `B-100`,
  `B-101`, `B-105`, `B-113` kapanmis olacak
- shared UI token/class drift kalmayacak
- manual notification fetch standardi kalmayacak
- touched technical files English-only olacak
- tek kirmizi test kalmayacak

## Phase 17 - ML, Orphan Kod Karari ve Backend Veri Modeli Kapanisi

### Goal

- backend truthfulness, ML/prediction/import/report correctness ve orphan production
  code temizligini clean-rebuild hazir seviyesine getirmek

### Included B-codes

- `B-LGB-01`, `B-KAL-01`, `B-16`, `B-17`, `B-18`, `B-21`, `B-22`, `B-23`,
  `B-94`, `B-99`, `B-ML-01`, `B-ML-02`, `B-ML-03`, `B-ML-04`, `B-ML-06`,
  `B-ML-07`, `B-SW-01`, `B-SW-02`, `B-PS-01`, `B-PS-02`, `B-PS-03`,
  `B-PS-05`, `B-RS-02`, `B-RS-04`, `B-RS-06`, `B-DS-01`, `B-SIS-01`

### Current repo state

- `B-LGB-01`: standalone LightGBM predictor production import graph'inda aktif
  gorunmuyor; orphan technical debt olarak duruyor
- `B-KAL-01`: `kalman_estimator.py` production yolunda aktif gorunmuyor; orphan
  technical debt
- `B-16` ve `B-99`: training/report zincirlerinde string join temelli sefer secimi
  hala var
- `B-17`: `rota_detay` yapisi birden fazla farkli varsayimla okunuyor
- `B-18` ve `B-SW-01`: sefer write prediction cagrisi route metrics tasimiyor
- `B-21`: model predict lock'u erken birakiyor
- `B-22`: mismatch durumunda physics-only fallback yok
- `B-23`: yas/mevsim faktorleri cift sayilma riski tasiyor
- `B-94`: repo count/summary akislarinda soft-delete filtresi tutarsiz
- `B-ML-01`: `train_general_model` string join kullaniyor
- `B-ML-02`: `train_for_vehicle` mevsimsellikte `date.today()` kullaniyor
- `B-ML-03`: `predict_consumption` tanimsiz `self.dorse_repo` bagimliligina
  dayanabiliyor
- `B-ML-04`: genel model metrik map'i kismen yanlis
- `B-ML-06`: physics baseline `flat_distance_km` gecirmiyor
- `B-ML-07`: physics predictor route detail'i kullanmiyor
- `B-SW-02`: `prediction_liters` -> `tahmini_tuketim` birim hatasi suruyor
- `B-PS-01`: driver influence cift sayilabiliyor
- `B-PS-02`: `route_analysis['ratios']` contract'i uretici ve tuketici arasinda
  uyumsuz
- `B-PS-03`: confidence fallback'i yapay `1.0`
- `B-PS-05`: XGBoost result key okumalari yanlis
- `B-RS-02`: route cache modeli detay alanlarini tasimiyor
- `B-RS-04`: offline fallback tum mesafeyi sehir ici sayiyor
- `B-RS-06`: `performance_score` hardcoded `85.0`
- `B-DS-01`: dashboard service var olmayan report metodlarina baglaniyor
- `B-SIS-01`: import akisi `sofor_id/guzergah_id` bos birakabiliyor

### Problem explanation

#### B-LGB-01

- Problem:
  - production'da kullanilmayan LightGBM predictor runtime tree'de duruyor
- Production etkisi:
  - import graph ve ownership karmasasi yaratir
- Kok neden:
  - experimental/prod ayrimi fiziksel olarak netlestirilmemis
- Decision-complete fix:
  - experimental alana tasinacak ya da silinecek; prod import graph'tan tamamen
    cikarilacak
- Tests:
  - prod import graph smoke

#### B-KAL-01

- Problem:
  - production'da kullanilmayan Kalman estimator runtime tree'de duruyor
- Production etkisi:
  - orphan teknik borc ve yanlis import riski
- Kok neden:
  - experimental/prod ayrimi net degil
- Decision-complete fix:
  - experimental namespace'e tasinacak ya da kaldirilacak
- Tests:
  - dead-code import scan

#### B-16

- Problem:
  - training dataset secimi string join ile yurutuluyor
- Production etkisi:
  - yanlis seferler modele girebilir
- Kok neden:
  - canonical relational training selection contract'i yok
- Decision-complete fix:
  - foreign-key/path temelli training selection kurulacak
- Tests:
  - training dataset selection tests

#### B-17

- Problem:
  - `rota_detay` farkli katmanlarda farkli shape varsayimlariyla okunuyor
- Production etkisi:
  - route based tahmin ve gorsellestirme bozulur
- Kok neden:
  - strict route-detail schema yok
- Decision-complete fix:
  - route detail icin tek schema + adapter katmani kurulacak
- Tests:
  - route-detail contract tests

#### B-18

- Problem:
  - prediction cagrisina route metric alanlari gitmiyor
- Production etkisi:
  - route-tabanli tahmin gercekte rotayi kullanmiyor
- Kok neden:
  - sefer write -> prediction DTO eksik
- Decision-complete fix:
  - mesafe, egim, route-analysis oranlari ve gereken route metadata prediction
    input'unda tasinacak
- Tests:
  - sefer write prediction input tests

#### B-21

- Problem:
  - training/predict lock stratejisi predict kritik bolgesini tam korumuyor
- Production etkisi:
  - race condition riski
- Kok neden:
  - lock scope dar
- Decision-complete fix:
  - concurrency contract safe lock stratejisine cekilecek
- Tests:
  - predictor concurrency tests

#### B-22

- Problem:
  - feature mismatch physics-only fallback yerine sessiz pad/truncate ile geciliyor
- Production etkisi:
  - yanlis tahmin sessizce yesil kalabilir
- Kok neden:
  - guvenli fallback contract'i yok
- Decision-complete fix:
  - mismatch halinde explicit physics-only fallback veya non-success donulecek
- Tests:
  - feature mismatch fallback tests

#### B-23

- Problem:
  - yas/mevsim faktorleri iki kez etki ediyor
- Production etkisi:
  - tahmin kalibrasyonu bozulur
- Kok neden:
  - baseline ile model feature katkisi ayrismamis
- Decision-complete fix:
  - baseline ve feature contribution net ayrilacak
- Tests:
  - factor double-count tests

#### B-94

- Problem:
  - count/summary akislarinda soft-delete filtresi tutarli degil
- Production etkisi:
  - dashboard/reporting sayimlari gercegi bozabilir
- Kok neden:
  - canonical repository count contract'i eksik
- Decision-complete fix:
  - count ve summary repo metodlari `is_deleted = false` standardina cekilecek
- Tests:
  - repository count soft-delete tests

#### B-99

- Problem:
  - B-16'nin ayni string join sorunu reporting/training tarafinda da var
- Production etkisi:
  - rapor ve egitim farkli kaynaktan yanlis veri toplayabilir
- Kok neden:
  - kok sorun tum dataset selection zincirine yayilmis
- Decision-complete fix:
  - reporting/training source selection da key-based olacak
- Tests:
  - report training source-selection tests

#### B-ML-01

- Problem:
  - `train_general_model` string join ile veri topluyor
- Production etkisi:
  - genel model dataset'i guvenilmez
- Kok neden:
  - relational query yerine text match kullaniliyor
- Decision-complete fix:
  - canonical query'ye gecilecek
- Tests:
  - general model query tests

#### B-ML-02

- Problem:
  - tarihsel veriye bugunun mevsim faktoru uygulaniyor
- Production etkisi:
  - tarihsel mevsimsellik bozuluyor
- Kok neden:
  - row-level tarih kullanilmiyor
- Decision-complete fix:
  - her kaydin kendi tarihiyle seasonality hesaplanacak
- Tests:
  - historical seasonality tests

#### B-ML-03

- Problem:
  - predictor tanimsiz repo property'ye dayanir
- Production etkisi:
  - runtime `AttributeError` riski
- Kok neden:
  - dependency wiring explicit degil
- Decision-complete fix:
  - init contract ve dependency injection netlestirilecek
- Tests:
  - predictor dependency wiring tests

#### B-ML-04

- Problem:
  - model metrics mapping kismen yanlis
- Production etkisi:
  - raporlanan model kalitesi gercegi yansitmayabilir
- Kok neden:
  - metric persistence/readback schema'si net degil
- Decision-complete fix:
  - tek metrics schema ve parser kullanilacak
- Tests:
  - model metrics mapping tests

#### B-ML-06

- Problem:
  - physics baseline `flat_distance_km` kullanmiyor
- Production etkisi:
  - route geometry tahmine eksik yansiyor
- Kok neden:
  - predictor input contract eksik
- Decision-complete fix:
  - physics predictor tum route metric alanlarini kullanacak
- Tests:
  - physics predictor route-metric tests

#### B-ML-07

- Problem:
  - physics predictor route detail breakdown'u kullanmiyor
- Production etkisi:
  - 60/20/20 kaba varsayimla calisiyor
- Kok neden:
  - detay breakdown entegrasyonu yok
- Decision-complete fix:
  - gercek route breakdown oranlari baseline'a dahil edilecek
- Tests:
  - route breakdown physics tests

#### B-SW-01

- Problem:
  - `route_analysis` detayi write-service prediction akisina gitmiyor
- Production etkisi:
  - sefer olusurken tahmin route'tan kopuk kaliyir
- Kok neden:
  - write-service payload mapper eksik
- Decision-complete fix:
  - write-service -> prediction service arasi tam route-analysis payload contract'i
    kurulacak
- Tests:
  - write-service prediction contract tests

#### B-SW-02

- Problem:
  - litres/consumption unit map'i yanlis alana yaziliyor
- Production etkisi:
  - UI ve analiz katmanina yanlis birim siziyor
- Kok neden:
  - canonical output unit contract'i yok
- Decision-complete fix:
  - prediction output units field seviyesinde tek standarda cekilecek
- Tests:
  - prediction unit mapping tests

#### B-PS-01

- Problem:
  - driver influence iki kez uygulanabiliyor
- Production etkisi:
  - tahmin sistematik olarak sapabilir
- Kok neden:
  - physics ve ensemble katkilari ayrismamis
- Decision-complete fix:
  - driver factor tek hesap katmaninda uygulanacak
- Tests:
  - driver influence double-count tests

#### B-PS-02

- Problem:
  - `ratios` key sozlesmesi producer/consumer arasinda bozuk
- Production etkisi:
  - route-based predictor farkli schema bekliyor
- Kok neden:
  - versioned strict route-analysis ratio schema yok
- Decision-complete fix:
  - ratio schema strict ve versioned hale getirilecek
- Tests:
  - ratio contract tests

#### B-PS-03

- Problem:
  - confidence yoksa servis yapay `1.0` kullaniyor
- Production etkisi:
  - belirsizlik sahte sekilde yesil gosteriliyor
- Kok neden:
  - unknown confidence state tanimlanmamis
- Decision-complete fix:
  - explicit unknown/unavailable confidence contract'i donulecek
- Tests:
  - confidence absence tests

#### B-PS-05

- Problem:
  - XGBoost result key'leri yanlis okunuyor
- Production etkisi:
  - egitim metrikleri raporu bozuluyor
- Kok neden:
  - train result schema tekil degil
- Decision-complete fix:
  - train result key set'i tek standarda alinacak
- Tests:
  - xgboost result parsing tests

#### B-RS-02

- Problem:
  - route cache modeli detay alanlarini tasimiyor
- Production etkisi:
  - cache yazimi sessiz detay kaybi uretir
- Kok neden:
  - schema eksik
- Decision-complete fix:
  - route cache schema/offline storage genisletilecek
- Tests:
  - route cache persistence tests

#### B-RS-04

- Problem:
  - offline fallback tum mesafeyi sehir ici kabul ediyor
- Production etkisi:
  - route breakdown gercegi bozuyor
- Kok neden:
  - offline fallback source-backed degil
- Decision-complete fix:
  - explicit unknown breakdown veya daha guvenli strategy uygulanacak
- Tests:
  - offline route breakdown tests

#### B-RS-06

- Problem:
  - `performance_score` hardcoded `85.0`
- Production etkisi:
  - rapor ve analizde sahte performans skoru uretiliyor
- Kok neden:
  - source-backed formula yok
- Decision-complete fix:
  - gercek formula kurulacak ya da alan kaldirilacak
- Tests:
  - performance score truthfulness tests

#### B-DS-01

- Problem:
  - dashboard service var olmayan report methodlarini cagiriyor
- Production etkisi:
  - dashboard akisinda runtime hata veya bogus fallback riski
- Kok neden:
  - dashboard/report contract hizasi kaymis
- Decision-complete fix:
  - dashboard/report contract yeniden eslenecek
- Tests:
  - dashboard report integration tests

#### B-SIS-01

- Problem:
  - sefer import `sofor_id` ve `guzergah_id` alanlarini garanti etmiyor
- Production etkisi:
  - import edilen seferler yari/dogru olmayan sekilde sisteme girebilir
- Kok neden:
  - resolve/validation pipeline yetersiz
- Decision-complete fix:
  - strict resolution, row-level rejection ve guided fix akisi eklenecek
- Tests:
  - trip import resolution tests

### Production truth cleanup in this phase

- training, prediction, dashboard, route cache ve import zincirinde sahte/uydurma
  basari, yapay confidence, hardcoded score ve sessiz veri kaybi kaldirilacak
- production'da kullanilmayan orphan ML predictor kodu prod import yuzeyinden
  cikarilacak
- fake operational DB mirasina dayali branching yerine clean-rebuild ve insufficient
  data davranisi sabitlenecek

### English-only conversion in this phase

- ML, prediction, route, dashboard, import, repository ve script technical surface
  English-only olacak
- orphan predictor kararinda file/module/symbol naming English-only korunacak
- test descriptions ve training/report script mesajlari English-only olacak

### Implementation steps

1. orphan ML predictor/import graph envanterini cikar ve prod surface'ten temizle
2. route detail, ratio, prediction input/output ve metric schema'larini tek contract'a
   indir
3. training query'lerini string join'den canonical key-based modele tasi
4. predictor concurrency, fallback, confidence ve unit mapping sorunlarini kapat
5. route cache, dashboard/report ve import pipeline truthfulness aciklarini kapat
6. `is_real` mirasi, soft-delete count ve clean-rebuild gereksinimlerini backend veri
   modelinde son kez hizala

### Files/subsystems affected

- `app/core/ml/*`
- `app/services/prediction_service.py`
- `app/core/services/sefer_write_service.py`
- `app/database/repositories/sefer_repo.py`
- `app/database/repositories/analiz_repo.py`
- route service / route cache / dashboard / report / import services
- related training scripts

### Tests

- prod import graph smoke
- updated ML tests
- dead-code import yok kontrolu
- prediction/report/import integration tests
- route cache persistence tests
- dashboard report integration tests
- trip import resolution tests

### Exit gate

- `B-LGB-01`, `B-KAL-01`, `B-16`, `B-17`, `B-18`, `B-21`, `B-22`, `B-23`,
  `B-94`, `B-99`, `B-ML-01`, `B-ML-02`, `B-ML-03`, `B-ML-04`, `B-ML-06`,
  `B-ML-07`, `B-SW-01`, `B-SW-02`, `B-PS-01`, `B-PS-02`, `B-PS-03`,
  `B-PS-05`, `B-RS-02`, `B-RS-04`, `B-RS-06`, `B-DS-01`, `B-SIS-01`
  kapanmis olacak
- prod import graph'ta orphan predictor kalmayacak
- yapay confidence / hardcoded performance score / string-join training kalmayacak
- touched technical files English-only olacak
- tek kirmizi test kalmayacak

## Phase 18 - Dokuman Senkronu, Clean Rebuild ve Son Regresyon

### Goal

- clean rebuild, English schema, non-route execution audit, packaging/secret hygiene
  ve validation senkronunu final production gate'e getirmek

### Included B-codes

- Bu faz yeni unresolved B-code yerine final production closure islerini kapsar.

### Current repo state

- clean rebuild karari kilitli ama tam uygulama ve roundtrip dogrulamasi tamamlanmis
  degil
- mevcut fake operational DB prod'a tasinmayacak karari var; ama final migration ve
  bootstrap acceptance kaydi eksik
- workers/background jobs/startup hooks/WebSocket-SSE/listener surface tam final
  audit kapisina alinmis degil
- compose/Docker/env template tarafinda secret hygiene riski suruyor
- validation raporundaki yanlis toplamlar, tekrarlar ve tarihsel notlar final
  yeniden-uretim ile senkronlanmadi

### Problem explanation

- Clean rebuild ve English schema kapanmadan production-ready denemez.
- Validation raporu yeniden uretilmeden hangi sorunlarin gercekten kapandigi resmi
  olarak kayda gecmez.
- Non-route execution audit kapanmadan worker/websocket/background tarafinda fake,
  mock veya stale prod-disi yol kalma riski surer.

### Decision-complete solution

- English schema ile temiz bootstrap ana yol olacak; fake mevcut DB migrate
  edilmeyecek.
- Migration acceptance tek akista dogrulanacak:
  - upgrade
  - smoke
  - downgrade
  - upgrade
- workers, background jobs, startup/lifespan, WebSocket/SSE, pubsub/listener ve
  deploy entrypoint surface'i tek tek audit edilip prod-disina referans
  birakmayacak.
- Docker, compose, env template ve CI surface'i secret hygiene ve non-prod path
  reachability acisindan kapatilacak.
- validation raporu repoya gore yeniden uretilecek; yanlis `KALDIRILDI/Dogrulandi`
  ve yanlis toplam notlari temizlenecek.

### Production truth cleanup in this phase

- stale non-prod generator, fake bootstrap, seed/demo/synthetic path prod build ve
  runtime reachability icinden cikarilacak
- final remnant scan ile `fake/mock/prototype/simulated/hardcoded/no-op` kalanlari
  sifirlanacak
- fresh DB empty-and-real startup davranisi dogrulanacak; analytics/reporting/ML
  yeterli gercek veri yoksa success donmeyecek

### English-only conversion in this phase

- docs, validation markdown, CI/test/report tooling ve deploy templates technical
  surface'i English-only olacak
- yalniz kullaniciya gorunen UI/resource Turkish kalacak
- rebuild ve migration belgeleri English schema isimleriyle tek kaynak olacak

### Implementation steps

1. clean rebuild bootstrap akisini English schema ile tek accepted path olarak kur
2. migration roundtrip acceptance scriptlerini ekle veya sabitle
3. workers/background/startup/ws/sse/pubsub/listener/deploy entrypoint surface'ini
   final audit listesine gore tara ve kapat
4. Docker, compose, env template ve CI surface'inde secret hygiene ve prod-disina
   referanslari temizle
5. validation raporunu yeniden uret; unresolved/closed ayrimini guncel repo gercegiyle
   senkronla
6. tum cumulative gates'i sirali calistir ve production sign-off checkliste bagla

### Files/subsystems affected

- migrations / alembic / schema docs
- bootstrap scripts / env examples / compose / Docker / CI
- workers / background jobs / startup hooks / listeners / ws-sse surfaces
- validation markdown and production-foundation docs

### Tests

- full backend pytest
- full frontend test/build
- clean-db `upgrade -> smoke -> downgrade -> upgrade`
- lint/typecheck
- validation raporunun yeniden uretilmesi
- remnant marker scan
- Turkish technical text scan
- packaging/deploy smoke

### Exit gate

- clean rebuild ve English schema tek accepted path olacak
- prod-disina reachable seed/demo/fake bootstrap yolu kalmayacak
- technical Turkish scan final touched docs/tooling surface icin sifir olacak
- validation raporu yeniden uretilmis ve repo gercegiyle uyumlu olacak
- full cumulative gates green olacak

## Appendix - Scope Policy for This File

- Bu dosya yalniz repo ustunde bugun de unresolved olarak dogrulanmis maddeleri
  tasir.
- Cozulmus veya yalniz tarihsel/editorial nitelikte kalan maddeler ana fazlardan
  bilincli olarak cikarilmistir.
- Validation raporundaki duplicate referanslar yeni bir is maddesi uretmez; tek kok
  sorun hangi fazda kapanacaksa oraya yazilir.
- Bugun kapali gorunen bir sorun ileride regresyona ugrarsa en yakin ilgili faza
  yeniden dahil edilir.
