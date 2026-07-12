# Modül Görevi: auth_rbac (dalga 6/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/auth_rbac/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** driver dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil; `out=1/in=17` profiliyle EN SAĞLIKLI sağlayıcı — kimlik/permission her modülün bağımlı olduğu temel katman.

---

## 1. Dosya envanteri (21 dosya, 2.331 LOC)
```
app/api/v1/endpoints/auth.py
app/api/v1/endpoints/users.py
app/api/v1/endpoints/admin_users.py
app/api/v1/endpoints/admin_roles.py
app/api/v1/endpoints/preferences.py
app/api/v1/endpoints/ws_ticket.py
app/core/services/auth_service.py
app/core/services/user_service.py
app/core/services/security_service.py
app/core/services/license_service.py
app/core/services/preference_service.py
app/core/security.py
app/database/repositories/kullanici_repo.py
app/database/repositories/rol_repo.py
app/database/repositories/session_repo.py
app/schemas/user.py
app/schemas/preference.py
app/infrastructure/security/jwt_handler.py
app/infrastructure/security/permission_checker.py
app/infrastructure/security/token_blacklist.py
app/scripts/create_admin.py
```

## 2. Route envanteri (25 route)
`auth.py`(6) + `users.py`(4) + `admin_users.py`(5) + `admin_roles.py`(5) + `preferences.py`(4) + `ws_ticket.py`(1) = 25.

## 3. Tablo sahipliği (4 tablo)
`kullanicilar`, `roller`, `kullanici_oturumlari`, `kullanici_ayarlari`. **`kullanicilar` sistemin en büyük FK mıknatısı — ~28 inbound çapraz-şema kenar** (her modülün audit/creator/updater/resolver kolonu buraya bağlı). FAZ2'de bu, auth_rbac şemasına en yoğun SELECT-only grant talebini getirecek — rol matrisinde özel olarak işaretlenir.

## 4. Bağlaşıklık karnesi
- **out (yalnız 1!):** auth_rbac→notification 1
- **in (17):** admin_platform→auth_rbac 7 (en yoğun — `admin_attribution.py`/`admin_config.py`/`admin_health.py`→`permission_checker.py`), notification→auth_rbac 2, analytics_executive→auth_rbac 2, anomaly→auth_rbac 1, route_simulation→auth_rbac 1, import_excel→auth_rbac 1, fleet→auth_rbac 1, prediction_ml→auth_rbac 1, trip→auth_rbac 1
- **B.2 pairwise kararı:** `*→auth_rbac` HER ZAMAN senkron (kimlik/permission çözümü anlık olmalı); audit-actor id'leri (created_by_id vb.) DEĞER olarak taşınır, join gerektirmez — bu yüzden 28 FK kenarına rağmen runtime çağrı sayısı düşük kalır.
- **Multi-worker güvenlik state'i** (MEMORY §4.1) bu modülün SINIRLARI İÇİNDE ama ÇÖZÜMÜ FAZ2'de ayrı görev (`faz2-guvenlik-state-redis.md`): `BruteForceDetector`/`RBACViolationTracker` bugün `security_probe.py`'de (platform-infra), auth_rbac'a taşınmaz — cross-cutting infra olarak kalır, yalnız Redis-backed hale gelir.

## 5. Taşıma adımları
1. İskelet + `kullanici_repo.py`/`rol_repo.py`/`session_repo.py` → `infrastructure/repository.py` (3 ayrı dosya).
2. `auth_service.py`, `security.py`, `jwt_handler.py`, `token_blacklist.py`, `permission_checker.py` → `domain/` (token/permission mantığı I/O-hafif).
3. `user_service.py`, `preference_service.py` → `application/` CRUD use-case'leri.
4. `license_service.py` → `application/check_license.py` (admin_platform ile ilişkisi var, ama kod içeriği auth kontrolü — burada kalır).
5. `ws_ticket.py` → `api/ws_ticket_routes.py` (WebSocket kimlik doğrulama bileti).
6. `create_admin.py` script'i → `scripts/` içinde kalır (dış yazar, A.4/§5'te "16 DB-script"in biri), yalnız import yolu güncellenir.
7. Shim'ler + CLAUDE.md — bu modülün CLAUDE.md'sinde "Şema & tablo sahipliği" bölümü 28 inbound FK'yı özellikle vurgular (FAZ2 rol tasarımı için kritik referans).

## 6. Kabul kriterleri
- [ ] 21 dosya taşındı
- [ ] `out=1` kontratı korunuyor (yeni cross-module import eklenmedi)
- [ ] 28 inbound FK, fk_registry.yml taslağına (FAZ2 için) not düşüldü
- [ ] Multi-worker güvenlik state'i BURADA çözülmedi, açıkça FAZ2'ye ertelendi (TODO işaretli)
