# Modül Görevi: shared_kernel (dalga 16/17 — ERİME, yeni modül DEĞİL)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `v2/modules/shared_kernel/CLAUDE.md`'yi Read ile oku (yoksa oluştur).

**Doğa farkı:** Bu bir iş modülü değil — 15 modül taşındıkça geriye kalan, GERÇEKTEN paylaşılan kod. Bu dalga 15 modülün TAMAMI bitince başlar; amaç mevcut 22 dosyayı/~5.223 LOC'u YALNIZ KÜÇÜLTMEK (B.1 kuralı burada "bir dosya = bir görev" değil, "shared_kernel yalnız küçülebilir, büyümez" anlamında kullanılıyor — iki farklı kural aynı isimle anılmasın diye bu ayrım burada açıkça not edildi).

**Giriş kriteri:** admin-platform dalgası (15) tamamlandı — tüm iş modülleri artık `v2/modules/` altında. **Çıkış kriteri:** `v2/modules/shared_kernel/` dizini yalnız GERÇEKTEN ≥2 modül tarafından kullanılan kod içeriyor; cross-module her yeni giriş CODEOWNERS onaylı.

---

## 0. ÖN-DENETİM DÜZELTMELERİ (dalga 16 başlamadan yapılan inceleme, kullanıcı onayıyla)

Bu plan, dalga 15 (admin_platform) bittikten sonra ajan kullanılmadan satır satır incelendi ve gerçek koda karşı doğrulandı (`grep -rln` ile her dosyanın gerçek çağıranları sayıldı). Orijinal taslak 4 yerde önceki 15 dalganın kendi kurduğu yerleşik ilkelerle çelişiyordu — hepsi burada düzeltildi:

1. **Yol kuralı hatası**: taslak `app/shared_kernel/`, `app/modules/<sahip>/` diyordu. Ama `TASKS/STATUS.md`'deki kullanıcı kararı ("İşin sonunda v2 kalacak, v2 dışında bizi bağlayan hiçbir şey olmamalı... tüm 15 modül + shared_kernel + platform-infra v2'ye taşındıktan SONRA app/ dizini TAMAMEN SİLİNİR") ve önceki 15 dalganın hepsinin kullandığı gerçek konvansiyon `v2/modules/<isim>/`. Bu dosyadaki TÜM `app/shared_kernel`/`app/modules/<sahip>` ifadeleri `v2/modules/shared_kernel`/`v2/modules/<isim>` olarak düzeltildi (aşağıda madde 1/3/4).

2. **`core/entities/models.py` (683 satır) için madde 2'nin genel kuralı YANLIŞ granülerlikte**: bu dosya generic paylaşılan kod değil — `database/models.py` ile AYNI karakterde bir dosya: ~9 iş varlığı (entity), her biri TEK bir modüle ait, ama birçoğu başka modüller tarafından da OKUNUYOR (`Sefer` trip+fuel+prediction_ml+import_excel+fleet tarafından import ediliyor — gerçek grep ile doğrulandı). Taslağın "≥2 modül import ediyorsa BURADA KALIR" kuralı harfiyen uygulanırsa bu dosya BÖLÜNMEDEN sonsuza dek shared_kernel'de kalır — tam olarak `database/models.py`'nin eski hâlinin (taşımadan önceki God-file) küçük bir kopyasını yeniden yaratır, 15 dalganın kurduğu "veriyi/tabloyu sahiplenen modüle taşı, kim-en-çok-import-ediyor'a bakma" ilkesini ihlal eder. **Düzeltme**: bu dosya madde 2'nin genel kuralından MUAF tutulup madde 3'ün (database/models.py) kullandığı SAHİPLİK bazlı yaklaşımla bölünecek — aşağıda yeni madde 3b.

3. **Taslakta "sil" seçeneği hiç yok — sadece "kal" veya "taşı"**: gerçek grep sonucu 2 dosyanın (`protocols.py`, `interfaces/repositories.py`) SIFIR prod çağıranı olduğu bulundu (yalnızca kendi test dosyaları onları egzersiz ediyor, gerçek servis sınıflarına karşı değil — o servisler zaten dalga 1-15'te free function'a dissolve edildi). Bunlar taşınacak bir "ev" değil, SİLİNECEK ölü kod. Ayrıca `core/entities/models.py` içindeki `Ayar` sınıfının da sıfır çağıranı bulundu (aşağıda madde 3b). **Düzeltme**: madde 2'ye üçüncü bir karar dalı eklendi: kal / taşı / **sil (sıfır çağıran doğrulanırsa)**.

4. **`app/core/unit_of_work.py` gerçek bir SHIM — kök CLAUDE.md kuralını ihlal ediyor**: dosyanın kendi docstring'i itiraf ediyor ("Backward-compatible... Bazı eski kod/testler kullanıyor"), tek yaptığı `app.database.unit_of_work.UnitOfWork`'ü yeniden ihraç etmek. Gerçek çağıranı grep ile sıfıra yakın (`test_compliance_final.py` tek satır). Kök CLAUDE.md'nin "migrated modüllerin eski app/ dosyaları silinir, shim bırakılmaz" kuralını 15 dalga boyunca fark edilmeden ihlal etmiş. **Düzeltme**: bu dosya "taşınacak" değil "silinecek shim" olarak işaretlendi (madde 2 envanterinde not düşüldü), tek test çağıranı `app.database.unit_of_work`'e güncellenecek.

5. **public.py/events.py kararı hiç yoktu**: diğer 15 modülün HEPSİNDE zorunluydu, burada hiç bahsi geçmiyordu. shared_kernel iş modülü olmadığı için `public-surface-only-X` tipi bir import-linter kısıtı anlamsız (amaç zaten HERKESİN serbestçe import edebilmesi) — ama "hangi sembollerin kasıtlı dış-yüzey olduğu" belirsiz kalırsa gelecekte rastgele iç-detay importları (`v2.modules.shared_kernel.infrastructure.base.Base` gibi dağınık importlar) çoğalabilir. **Düzeltme**: madde 7 (yeni) — minimal bir `public.py` eklenmesi kararlaştırıldı, zorunlu import-linter kontratı olmadan, yalnız disiplin için.

6. **Düzeltme #1'in kendisi eksikti — kullanıcı bunu yakaladı**: ilk düzeltme turunda `app/shared_kernel/` → `v2/shared_kernel/` yazıldı, yani `v2/modules/`'ın KARDEŞİ bir üst-seviye dizin olarak bırakıldı. Ama kök `CLAUDE.md`'nin modül tablosu `shared_kernel`/`platform_infra`'yı diğer 15 modülle **AYNI tabloda, aynı sütunlarla** listeliyor — yani onlar da normal birer `v2/modules/<isim>/` girdisi, `v2/modules/`'ın dışında özel bir konum değil (ve zaten `v2/` altında bugün `v2/modules/`'tan başka üst-seviye dizin yok). **Düzeltme**: dosyadaki TÜM `v2/shared_kernel` / `v2.shared_kernel` ifadeleri `v2/modules/shared_kernel` / `v2.modules.shared_kernel`'e çevrildi.

7. **"platform şeması" 6 tablosu tek blok değil — 3'ü admin_platform'a taşınabilir, 3'ü hiçbir v2 modülüne taşınamaz (2026-07-21, dalga 16 madde-3 ön-denetimi)**: `MEMORY/PROGRESS.md` §2.2'nin "platform (şema)" satırı (`sistem_konfig, konfig_gecmis, outbox_events, error_events, error_occurrences, idempotency_keys` — 6 tablo) tek bir 16. sahiplik gibi okunuyor ama gerçek grep + admin_platform'un KENDİ dalga-15 çıktısı (`v2/modules/admin_platform/application/error_events.py`'nin docstring'i: "error_events/error_occurrences/error_hourly_stats'ın YAZIM yolu app/infrastructure/monitoring/'de yaşıyor... hiçbir v2 modülüne ait değil") bunu ikiye ayırıyor:
   - `sistem_konfig`, `konfig_gecmis`, `idempotency_keys` → gerçek çağıranların TAMAMI `v2.modules.admin_platform.*` — **admin_platform'a taşınır** (planın zaten admin_platform satırında listelediği `admin_audit_log`/`entegrasyon_ayarlari` ile birlikte toplam 5 tablo).
   - `outbox_events` → gerçek çağıran tek dosya, `app/infrastructure/events/outbox_service.py` (cross-cutting, TÜM modüller `save_outbox_event` ile kullanıyor, event_bus.py/audit_logger.py ile aynı "henüz v2'ye taşınmamış cross-cutting infra" kategorisi).
   - `error_events` → gerçek çağıranların ezici çoğunluğu `app/infrastructure/monitoring/*` (audit_logger.py/event_bus.py ile aynı kategori).
   - `error_occurrences` → RAW SQL ile (`INSERT INTO error_occurrences`, aylık partition) `app/infrastructure/monitoring/event_bus.py`'de yazılıyor — ORM sınıfı neredeyse yalnız test/referans amaçlı.
   **Düzeltme (2026-07-21, kullanıcı geri bildirimiyle REVİZE edildi)**: madde 3 aşağıda güncellendi — gerçek dağıtım **40 tablo → 15 iş modülü + admin_platform (toplam 16 hedef)**. Kalan 3 tablo İLK ÖNCE burada `app/database/models.py`'de bırakılmak üzere planlanmıştı, ama kullanıcı bu ertelemeyi ("geri de dosya bırakmak için mi bu işi yapıyoruz") reddetti. Yeniden incelendiğinde erteleme gerekçesiz çıktı — üçü de gerçekte küçük, hemen taşınabilir: **`outbox_events`, `error_events`, `error_occurrences` artık `v2/modules/shared_kernel/infrastructure/{outbox,error_monitoring_models}.py`'ye taşındı** (aşağıdaki madde 3'ün güncel hâline bakın). Yalnız ORM sınıfları taşındı — bu tabloları YAZAN gerçek alt sistemlerin kendisi (`app/infrastructure/events/event_bus.py`, `app/infrastructure/monitoring/*` — probes/alarm_router, ~2300 satır) hâlâ `app/`'de, o taşıma gerçekten büyük ve ayrı bir iş (muhtemelen `platform_infra`/dalga 17).

---

## 1. Mevcut envanter (22 dosya, ~5.223 LOC — gerçek `wc -l` ile doğrulandı)
```
app/__init__.py                          → v2/modules/shared_kernel/__init__.py (boş)
app/core/__init__.py                     → v2/modules/shared_kernel/__init__.py ile birleşir
app/core/entities/__init__.py            → dağıtılır (madde 3b)
app/core/entities/models.py              → BÖLÜNÜR modül-başına (madde 3b) — 683 satır
app/database/models.py                   → BÖLÜNÜR modül-başına (madde 3) — 1.988 satır, EN BÜYÜK
app/schemas/base.py                      → v2/modules/shared_kernel/schemas/base.py (gerçek kullanım taranacak)
app/schemas/api_responses.py             → BÖLÜNÜR (madde 4) — 846 satır
app/schemas/validators.py                → v2/modules/shared_kernel/schemas/validators.py (gerçek kullanım taranacak)
app/core/interfaces/__init__.py          → interfaces/repositories.py ile birlikte SİLİNİR (madde 2 düzeltme #3)
app/core/interfaces/repositories.py      → SİLİNİR — sıfır prod çağıran (madde 2 düzeltme #3)
app/core/protocols.py                    → SİLİNİR — sıfır prod çağıran (madde 2 düzeltme #3)
app/core/errors.py                       → v2/modules/shared_kernel'de KALIR (main.py bootstrap seviyesi, tek "modül" değil)
app/core/exceptions.py                   → v2/modules/shared_kernel'de KALIR (57 gerçek çağıran, çoklu modül)
app/core/unit_of_work.py                 → SİLİNİR — backward-compat shim (madde 2 düzeltme #4)
app/core/services/__init__.py            → içeriği kontrol edilip muhtemelen SİLİNİR (dalga 1-15 sonrası app/core/services/ neredeyse boş)
app/core/utils/__init__.py               → v2/modules/shared_kernel/utils/__init__.py
app/core/utils/clock.py                  → gerçek kullanım taranacak, v2/modules/shared_kernel'de KALIR (varsayım)
app/core/utils/type_helpers.py           → gerçek kullanım taranacak, v2/modules/shared_kernel'de KALIR (varsayım)
app/database/__init__.py                 → v2/modules/shared_kernel/__init__.py ile birleşir
app/database/repositories/__init__.py    → TAMAMEN SİLİNİR (madde 5) — re-export hunisi
app/database/base_repository.py          → v2/modules/shared_kernel/infrastructure/base_repository.py (çoklu modül kullanıyor — BaseRepository generic)
app/database/unit_of_work.py             → v2/modules/shared_kernel/infrastructure/unit_of_work.py (gerçek UoW — TEK gerçek versiyon, app/core/unit_of_work.py'nin shim'i değil bu)
```

## 2. Her dosya için ayrı karar — ÜÇ seçenekli (kal / taşı / sil)
Her dosya 15 modül taşınırken zaten "kim import ediyor" ile test edildi (import-linter kontratları). Bu dalgada üç olası karar var:
- **KALIR**: dosya ≥2 modül tarafından GERÇEKTEN import ediliyor VE tek bir modüle ait değil (generic altyapı — `grep -rln "from app.core.X import\|from app.database.X import" v2/` ile doğrulanır, varsayılmaz).
- **TAŞINIR**: dosya (veya dosyanın bir SEMBOLÜ — bkz. madde 3b) tek bir modüle ait, o modülün kendi dizinine gider.
- **SİLİNİR**: dosyanın (veya sembolün) sıfır gerçek (prod) çağıranı var — yalnız kendi test dosyası tarafından egzersiz ediliyor. Silmeden önce standart ritüel uygulanır: `grep -rln` ile sıfır-çağıran TEKRAR doğrulanır, sonra dosya + varsa tek test dosyası birlikte silinir (dalga 1-15'te `config_repo.py`/`model_manager.py`/`predictors/` paketinde uygulanan aynı yöntem).

Bilinen SİLİNECEK adaylar (madde 0'da bulundu, dalga 16 başında TEKRAR doğrulanmalı — bu liste varsayım değil ama zaman geçtiği için re-check şart):
- `app/core/protocols.py` (`ITripService`/`IDriverService`/`IVehicleService`/`IFuelService`/`IInternalService`) — sıfır prod çağıran.
- `app/core/interfaces/repositories.py` (soyut `BaseRepository` Protocol'ü, gerçek `app/database/base_repository.py`'den FARKLI) — sıfır prod çağıran.
- `app/core/unit_of_work.py` — backward-compat shim, kök CLAUDE.md ihlali.
- `core/entities/models.py::Ayar` sınıfı — sıfır çağıran (madde 3b).

## 3. models.py bölünmesi (D.1 risk #1 — en riskli mekanik adım)
`app/database/models.py` (1.988 satır, 43 ORM tablosu, 45 `relationship()`) BU DALGADA **40 tablosu** modül-başına dağıtılır: her tablo `v2/modules/<sahip>/infrastructure/models.py`'ye taşınır (sahiplik MEMORY/PROGRESS.md §2.2 tablosundan, madde 0 düzeltme #7 ile düzeltilmiş hâliyle — 15 iş modülü + admin_platform, admin_platform toplam 5 tablo: `admin_audit_log`, `entegrasyon_ayarlari`, `sistem_konfig`, `konfig_gecmis`, `idempotency_keys`). Ortak `Base` sınıfı BURADA (`v2/modules/shared_kernel/infrastructure/base.py`) kalır, her modül ondan miras alır — İLK taşınacak parça bu, çünkü 43 tablonun HEPSİ ona bağımlı.

**3 tablo — DA TAŞINDI (2026-07-21, kullanıcı geri bildirimiyle, madde 0 düzeltme #7 revizyonu)**: `outbox_events`, `error_events`, `error_occurrences` başta ertelenmişti ama kullanıcı bu ertelemeyi reddetti. Gerçek inceleme sonucu:
- `outbox_events` → gerçek tek sahibi `app/infrastructure/events/outbox_service.py` (136 satır, küçük+self-contained) — ORM sınıfı + servis kodu birlikte `v2/modules/shared_kernel/infrastructure/outbox.py`'ye taşındı, eski dosya silindi (shim yok).
- `error_events`/`error_occurrences` → hiçbir prod kod bu ORM sınıflarını KULLANMIYORDU (yalnız Alembic şema kaydı + 1 test dosyası) — asıl yazım yolu `app/infrastructure/monitoring/event_bus.py`'de ham SQL. ORM sınıfları (+ 2 PG enum) `v2/modules/shared_kernel/infrastructure/error_monitoring_models.py`'ye taşındı.

Monitoring alt sisteminin KENDİSİ (probes/alarm_router/event_bus, ~2300 satır, 13 dosya) taşınmadı — bu ayrı, çok daha büyük bir iş (muhtemelen `platform_infra`/dalga 17). `app/database/models.py` artık bu 3 sınıfı içermiyor.

**27 çapraz-modül `relationship()`** kaldırılırken lazy-load kırılma riski var — mitigasyon sırası:
1. Önce trip dalgasında yapılan `_with_relations()` indirgemesi (bkz. trip.md madde 5) TÜM modüllerde tekrarlanır — her modülün repository'si kendi joinedload'unu explicit tutar.
2. `relationship(back_populates=...)` çiftleri (ör. `Arac.seferler`↔`Sefer.arac`) iki ayrı modülün models.py'sinde TANIMLANAMAZ (SQLAlchemy kısıtı) — çözüm: FK kolonu kalır (ID referansı), `relationship()` KALDIRILIR, ilgili okuma explicit sorguya (repository metodu) çevrilir. Bu, D.1/1'in önerdiği "önce `_with_relations()`, sonra explicit sorgu" sırasının 2. adımı.
3. Her adımda `alembic check` BOŞ DİFF vermeli (modeller yer değiştiriyor, şema değişmiyor — FAZ2'nin şema taşıması AYRI, burada yalnız Python dosya konumu değişiyor).
4. **Önerilen sıra**: tek seferde 43 tabloyu birden taşımak yerine, modül modül (trip önce, sonra fleet, ...) — her modülün tabloları taşındıktan sonra `alembic check` + o modülün testleri + `pytest --collect-only` ile doğrulanıp bir sonraki modüle geçilir. Tek dev-adımda 43 tabloyu birden taşımak, hatanın hangi tabloda olduğunu ayırt etmeyi imkansızlaştırır.

## 3b. `core/entities/models.py` bölünmesi (YENİ — madde 0 düzeltme #2)
683 satırlık bu dosya `database/models.py` ile AYNI mantıkla, SEMBOL bazında (sınıf bazında) dağıtılır — "kaç modül import ediyor" değil "hangi modülün iş nesnesi" sorusuna göre:

| Sınıf | Hedef modül | Not |
|---|---|---|
| `Arac`, `AracCreate`, `AracUpdate` | fleet | |
| `Sofor`, `SoforCreate` | driver | |
| `Lokasyon` | location | |
| `YakitAlimi`, `YakitAlimiCreate`, `YakitUpdate`, `YakitPeriyodu` | fuel | |
| `Sefer`, `SeferCreate`, `SeferUpdate` | trip | |
| `DurumEnum`, `SeferDurumEnum`, `ZorlukEnum` | trip | sefer durum/zorluk enum'ları |
| `PredictionResult` | prediction_ml | |
| `AnomalyResult`, `AnomalyType`, `SeverityEnum` | anomaly | |
| `DashboardStats`, `VehicleStats`, `DriverStats` | **doğrulanacak** | gerçek çağıranlar driver+fleet+reports karışık — dalga 16 başında üçü de okunup gerçek "kim üretiyor, kim tüketiyor" ayrımı yapılmalı (muhtemel aday: reports, ama varsayılmadı) |
| `Ayar` | **SİLİNİR adayı** | sıfır çağıran bulundu, dalga 16'da re-check + sil |
| `BaseEntity` | v2/modules/shared_kernel | gerçekten paylaşılan taban Pydantic sınıfı — TEK KALAN shared_kernel üyesi bu dosyadan |

Her taşınan sınıf, hedef modülün `schemas.py` (Pydantic response ise) veya `domain/`/kendi entity dosyasına gider — hangisi olduğu o modülün mevcut yapısına göre karar verilir (örn. trip zaten `schemas.py`'de `SeferBase`/`SeferCreate` taşıyor, bu yeni `Sefer`/`SeferCreate` sınıflarının onlarla çakışıp çakışmadığı — muhtemelen AYNI amaç, olası birleştirme fırsatı — dalga 16'da netleştirilecek, varsayılmadı).

## 4. api_responses.py (846 satır, ~40 sınıf) dağıtımı
MEMORY §B.1'deki ölçüm: health/import/notification/maintenance/fuel/weather/route/location/fleet/dorse karışık sınıflar. Her sınıf, hangi modülün response şeması olduğuna göre o modülün `schemas.py`'sine taşınır (ör. `MaintenanceRecordResponse`→fleet, `WeatherDashboardResponse`→route_simulation, `NotificationRuleResponse`→notification). Ortak taban sınıflar (`MessageResponse`, `SuccessCountResponse`, `DeleteResultResponse` gibi jenerik zarflar) BURADA (`v2/modules/shared_kernel/schemas/api_responses.py`) kalır.

## 5. repositories/__init__.py re-export hunisi
MEMORY §2.1'de tespit edilen `database/repositories/__init__.py`'nin 15 modülün repo'sunu re-export etmesi — bu dalgada TAMAMEN SİLİNİR (her modül kendi repository'sini `infrastructure/repository.py`'den doğrudan import eder, merkezi huniye ihtiyaç kalmaz). **Gerçek blast-radius doğrulandı (dalga 16 ön-denetimi)**: yalnız 2 gerçek çağıran var — `app/database/unit_of_work.py` (20 `_Lazy` descriptor'ın import satırları, her biri ilgili modülün `infrastructure/repository.py`'sine doğrudan çevrilecek) ve `tests/test_app_boot.py` (boot-smoke testi, import yolu güncellenecek). Bu, planın EN DÜŞÜK riskli adımı — dalga 16'nın ilk yapılacak işi olarak önerilir (mekanizmayı kanıtlar, sonraki daha riskli adımlara güven verir).

## 6. Kabul kriterleri
- [x] Tüm yol referansları `v2/modules/shared_kernel/` ve `v2/modules/<isim>/` (madde 0 düzeltme #1)
- [x] `core/entities/models.py` sembol-bazında dağıtıldı — dosyanın kendisi artık yok, `BaseEntity` `v2/modules/shared_kernel/domain/base_entity.py`'ye taşındı (bu erken bir dalga 16 alt-adımında yapılmış, bu doküman-güncelleme turunda doğrulandı)
- [x] `protocols.py`, `interfaces/repositories.py`, `app/core/unit_of_work.py` — üçü de zaten yok (sıfır-çağıran silme daha önce yapılmış, bu turda doğrulandı: `app/core/protocols.py`/`app/core/interfaces/`/`app/core/unit_of_work.py` dosya sisteminde mevcut değil)
- [x] `Ayar` sınıfı — grep ile doğrulandı, hiçbir yerde `class Ayar` yok (core/entities/models.py ile birlikte gitti)
- [x] models.py'nin 43 tablosunun TAMAMI dağıtıldı (15 iş modülü + admin_platform + shared_kernel), her adımda `alembic check` boş-diff. Kalan 3 tablo (`outbox_events`/`error_events`/`error_occurrences`) de taşındı (2026-07-21, kullanıcı geri bildirimiyle) — `v2/modules/shared_kernel/infrastructure/{outbox,error_monitoring_models}.py`. Son 3 iş-modülü tablosu (`Lokasyon`/`LokasyonSegment`→location, `YakitAlimi`/`YakitPeriyot`/`YakitFormul`→fuel, `PageView`→reports) taşınınca `app/database/models.py`'de SIFIR sınıf kaldı — dosya TAMAMEN SİLİNDİ (44 gerçek çağıran dosya güncellendi, `Base` artık doğrudan `v2.modules.shared_kernel.infrastructure.base`'den import ediliyor).
- [x] Çapraz-modül `relationship()`'lar kaldırıldı, explicit FK-id kolonlarına çevrildi — her modülün taşınması sırasında tek tek doğrulanıp yapıldı (auth_rbac↔notification/prediction_ml, route_simulation↔location gibi), her yeni `infrastructure/models.py`'nin kendi docstring'inde dokümante
- [x] api_responses.py 846 satır dağıtıldı, yalnız jenerik zarflar (`MessageResponse`/`SuccessCountResponse`/vb., 118 satır) `v2/modules/shared_kernel/schemas/api_responses.py`'de kaldı (bu erken bir alt-adımda yapılmış, bu turda doğrulandı)
- [x] repositories/__init__.py hunisi silindi (`app/database/repositories/` artık boş, yalnız `__pycache__`)
- [x] `v2/modules/shared_kernel/public.py` oluşturuldu — kasıtlı dış-yüzey sembolleri (madde 7)
- [x] Kalan shared_kernel dosya sayısı 19 (≤22, büyümedi) — `find v2/modules/shared_kernel -name "*.py" | grep -v __pycache__ | wc -l` ile doğrulandı

## 7. public.py/events.py kararı (YENİ — madde 0 düzeltme #5)
shared_kernel iş modülü olmadığı için `public-surface-only-shared_kernel` tipi ZORUNLU bir import-linter kısıtı anlamsız (amaç zaten her modülün serbestçe erişebilmesi). Ama disiplin için minimal bir `v2/modules/shared_kernel/public.py` oluşturulacak — yalnız KASITLI dış-yüzeyi listeler (`Base`, `BaseRepository` generic, kalan `exceptions.py` hiyerarşisi, `errors.py::DiagnosticHelper`, `UnitOfWork`/`get_uow`, `clock`/`type_helpers` yardımcıları, kalan jenerik response zarfları). `events.py` gerekmiyor — shared_kernel event yayınlamaz/dinlemez (event_bus zaten `app/infrastructure/events/`'te ayrı bir cross-cutting altyapı, bu modülün kapsamı dışında).
