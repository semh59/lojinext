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
- [ ] admin_ws.py kararı verildi ve iki modülün de CLAUDE.md'sine + import-linter kontratına işlendi
- [ ] `notification_service.py`→`admin_ws.py` katman ihlali düzeltildi (davranışsal test bunu doğruluyor)
- [ ] 13 (veya 14, karara göre) dosya taşındı, shim tek satır
- [ ] SEFER_UPDATED/SLA_DELAY event aboneliği `events.py`'de DTO tipli
- [ ] Celery isim-uzayı testi `notifications.weekly_digest` için yeşil
