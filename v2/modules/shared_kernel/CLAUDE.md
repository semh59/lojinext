# Modül: shared_kernel

## Doğa farkı (bu bir iş modülü DEĞİL)

15 iş modülü + admin_platform taşındıktan sonra geriye kalan, GERÇEKTEN
≥2 modül tarafından paylaşılan altyapı/kod. B.1 kuralı burada "bir dosya =
bir görev" anlamında değil, "shared_kernel yalnız küçülebilir, büyümez"
anlamında geçerli — yeni bir cross-module bağımlılık ortaya çıktığında
buraya kod eklemek yerine, önce gerçekten paylaşılan mı yoksa bir modülün
sahiplenmesi gereken bir şey mi olduğu sorgulanır.

Import-linter'ın `public-surface-only-<module>` tipi kontratları burada
YOK — amaç zaten herkesin serbestçe import edebilmesi. `public.py` yine de
var (madde 0 düzeltme #5): kasıtlı dış-yüzeyi belgelemek için, zorunlu bir
kontrat olmadan.

## Neden "Senkron konuştuğu modüller" / "Yayınladığı/dinlediği event'ler" başlığı YOK

Diğer 15 iş modülünün CLAUDE.md'si bu iki başlığı taşır, burada kasıtlı
olarak yok — unutulmadı:

- **Senkron konuştuğu modüller**: bu başlık normalde "bu modül hangi
  DİĞER modülün `public.py`'sini çağırıyor" sorusuna cevap verir — yani
  modülün DIŞARI doğru bağımlılığını gösterir. shared_kernel'in dışarı
  doğru böyle bir bağımlılığı YOK (tam tersi yönde çalışır: herkes ona
  bağımlı, o kimseye değil). `unit_of_work.py`'nin 15 modülün
  repository'lerini import etmesi bu kategoriye girmez — bu bir iş
  akışı çağrısı değil, DI/lazy-bind mekaniği (aşağıdaki "İzin verilen /
  yasak import'lar" bölümünde `ignore_imports` listesiyle zaten
  belgelendi, ikinci kez ayrı başlıkta tekrarlamak gereksiz olurdu).
- **Yayınladığı/dinlediği event'ler**: shared_kernel kendi domain
  event'ini yayınlamaz ve hiçbir event'e abone olmaz. `infrastructure/
  outbox.py`'nin `OutboxEvent`/`save_outbox_event`/`OutboxService` içeriği
  bir istisna DEĞİL — bu, DİĞER modüllerin (driver/trip/fuel/location/
  fleet) KENDİ event'lerini yazdığı paylaşılan altyapı tablosu/servisi;
  shared_kernel'in kendisi hiçbir `EventType` tanımlamaz, hiçbir
  `@publishes`/`register_handlers` çağırmaz (`grep -rn "publishes\|
  register_handlers" v2/modules/shared_kernel/` sıfır sonuç verir).

## İçerik envanteri (dalga 16, task #58/#59 — `app/`'den taşındı)

```
v2/modules/shared_kernel/
├── public.py                              # kasıtlı dış-yüzey (aşağıya bkz.)
├── errors.py                              # BusinessException, DiagnosticHelper, create_error_response
├── exceptions.py                          # DomainError hiyerarşisi (57 gerçek çağıran)
├── domain/
│   └── base_entity.py                     # BaseEntity (Pydantic) — fleet.Arac/trip.Sefer entity'leri miras alır
├── infrastructure/
│   ├── base.py                            # Base (SQLAlchemy DeclarativeBase), EncryptedPII, get_utc_now
│   ├── base_repository.py                 # BaseRepository[T] — generic CRUD (27 gerçek çağıran)
│   ├── unit_of_work.py                    # UnitOfWork, get_uow, unit_of_work (168 gerçek çağıran — TÜM modüller)
│   ├── outbox.py                          # OutboxEvent ORM + save_outbox_event/OutboxService (dalga 16 task #58)
│   └── error_monitoring_models.py         # ErrorEvent/ErrorOccurrence ORM (dalga 16 task #58 — hiçbir prod çağıranı yok, yalnız Alembic şema kaydı)
├── schemas/
│   ├── base.py                            # ResponseMeta, StandardResponse
│   ├── api_responses.py                   # MessageResponse/SuccessCountResponse/... (846→118 satır, geri kalanı modüllere dağıtıldı)
│   └── validators.py                      # sanitize_string/check_xss/validate_*/create_*_validator (güvenlik validatorları)
└── utils/
    ├── clock.py                           # current_date/current_datetime_utc (test-edilebilir clock injection)
    └── type_helpers.py                    # safe_float
```

## Public API (public.py imzaları)

```python
# domain entity
BaseEntity

# errors (FastAPI-facing, app/main.py'nin exception_handler'ı)
BusinessException, DiagnosticHelper, create_error_response

# domain exception hiyerarşisi (app/main.py handler'ları HTTP koduna map eder)
DomainError, FuelCalculationError, ImportValidationError, ExcelExportError,
RouteProcessingError, MLPredictionError, AnomalyDetectionError,
AuditLogError, LLMProviderError

# ORM base + generic infra
Base, EncryptedPII, get_utc_now
BaseRepository
ErrorEvent, ErrorOccurrence
OutboxEvent, OutboxService, get_outbox_service, save_outbox_event
UnitOfWork, get_uow, unit_of_work

# generic response envelopes
ResponseMeta, StandardResponse
MessageResponse, MessageWithWarningResponse, SuccessCountResponse,
ImportResultResponse, DeleteResultResponse, UploadResultResponse,
TaskStatusResponse, SuccessOnlyResponse

# güvenlik validatorları
sanitize_string, check_xss, check_sql_injection, validate_safe_string,
validate_username, validate_name, mask_phone, validate_dict_size,
validate_password_complexity, validate_phone,
create_safe_string_validator, create_username_validator,
create_name_validator, create_password_validator, create_phone_validator

# clock injection
current_date, current_datetime_utc

# type helpers
safe_float
```

Bazı dosyalar (örn. `infrastructure/unit_of_work.py`, `infrastructure/
base_repository.py`) 15+ modül tarafından o kadar sık import edildiği için
pratikte hem `public.py` üzerinden hem de doğrudan
`v2.modules.shared_kernel.infrastructure.<dosya>` üzerinden import edilir
— ikisi de sanctioned (bkz. aşağıdaki "izin verilen import'lar").

## Sınıf istisnaları (B.1 anlamında değil — bunlar zaten "kal" kararı alınmış generic altyapı)

- **`BaseRepository`** — tüm 15 modülün repository'lerinin miras aldığı
  generic CRUD sınıfı (repository pattern zaten B.1'in istisnası, bkz. kök
  CLAUDE.md "Repository pattern").
- **`UnitOfWork`** — tek transaction + lazy-bound repository'ler; gerçek
  mutable state (session, commit/rollback durumu) taşıyan tek sınıf.
- **`OutboxService`** — `outbox_events` tablosuna yazan ince bir servis
  (dalga 16 task #58'de `app/infrastructure/events/outbox_service.py`'den
  taşındı, shim bırakılmadan eski dosya silindi).
- **`DiagnosticHelper`** — `errors.py`'nin `create_error_response`'unun
  kullandığı statik-metot yardımcı sınıfı (state yok, sınıflandırma amaçlı).

## Neden buraya taşındı — her dosya için gerekçe

- **`errors.py`/`exceptions.py`**: `app/main.py`'nin bootstrap-seviyesi
  exception handler'ları tarafından kullanılıyor (main.py tek bir "modül"
  değil, tüm app'in giriş noktası) + `exceptions.py`'nin 57 gerçek çağıranı
  15 modüle yayılmış durumda.
- **`base_repository.py`/`unit_of_work.py`**: TÜM 15 iş modülünün
  repository'leri `BaseRepository`'den miras alır, TÜM modüllerin
  application-katmanı `UnitOfWork`'ü kullanır (168 gerçek çağıran, bu
  projenin en yoğun import edilen tek dosyası).
- **`schemas/base.py`/`schemas/validators.py`/`schemas/api_responses.py`**:
  jenerik response zarfları (`MessageResponse` vb.) ve güvenlik
  validatorları (`sanitize_string`/`check_xss` vb.) hiçbir işe özgü değil,
  tüm modüllerin Pydantic şemaları bunları kullanır.
- **`utils/clock.py`/`utils/type_helpers.py`**: test-edilebilirlik için
  clock injection + `safe_float` tip dönüşümü — hiçbir modüle özgü değil.
- **`domain/base_entity.py`**: `BaseEntity` — fleet'in `Arac` ve trip'in
  `Sefer` internal (Pydantic) entity'leri bundan miras alır.
- **`infrastructure/outbox.py`/`error_monitoring_models.py`**: bkz.
  yukarıdaki içerik envanteri notu — ikisi de kullanıcı geri bildirimiyle
  (2026-07-21, "bu 3 tablonun sahibini bulun taşıyın") dalga 17'ye
  ertelenmekten kurtarılıp hemen taşındı.

## İzin verilen / yasak import'lar

`public-surface-only-shared_kernel` gibi bir kontrat YOK (kasıtlı — bu
modülün amacı zaten herkesin serbestçe erişebilmesi). `module-cross-
domain-infra-independence` ve `module-internal-layers` kontratlarının
`ignore_imports` listesinde `v2.modules.shared_kernel.infrastructure.
unit_of_work -> v2.modules.<X>.infrastructure.<repo>` şeklinde 20 satır
var — bu, `UnitOfWork`'ün TÜM modüllerin repository'lerini lazy-bind
etmesinin doğal/kabul edilmiş sonucu, ihlal değil.

**İki döngüsel-import istisnası** (dalga 16 task #58 sırasında bulundu,
`ignore_imports`'a eklendi):
- `v2.modules.trip.infrastructure.repository -> v2.modules.location.infrastructure.models`
- `v2.modules.analytics_executive.infrastructure.executive_read_models -> v2.modules.fuel.infrastructure.models`

İkisi de aynı sebep: `unit_of_work.py` bu iki dosyayı import ediyor, bu iki
dosya da normalde `location.public`/`fuel.public` üzerinden gitseydi o
public.py'ler `unit_of_work.py`'ye geri bağımlı use-case'ler içerdiği için
(`add_trip.py`, `add_yakit.py` — ikisi de `get_outbox_service`/`UnitOfWork`
kullanıyor) döngü oluşurdu. Çözüm: bu 2 dosya cross-module ORM sınıfını
`public.py` yerine doğrudan hedef modülün `infrastructure.models`'ından
alır (reports'un `ReportRepos.yakit_repo = v2.modules.fuel.infrastructure.
repository` ile aynı, zaten dokümante edilmiş infra-to-infra deseni).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`hata`=error/exception, `birim iş`=unit of work, `depo`=repository,
`zarf`=envelope (response), `doğrulayıcı`=validator, `saat enjeksiyonu`=clock
injection.

## Kapsam dışı bırakılanlar (shared_kernel'e AİT DEĞİL, karıştırılmasın)

- `v2/modules/platform_infra/container.py` (dalga 17'de `app/core/
  container.py`'den taşındı) — DI composition root, bootstrap-seviyesi,
  ayrı bir konsept.
- `app/core/ai/*` (5 dosya) — ai_assistant modülünün henüz taşınmamış
  eski dosyaları (kendi CLAUDE.md'sinde dokümante, bu modülün kapsamı
  dışı).
- `app/core/services/{weather_service,route_validator,openroute_service,
  route_calibration_service}.py` — route_simulation'ın henüz taşınmamış
  eski dosyaları (kök CLAUDE.md'de dokümante).
- `app/database/{connection.py,db_session.py,init_db.py}` — DB bootstrap/
  engine kurulumu, orijinal 22 dosyalık envanterde hiç yoktu, kapsam dışı.
- `app/schemas/telegram.py` — iş-alanına özgü Telegram bot şemaları
  (trip/driver/admin_platform'un konusu), generic değil.
- `app/schemas/trip_planner.py` — zaten `v2.modules.ai_assistant.schemas`'a
  yönlendiren, kendi docstring'inde "FAZ4'te silinir" diye dokümante
  edilmiş bilinçli bir shim; bu dalganın kapsamı dışı.

## Test stratejisi

Bu dosyaların kendi ayrı test dosyası genelde yok (`exceptions.py`,
`base_repository.py`, `unit_of_work.py` gibi altyapı, her modülün KENDİ
testleri tarafından dolaylı olarak egzersiz edilir). Doğrudan testler:
`app/tests/unit/test_unit_of_work_semantics.py` (UoW re-entrancy/ghost-
transaction/nested-session semantiği), `app/tests/unit/test_coverage_boost.py`
(errors.py — `BusinessException`/`create_error_response`).
