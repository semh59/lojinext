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

## 🔴 Kritik keşif (taşıma sırasında bulundu, regresyon DEĞİL): event-subscriber HİÇ ÇALIŞMIYOR

`register_handlers()` (eski `NotificationService.register_handlers`) app
başlangıcında (main.py `lifespan`) veya başka hiçbir yerde **çağrılmıyor**.
Yani `bildirim_kurallari` tablosundaki kurallar hiçbir zaman tetiklenmiyor —
admin CRUD (`/admin/notifications/rules`) çalışıyor, kural oluşturulabiliyor,
ama SEFER_UPDATED/SLA_DELAY event'leri geldiğinde `handle_event` hiç
çağrılmadığı için `bildirim_gecmisi`'ne hiçbir satır düşmüyor. Aynı desen
`app/core/handlers/physics_handler.py`'nin `.register()` metodu için de
geçerli (o da hiç çağrılmıyor) — bu, notification'a özel değil, muhtemelen
event-bus tüketicilerinin genel bir başlangıç-kablolama boşluğu. Bu taşımanın
kapsamı dışında bırakıldı (davranış değişikliği + downstream test/etki analizi
gerektirir, kullanıcı kararı gerekiyor) — sessizce atlanmadı, burada
dokümante edildi. `PushSendResult`/push akışı bundan ETKİLENMEZ (ayrı,
doğrudan çağrılan bir yol — `/push/test`, digest task, insight_engine vb.).

## Senkron konuştuğu modüller (gerekçe + tutarlılık gereksinimi)

- **auth_rbac** (senkron, in-edge): `auth.py`'nin `/password-reset-request`
  endpoint'i `send_password_reset`'i public.py üzerinden çağırır.
- **admin_platform / preference sahibi modül** (senkron, geçici out-edge):
  `domain/quiet_hours.py`'nin `is_user_quiet_now`'ı
  `app.core.services.preference_service.PreferenceService`'i doğrudan import
  eder — henüz v2'ye taşınmamış.
- **analytics_executive** (senkron, in-edge): `insight_engine.py`'nin
  `_notify_serious_alerts` fonksiyonu `send_push_broadcast`'i fonksiyon-içi
  (inline) import eder.
- **fuel modülü adayı** (senkron, in-edge): `compliance_tasks.py`
  (muayene push hatırlatma) `send_push_broadcast`'i top-level import eder.
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

- `app/api/v1/endpoints/admin_ws.py` — yalnız `/training` kaldı (admin_platform,
  henüz eski `app/` yolunda, dalga 15'e kadar).
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
- **Katman ihlali düzeltmesi**: eski `notification_service.py`,
  `app.api.v1.endpoints.admin_ws`'den `notification_ws_manager`'ı import
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
yasak — bugünkü konsolide-fonksiyon çağrıları (`insight_engine.py`,
`compliance_tasks.py` vb.) bu kurala aykırı, gate aktive olunca
`ignore_imports`'a dondurulacak (location'ın kendi CLAUDE.md'sindeki
notla aynı durum).

## Domain terimleri TR↔EN sözlüğü (FAZ3 girdisi)

`bildirim`=notification, `kural`=rule, `olay_tipi`=event_type,
`kanal`=channel, `durum`=status, `okundu`=read, `sessiz_saat`=quiet_hours,
`abonelik`=subscription.

## Modüle özel iş kuralları & gotcha'lar

- **`notification_prioritizer.py` (→ `domain/prioritizer.py`) tamamen ölü
  kod**: `NotificationPrioritizer` sınıfı hiçbir prod kod tarafından
  çağrılmıyor (yalnız kendi testlerinde kullanılıyor) — location'ın
  `LOKASYON_ADDED` event-publish'inin dead-code durumuyla aynı desen, bu
  taşımanın getirdiği bir regresyon değil.
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
  — İstisna: fonksiyon-içi (inline) importlar (`insight_engine.py`'deki
  `send_push_broadcast`, `push_to_user`'ın `is_user_quiet_now`'ı gibi) —
  bunlar KAYNAK modülden patch'lenir (`v2.modules.notification.domain.quiet_hours.is_user_quiet_now`).
