# Modül Görevi: notification (dalga 2/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/notification/CLAUDE.md`'yi Read ile oku (yoksa bu görev madde 7'de oluşturur).

**Giriş kriteri:** location dalgası tamamlandı (taşıma deseni kanıtlandı). **Çıkış kriteri:** import-linter kontratı yeşil, slice+entegrasyon testleri geçiyor.

---

## 1. Dosya envanteri (13 dosya, 1.330 LOC)
```
app/api/v1/endpoints/push.py
app/api/v1/endpoints/admin_notifications.py
app/core/services/notification_service.py
app/core/services/notification_prioritizer.py
app/core/services/push_sender.py
app/core/services/quiet_hours.py
app/core/services/email_service.py
app/database/repositories/notification_repository.py
app/schemas/push.py
app/schemas/telegram.py
app/infrastructure/notifications/__init__.py
app/infrastructure/notifications/telegram_notifier.py
app/workers/tasks/notification_tasks.py
```

## 2. Route envanteri + AÇIK NOT
`push.py`(4) + `admin_notifications.py`(5) = 9 route yukarıdaki dosya listesinde. Ancak MEMORY/PROGRESS.md §2.1 route toplamı (232) doğrulaması notification modülüne **11** route atıyor — fark **`app/api/v1/endpoints/admin_ws.py`**'nin 2 route'undan geliyor. `admin_ws.py` dosya-içerik taramasında admin_platform'a atanmış (26 dosyalık listede), ama fonksiyonel olarak bildirim WebSocket köprüsü. **Bu bir çözülmemiş sınır kararıdır — varsayılmadı:** FAZ0/bu dalgada içerik okunarak (`app/api/v1/endpoints/admin_ws.py` full read) karar verilecek: (a) dosya notification'a taşınır (route sayısı planla tutar, admin_platform 26→25 dosya) veya (b) admin_platform'da kalır ve notification→admin_platform senkron bağımlılığı olarak kontrata girer. Karar bu bölüme işlenir, iki modülün de import-linter kontratına yansıtılır.

## 3. Tablo sahipliği
`bildirim_kurallari`, `bildirim_gecmisi`, `push_subscriptions` (3 tablo).

## 4. Bağlaşıklık karnesi
- **out:** notification→auth_rbac 2, notification→admin_platform 1
- **in:** admin_platform→notification 2, ai_assistant→notification 1, trip→notification 1, analytics_executive→notification 2, auth_rbac→notification 1, fuel→notification 1
- Celery: `notification_tasks.py` (1 task: `notifications.weekly_digest`, beat mon 08:00 UTC). Event subscriber: `notification_service.py` satır 27-28 `SEFER_UPDATED`+`SLA_DELAY` dinliyor (`handle_event` via `register_handlers`) — bu 2 event, trip modülünden asenkron geliyor (MEMORY §2.3 asenkron liste ile tutarlı).
- **Gerçek katman ihlali (MEMORY §2.1'de tespit edildi):** `notification_service.py` → `endpoints/admin_ws.py` (servis→endpoint import). Bu taşıma sırasında DÜZELTİLİR: admin_ws'in WebSocket broadcast fonksiyonu `notification/infrastructure/ws_broadcaster.py`'ye taşınır, notification_service oradan çağırır (endpoint'ten değil).

## 5. Taşıma adımları
1. İskelet oluştur; `admin_ws.py` kararını (madde 2) uygula.
2. `notification_repository.py` → `infrastructure/repository.py`.
3. `notification_service.py`'nin event-subscriber kısmı → `events.py` + `application/handle_trip_events.py`; `admin_ws` ihlali burada çözülür.
4. `push_sender.py`, `quiet_hours.py`, `email_service.py`, `notification_prioritizer.py` → `domain/` (saf iş kuralı; I/O'suz kısımlar) + `infrastructure/` (gönderim adaptörleri) ayrımı.
5. `telegram_notifier.py` → `infrastructure/telegram_client.py` (dış API istemcisi).
6. `notification_tasks.py` → `infrastructure/tasks.py`; Celery isim-uzayı testi (`faz1-davranissal-mimari-testler.md` madde 5) burada `notifications.weekly_digest` girdisini alır.
7. `app/modules/notification/CLAUDE.md` doldurulur.

## 6. Kabul kriterleri
- [x] admin_ws.py kararı verildi ve iki modülün de CLAUDE.md'sine + import-linter kontratına işlendi
      — üçüncü bir seçenek çıktı (madde 2'nin (a)/(b) varsayımı yanlıştı): dosya
      İKİ bağımsız route içeriyordu (`/training` admin_platform, `/live`
      notification). Dosyanın kendisi bölündü; paylaşılan `ConnectionManager`+
      WS-auth helper'ları `app/infrastructure/websocket/` altına (event_bus ile
      aynı gerekçeyle) gerçek shared-infra olarak çıkarıldı. Karar +
      import-linter notu `v2/modules/notification/CLAUDE.md`'de. admin_platform
      henüz taşınmadığı için kendi CLAUDE.md'si yok — dalga 15'te işlenecek.
- [x] `notification_service.py`→`admin_ws.py` katman ihlali düzeltildi (davranışsal test bunu doğruluyor)
      — `handle_trip_events.py` artık kendi modülünün `ws_broadcaster.py`'sinden
      import ediyor, hiçbir endpoint dosyasına bağımlı değil.
- [x] 13 (veya 14, karara göre) dosya taşındı, shim tek satır YOK (location'daki
      "shim bile yok" kararıyla aynı) — **gerçek sayı 12**: `schemas/telegram.py`
      taşıma sırasında incelendiğinde notification'a değil trip/telegram-bot
      DTO'larına ait çıktı (tüketicileri `internal.py`/`trips.py`, notification'ın
      kendi dosyalarının hiçbiri değil) — varsayılan 13'ten çıkarıldı, taşınmadı.
      admin_ws.py'nin `/live` route'u (13. dosyanın YARISI) ayrıca taşındı.
- [x] SEFER_UPDATED/SLA_DELAY event aboneliği `events.py`'de DTO tipli
      (`SeferUpdatedPayload`/`SlaDelayPayload`, tüm alanlar Optional — 4 farklı
      trip-modülü publish call-site'ı hafif farklı payload şekli gönderiyor)
- [x] Celery isim-uzayı testi `notifications.weekly_digest` için yeşil
      (`test_celery_app_config.py` + `test_weekly_digest_task.py`, container'da
      gerçek koşum: 24/24 pass)

**🔴 Kapsam dışı bırakılan kritik keşif** (bkz. CLAUDE.md): `register_handlers()`
hiçbir yerde çağrılmıyor — event-subscriber pipeline PROD'da hiç tetiklenmiyor.
Taşımanın getirdiği bir regresyon değil, öncesinde de böyleydi; davranış
değişikliği gerektirdiği için bu dalganın kapsamına alınmadı, kullanıcıya
raporlandı.

**Doğrulama (gerçek Docker container, gerçek pytest koşumu, 2026-07-13):**
ruff temiz (host kaynağına karşı, `python:3.12-slim` + mount), `mypy app/`
7/7 baseline (regresyon yok), `pytest --collect-only` 6767 test/0 hata,
notification'a özgü 24 dosya (yeni+değişen) gerçek `lojinext_test` DB'sine
karşı **194/194 pass** (159 unit + 11 integration/N+1/IDOR + 24 kök-`tests/`
ve dokunulan-tüketici regresyon seti), OpenAPI şema drift YOK (websocket
route'ları zaten şemada yok). Yan bulgu: Docker C-sürücüsü doluydu (bilinen
gotcha, kullanıcı onayıyla kurtarma reçetesi uygulandı, ~87GB host alanı
geri kazanıldı).
