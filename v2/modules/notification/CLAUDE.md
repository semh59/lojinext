# Modül: notification

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Sistem içi bildirim kurallarının (`bildirim_kurallari`) yönetimi, olay-tabanlı
bildirim üretimi (`bildirim_gecmisi`), Web Push aboneliği (`push_subscriptions`)
+ gönderimi, canlı bildirim WebSocket akışı (`/admin/ws/live`), Telegram
ops-bot hata/feedback bildirimleri, ve e-posta gönderimi (şifre sıfırlama vb.).

NE YAPMAZ: bildirimi TETİKLEYEN iş mantığı (trip modülü SEFER_UPDATED/
SLA_DELAY event'lerini publish eder, notification yalnız dinler); ML eğitim
ilerleme akışı (`/admin/ws/training` — admin_platform'un, bkz. aşağıdaki
admin_ws.py bölünmesi); kullanıcı tercihleri/sessiz-saat AYARLARININ
saklanması (`PreferenceService`, henüz taşınmamış cross-module bağımlılık).

## Public API (public.py imzaları)

```python
register_handlers() -> None                          # app startup — bkz. "Bilinen açık" altında
handle_event(event: Event) -> None                    # SEFER_UPDATED/SLA_DELAY işleyici

get_user_notifications(user_id: int) -> list[BildirimGecmisi]
mark_as_read(notification_id: int, user_id: int) -> bool     # IDOR-guard'lı
mark_all_as_read(user_id: int) -> int

list_rules() -> list[BildirimKurali]
create_rule(data: dict) -> BildirimKurali
update_rule(rule_id: int, changes: dict) -> BildirimKurali | None
delete_rule(rule_id: int) -> bool

subscribe_push(user_id: int, *, endpoint, p256dh, auth, user_agent) -> PushSubscription
unsubscribe_push(user_id: int, endpoint: str) -> None

send_push_to_user(user_id, *, title, body, url=None, uow=None, respect_quiet_hours=False) -> PushSendResult
send_push_broadcast(*, title, body, url=None, uow=None) -> PushSendResult
vapid_configured() -> bool

is_user_quiet_now(user_id, *, now=None) -> bool
is_within_quiet_hours(deger: dict, now_t: time) -> bool

notify_error(*, level, message, path="", trace_id="") -> None     # Telegram ops-bot
notify_feedback(*, message, username="", page="") -> bool
send_password_reset(email, token, name=None) -> None               # SMTP
send_text(to, subject, body) -> None

notification_ws_manager: ConnectionManager           # /live WS broadcaster
NotificationRepository, get_lokasyon_repo benzeri factory YOK — uow.notification_repo kullan
```

**Önemli**: `NotificationService` sınıfı YOK (location/route_simulation'daki
B.1 kararıyla aynı gerekçe — event-subscriber ikilisi (`register_handlers`/
`handle_event`) tek dosyada kalır çünkü tek bir event-subscription
use-case'inin iki yarısıdır, bağımsız use-case'ler değil). Diğerleri
(get/mark/mark_all/send_push_*) birer bağımsız fonksiyon.

## Yayınladığı / dinlediği event'ler (events.py DTO'ları)

notification kendi event'ini YAYINLAMAZ — yalnız trip modülünün
`SEFER_UPDATED`/`SLA_DELAY` event'lerini dinler. `events.py`'deki
`SeferUpdatedPayload`/`SlaDelayPayload` DTO'ları TÜM alanları Optional —
trip modülünün 4 farklı publish call-site'ı (physics_handler,
attribution_service, sefer_analiz_service, sefer_write_service) birbirinden
hafif farklı payload şekilleri gönderiyor; `handle_trip_events.py` yalnız
`sefer_id`/`trigger`/`delay_min` okuyor, DTO da yalnız bunları tipler.

## ✅ DÜZELTİLDİ (2026-07-16, kullanıcı kararıyla) — event-subscriber artık ÇALIŞIYOR

Önceki bulgu (taşıma sırasında keşfedildi, o dalganın regresyonu DEĞİLDİ):
`register_handlers()` app başlangıcında hiçbir yerde çağrılmıyordu, aynı
şekilde `physics_handler.py`'nin `.register()` metodu ve
`setup_cache_invalidation()`/`get_model_training_handler().setup()`/
`get_rag_sync_service().initialize()` de. Bu, tüm event-bus tüketicilerini
etkileyen repo-genelinde bir başlangıç-kablolama boşluğuydu — o zaman
davranış değişikliği + downstream etki analizi gerektirdiği için kullanıcı
kararına bırakılmıştı.

Kullanıcı "gerçekten bağla" kararını verince (`TASKS/STATUS.md` "Event-bus
wiring" bölümü) hepsi `app/main.py`'nin `lifespan`'ına eklendi — her biri
kendi `try/except`'i içinde, biri başarısız olursa diğerlerini veya app
startup'ı engellemez. Artık `bildirim_kurallari` tablosundaki kurallar
SEFER_UPDATED/SLA_DELAY geldiğinde gerçekten tetikleniyor (bu event'ler
zaten doğrudan `event_bus.publish_async()` ile in-process yayınlanıyordu —
`physics_handler.py`/`sefer_write_service.py`; eksik olan yalnız subscriber
tarafıydı). `PushSendResult`/push akışı bundan hiç etkilenmedi (ayrı,
doğrudan çağrılan bir yol).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **auth_rbac** (senkron, in-edge): `auth_routes.py`'nin
  `/password-reset-request` endpoint'i `send_password_reset`'i artık
  `v2.modules.notification.public`'ten çağırır (2026-07-18 düzeltmesi —
  eskiden public.py'yi atlayıp infrastructure/email_client'tan doğrudan
  import ediyordu; public.py aynı fonksiyonu zaten re-export
  eder ama bu çağıran onu kullanmıyor — düzeltildi, 2026-07-17
  dedektif denetimi bulgusu, bkz. `TASKS/bug-11-wave-b1-detective-audit-2026-07-17.md`
  madde 3).
- **auth_rbac** (senkron, out-edge): `application/quiet_hours.py`'nin
  `is_user_quiet_now`'ı `v2.modules.auth_rbac.application.preference_service`'i
  doğrudan import eder (dalga 6'da güncellendi — eski `app.core.services.
  preference_service.PreferenceService` yolu artık yok).
- **analytics_executive** (senkron, in-edge): `compliance_tasks.py`
  (muayene push hatırlatma) `send_push_broadcast`'i `notification.public`
  üzerinden import eder (2026-07-18: public'e çevrildi). ~~`generate_insights.py`'nin
  `_notify_serious_alerts`'i~~ — o dosya 2026-07-18 ölü-kod temizliğinde
  silindi, bu in-edge artık yok.
- **Trip modülü** (asenkron, event): `SEFER_UPDATED`/`SLA_DELAY` — bkz. yukarı.
- **Çeşitli workers/endpoints** (senkron, in-edge, `notify_error`/
  `notify_feedback`): `error_digest.py`, `fuel_coverage_check.py`,
  `alarm_router.py`, `feedback.py` — hepsi `telegram_client`'i import eder.

## admin_ws.py bölünmesi (dalga 2'nin kendi kapsamı, kullanıcı onayıyla)

Eski `app/api/v1/endpoints/admin_ws.py` İKİ bağımsız WebSocket route
içeriyordu: `/training` (ML eğitim ilerleme, admin_platform'a ait,
`training_ws_manager`) ve `/live` (canlı bildirim, notification'a ait,
`notification_ws_manager`). notification.md görev dosyasının (a)/(b)
seçenekleri ("dosya ya tamamen taşınır ya tamamen kalır") bu karışık içeriği
yansıtmıyordu — dosyanın kendisi bölündü:

- `v2/modules/admin_platform/api/admin_ws_routes.py` (eski adı
  `app/api/v1/endpoints/admin_ws.py`, dalga 15'te admin_platform'a
  taşındı) — yalnız `/training` kaldı.
- `v2/modules/notification/api/live_ws_routes.py` — `/live` buraya taşındı.
- Paylaşılan `ConnectionManager` sınıfı + WS auth helper'ları
  (`verify_ws_token`, `resolve_ws_identity`, `is_admin_email`) **hiçbir
  modüle ait olmayan gerçekten paylaşılan bir infra** olarak
  `app/infrastructure/websocket/{connection_manager,ws_auth}.py`'ye
  çıkarıldı (event_bus/audit_logger ile aynı gerekçe — cross-cutting infra,
  business modülü değil). Her iki route de bu paylaşılan sınıfı kullanır,
  birbirine bağımlı değil.
- URL kontratı KORUNDU: `/admin/ws/live` + `/admin/ws/training` — iki farklı
  router objesi `api.py`'de aynı `/admin/ws` prefix'i altına mount edilir
  (FastAPI bunu destekler, tek bir router olması şart değil).
- **Katman ihlali düzeltmesi**: eski `notification_service.py`, eski
  `app.api.v1.endpoints.admin_ws`'den (bugünkü adıyla `v2.modules.
  admin_platform.api.admin_ws_routes`) `notification_ws_manager`'ı import
  ediyordu (servis → endpoint, ters katman bağımlılığı). Artık
  `handle_trip_events.py`, kendi modülünün `infrastructure/ws_broadcaster.py`'sinden
  import ediyor — endpoint'e hiç bağımlı değil.

## Şema & tablo sahipliği

`bildirim_kurallari`, `bildirim_gecmisi`, `push_subscriptions` (3 tablo).

## İzin verilen / yasak import'lar (import-linter özeti)

FAZ1'in v2-modülü import-linter gate'i henüz aktif değil (bkz.
`TASKS/faz1-import-linter-baseline-ve-gate.md`, kendisi de DURMA NOKTASI'lı
ayrı bir onay gerektiren çatı görevi, location dalgasında da kurulmadı).
Hedef kontrat: diğer modüller yalnız `v2.modules.notification.public`'i
import eder; `application/`/`domain/`/`infrastructure/`'a doğrudan erişim
yasak — bu artık gerçekten böyle (2026-07-18'den beri `compliance_tasks.py`
public üzerinden gidiyor); gate aktive olunca mevcut `public`/`events`
importları zaten kurala uygun, ek `ignore_imports` gerekmiyor.

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`bildirim`=notification, `kural`=rule, `olay_tipi`=event_type,
`kanal`=channel, `durum`=status, `okundu`=read, `sessiz_saat`=quiet_hours,
`abonelik`=subscription.

## Modüle özel iş kuralları & gotcha'lar

- 🔴 **DÜZELTİLDİ (2026-07-15, "ilk 8 dalga" B.1 dedektif denetiminde
  bulundu, `TASKS/bug-route-layer-bypasses-application.md`) — GERÇEK BUG,
  B.1'in ötesinde:** `api/notification_routes.py`'nin rule CRUD handler'ları
  (`list_rules`/`create_rule`/`update_rule`/`delete_rule`) ve
  `api/push_routes.py`'nin `subscribe`/`unsubscribe`'ı `application/`
  katmanını atlayıp doğrudan `uow.notification_repo`/ORM'e erişiyordu —
  `application/manage_notification_rules.py` +
  `application/manage_push_subscription.py`'ye taşındı (mekanik, davranış
  değişikliği yok). AMA taşıma sırasında GERÇEK bir bug bulundu: eski
  `subscribe`/`unsubscribe` hiçbir zaman `uow.commit()` çağırmıyordu.
  `UnitOfWork.__aexit__`'in ghost-transaction guard'ı yalnız ORM
  identity-map'i (`session.new`/`dirty`/`deleted`) kontrol eder;
  `unsubscribe`'ın Core-tarzı `session.execute(delete(...))`'u bu
  koleksiyonlara dokunmadığı için guard hiç tetiklenmiyor ve "temiz çıkış,
  sadece kapat" dalına düşüp DELETE'i sessizce **rollback ediyordu**;
  `subscribe`'daki ORM `add`/attribute-mutasyonu ise `session.new`/`dirty`'yi
  dolduruyor, guard tetikleniyor, yine rollback oluyordu. Sonuç: her iki
  endpoint de 200/201/204 dönüyordu ama veritabanında HİÇBİR ŞEY kalıcı
  olmuyordu — push aboneliği/aboneliği-kaldırma taşımadan önce de (bug
  taşımadan ÖNCE vardı, `git show 78fd145:...push_routes.py` ile
  doğrulandı) çalışmıyordu. Testler bunu yakalamamıştı çünkü hiçbiri
  kalıcılığı ayrı bir sorgu ile doğrulamıyor, sadece status code kontrol
  ediyor (`test_push_coverage.py`). Düzeltme: her iki fonksiyona
  `await uow.commit()` eklendi — tek satırlık, davranış-genişletici değil,
  sadece dokümante edilen bug'ı kapatıyor.
- **`notification_prioritizer.py` tamamen ölü kod**: saf `score_priority`
  fonksiyonu `domain/prioritizer.py`'ye, DB-sorgulu `NotificationPrioritizer`
  sınıfı `infrastructure/prioritizer.py`'ye ayrıştırıldı (B.1 + domain'in
  I/O'suz kalması gerekliliği — ilk taşımada sınıf yanlışlıkla domain/'de
  bırakılmıştı, bağımsız denetimde yakalanıp düzeltildi). Sınıf hiçbir prod
  kod tarafından çağrılmıyor (yalnız kendi testlerinde kullanılıyor) —
  location'ın `LOKASYON_ADDED` event-publish'inin dead-code durumuyla aynı
  desen, bu taşımanın getirdiği bir regresyon değil.
- **EMAIL kanal teslimatı log-only stub**: `handle_trip_events.py`'de
  `kanal == "EMAIL"` dalı yalnız log basar, gerçek e-posta göndermez —
  `BildirimDurumu.FAILED` ile işaretlenir (dashboard'larda sahte "delivered"
  görünmesin diye kasıtlı).
- **Synthetic super-admin push guard** (`push_routes.py`): `current_user.id
  <= 0` (break-glass admin, `kullanicilar` tablosunda gerçek satırı yok) →
  erken 403, aksi halde push_subscriptions FK ihlaliyle opak 500 (0-mock
  epiği sırasında bulunmuş gerçek bug, `preferences.py`'deki aynı desenle
  korunuyor).
- **VAPID_PUBLIC_KEY boşsa `/push/vapid-public-key` push_enabled=False
  döner** — frontend buna göre subscribe etmemeli.
- **Weekly digest quiet-hours'a saygılı**: `infrastructure/tasks.py`'nin
  `weekly_digest` Celery task'i `respect_quiet_hours=True` ile çağırır —
  acil olmayan digest bildirimleri kullanıcı sessiz saatteyse atlanır (route
  içinden `send_test_push` gibi acil/manuel push'lar bunu YAPMAZ).
- **410 Gone → subscription otomatik silinir** (`webpush_client.py` +
  `application/send_push_{to_user,broadcast}.py`): pywebpush 410 dönerse
  kayıt `push_subscriptions`'tan silinir, `expired` sayaç artırılır.

## Test stratejisi (slice/entegrasyon koşumu)

- `app/tests/unit/test_services/test_notification_service_coverage.py`,
  `app/tests/unit/test_notification_n1.py` — event-subscriber (`handle_event`)
  testleri; N+1 testi GERÇEK DB'ye karşı (spy, mock değil).
- `app/tests/unit/test_{vapid,webpush_client,send_push_to_user,push_broadcast,
  quiet_hours,notification_prioritizer,email_service}.py` — domain/
  infrastructure/application katmanlarının ayrı ayrı unit testleri (eski tek
  `test_push_sender.py`, kod üç dosyaya bölündüğü için üç test dosyasına
  bölündü: `test_vapid.py`, `test_webpush_client.py`,
  `test_send_push_to_user.py`).
- `app/tests/unit/test_infrastructure/test_websocket_shared.py` —
  `ConnectionManager`/`verify_ws_token` (paylaşılan WS infra, admin_ws.py'nin
  eski `test_admin_ws_coverage.py`'sinden ayrıştırıldı).
- `app/tests/api/test_notification_live_ws.py` — `/live` route (admin_ws.py'nin
  `/training` testlerinden ayrıştırıldı, bkz. `test_admin_ws_coverage.py`).
- `app/tests/api/test_push_coverage.py`, `test_admin_notifications_coverage.py`,
  `test_admin_notifications.py` — endpoint testleri.
- `app/tests/security/test_idor_notifications.py`,
  `app/tests/integration/test_notification_ownership_integration.py` —
  `mark_as_read` IDOR-guard'ı (gerçek DB, gerçek iki kullanıcı).
- Free-function `unittest.mock.patch` hedefi HER ZAMAN **tüketen modül**
  namespace'i (örn. `v2.modules.notification.application.send_push_to_user.send_webpush`)
  — İstisna: fonksiyon-içi (inline) importlar (`push_to_user`'ın
  `is_user_quiet_now`'ı gibi) — bunlar KAYNAK modülden patch'lenir
  (`v2.modules.notification.application.quiet_hours.is_user_quiet_now`).
