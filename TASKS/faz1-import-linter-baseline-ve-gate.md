# FAZ1 (çatı) — import-linter Baseline → Gate

> **DURMA NOKTASI:** Baseline donduruldu (2026-07-17). Gerçek gate'e
> (continue-on-error kaldırma) geçmeden önce AYRI kullanıcı onayı gerekir.

**Amaç:** FAZ0'da rapor-modunda kurulan import-linter'ı gerçek modül
kontratlarıyla donatmak; ilk 11 dalgada taşınmış modüllerin (bkz.
`TASKS/STATUS.md` FAZ1 tablosu) mevcut çapraz-modül/katman ihlallerini
`ignore_imports` ile dondurup yalnız YENİ ihlallere karşı gate açmaya
hazırlamak. **Kod satır kalmaz eski `app.modules.*` dizaynından — asıl
kod 2026-07-12 kararıyla `v2/modules/<ad>/` altında yaşıyor (bkz.
`TASKS/STATUS.md` "KARAR (2026-07-12)" bölümü); bu dosyanın önceki
sürümü hâlâ `app.modules.*` yazıyordu, o TAMAMEN BAYATTI, gerçek
kontrat çalışması `v2.modules.*` üzerinden yapıldı.**

**Giriş kriteri:** FAZ0 çıkışı + en az 1 modül taşınmış — sağlandı (11/17
modül main'de yeşil).
**Bu turun çıkış kriteri:** 11 modülün kontratları rapor-modunda main'de
yeşil (gate DEĞİL). **FAZ1'in TAM çıkış kriteri** (gate + 5 gün yeşil)
kalan 6 dalga (12-17) taşınıp kontratlara eklendikten SONRA ayrı bir
turda ele alınacak.

---

## Gerçek kontrat tasarımı (`.importlinter`, uygulanmış hâli)

`root_packages = app, v2` (tekil `root_package` DEĞİL — import-linter
2.13 kaynağından doğrulandı: `session_options["root_packages"]` bekliyor,
`root_package` yalnız normalize edilip tek-elemanlı listeye çevriliyor).

3 kontrat tipi, 11 modülü kapsıyor (`location, route_simulation,
notification, fleet, fuel, driver, auth_rbac, anomaly, import_excel,
reports, analytics_executive`):

1. **`type = independence`** (`module-cross-domain-infra-independence`) —
   11 modülün `domain`/`infrastructure` katmanları (22 alt-paket)
   birbirinden bağımsız (yalnız public/events üzerinden erişim).
2. **`type = layers`** (`module-internal-layers`) — `containers` = 11
   modül, sıra `api : application : infrastructure : domain` (infra
   domain'i import edebilir, tersi yasak — kullanıcının "domain <-
   infrastructure" diyagramıyla tutarlı; `application`'ın
   `infrastructure`'ı import edebilmesi kodun gerçek deseniyle (use-case
   fonksiyonları constructor-injected repo tipini import ediyor)
   tutarlı, bilinçli seçim).
3. **`type = forbidden`, 11 AYRI kontrat** (`public-surface-only-<mod>`)
   — her modülün `application` katmanı, DİĞER 10 modülün `api`/
   `application`/`domain`/`infrastructure`'ına giremez (yalnız
   `public.py`/`events.py`). **Neden 11 ayrı kontrat, tek birleşik
   değil:** `forbidden` kontratı `source_modules`/`forbidden_modules`
   aynı iki set arasında pairwise kontrol yapıyor; tek birleşik kontratta
   `forbidden_modules` her modülün KENDİ katmanlarını da içerseydi
   (wildcard'la), modülün kendi `application -> domain` erişimi de
   (legal, gerekli) yanlışlıkla yasaklanırdı. 11 ayrı kontrat, her
   modülün forbidden listesinden KENDİSİ hariç tutulmasını garanti eder.

## Adım 0 doğrulaması (root_package/root_packages, VARSAYILMADI)

`import-linter==2.13` kaynağı (`application/use_cases.py:127,210-215`)
gerçek Docker container'da okundu: `root_packages` (çoğul, liste) tek
`root_package`'i normalize ediyor; `.importlinter`'da tekil `app` yerine
`root_packages = app, v2` (çoklu liste) yazıldı — hem eski `app/` hem
yeni `v2/` ağacı tek grafikte analiz ediliyor.

## Adım 1 — gerçek import grafiği (VARSAYILMADI, AST ile çıkarıldı)

`v2/modules/` içinde 59 gerçek çapraz-modül import kenarı bulundu (ast
tabanlı script, dosya+satır numarasıyla). Bunların üstüne, kontratları
gerçek `lint-imports` ile çalıştırınca (490+ "indirect" zincir) ortaya
çıkan **kritik bir mimari gerçek** keşfedildi (aşağıya bkz.).

## KRİTİK BULGU — "even indirectly" ve paylaşılan hub'lar

`independence`/`forbidden` kontrat tipleri **dolaylı (transitive)
zincirleri de kontrol ediyor** (import-linter kaynağı: "even
indirectly"). Bu codebase'de üç payla­şılan legacy hub var
(`app.database.unit_of_work` → `app.database.repositories` aggregator,
`app.core.container` DI container, `app.infrastructure.monitoring.
alarm_router`) + her modülün KENDİ `public.py`'si (kendi domain/
application/infrastructure'ını re-export eden, TAM DA istenen/meşru
giriş noktası) — bunlar neredeyse her modülü her modüle transitif olarak
bağlıyor. İlk deneme 3 temiz kontratla **494 sahte "ihlal" zinciri**
üretti (`Contracts: 0 kept, 14 broken`).

**Kullanıcı kararıyla** ("hub kenarlarını kes") çözüldü: hub'ların KENDİ
çıkış kenarları (`unit_of_work -> repositories`, container'ın ~20
fan-out kenarı, alarm_router'ın notification'a giden kenarı, her
modülün `public.py -> kendi_modülü.**` kenarı) `ignore_imports`'a
eklenerek graf bu noktalarda "kesildi" — çalışma zamanını ETKİLEMEZ,
yalnız linter'ın analiz grafiğini. Gerçek modül-sınırı ihlalleri (~30
kenar) böylece net görünür hâle geldi ve ayrı ayrı donduruldu.

**Wildcard gotcha (VARSAYILMADI, grimp kaynağından doğrulandı):**
`*` yalnız TEK segment eşler (subpackage'sız), `**` alt-paketleri de
kapsar (`grimp.ImportGraph.find_matching_modules` docstring'i). İlk
denemede `X.*` kullanılan kenarların çoğu (2+ segment derinlikte hedefe
sahip olanlar) SESSİZCE eşleşmedi (`unmatched_ignore_imports_alerting =
error` bunu yakaladı → "No matches for ignored import" hatası) — `**`ye
çevrilince düzeldi.

## Adım 2+3 — kontratlar yazıldı, bilinen bulgular donduruldu

Toplam ~50 `ignore_imports` satırı (hub-cut'lar + public.py-cut'lar +
gerçek modül-sınırı ihlalleri), her kontrata uygun şekilde dağıtıldı.
Örnek gerçek (donmuş, düzeltilecek) ihlaller:
- `driver.domain -> analytics_executive.infrastructure` (driver_stats.py,
  evaluation.py — `app.services.prediction_service` üzerinden dolaylı)
- `fuel.domain -> fleet.infrastructure` (consumption_prediction.py)
- `reports.infrastructure.repo_access -> {analytics_executive,driver,
  fleet,fuel}.infrastructure` (kendi mini-hub'ı — 4 modülün repo
  sınıflarını doğrudan import ediyor, public.py atlanıyor)
- `location.application -> route_simulation.{application,domain,
  infrastructure}` (route_simulation'ın henüz `public.py`'si yok —
  `location/CLAUDE.md`'de zaten dokümante edilmiş bilinen borç)
- `import_excel.application -> {fleet,fuel}.schemas` (şema doğrudan
  import, public.py'den re-export edilmiyor)
- `driver.domain <-> driver.infrastructure` (iki yönlü, B.1 ihlali)
- vb. (tam liste `.importlinter` dosyasının kendisinde, yorumlarla)

## Adım 4 — rapor modu doğrulandı (henüz gate DEĞİL)

`.github/workflows/ci.yml:291` zaten `lint-imports --config .importlinter
|| true` (continue-on-error, FAZ0'da kurulmuş) — DEĞİŞTİRİLMEDİ, zaten
istenen "rapor, non-blocking" semantiğinde. Gerçek Docker container'da
hem `--no-cache` hem normal (cache'li) koşumla doğrulandı:

```
Contracts: 13 kept, 1 broken.
```

Kalan 1 "broken" = FAZ0'nın ÖNCEDEN VAR OLAN `report-only` kontratı
(`app.core.services` vs `app.services`, bu görevin kapsamı dışında,
zaten bilinen/dokümante edilmiş drift, dokunulmadı). **Bu görevin
yazdığı 13 kontratın TAMAMI (independence + layers + 11×forbidden) KEPT.**

## Gate'e geçiş kriteri (SONRAKİ tur, bu turda YAPILMADI)

- Kalan 6 dalga (12-17: ai-assistant, prediction-ml, trip, admin-platform,
  shared-kernel, platform-infra) taşınıp kontratlara eklenmeli.
- O modüllerin de kendi bilinen ihlalleri `ignore_imports`'a dondurulmalı.
- `continue-on-error: true` satırı CI workflow'undan kaldırılır.
- 5 ardışık gün main'de bu adım yeşil kalır (flake yok).

## Kabul Kriterleri (BU TUR)

- [x] Adım 0'daki root_package/root_packages sorunu gerçekten çözülmüş
      (import-linter 2.13 kaynağından doğrulandı, varsayılmadı)
- [x] 3 kontrat tipi de `.importlinter`'da, 11 modülü kapsıyor
- [x] Mevcut tüm ihlaller `ignore_imports`'ta, sayı raporlanmış (~50 satır,
      hub-cut + public-cut + gerçek ihlal karışımı, hepsi yorumlu/açık)
- [x] `unmatched_ignore_imports_alerting = error` aktif (tüm 13 kontratta)
- [x] CI'da rapor modu (non-blocking) yeşil — `Contracts: 13 kept, 1
      broken` (1 broken = kapsam dışı, önceden var olan FAZ0 kontratı)
- [x] Gerçek gate'e (continue-on-error kaldırma) geçilmedi — ayrı onay
      bekliyor, bu turun kapsamı dışında.
