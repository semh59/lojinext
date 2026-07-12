# Modül Görevi: admin_platform (dalga 15/17)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/modules/admin_platform/CLAUDE.md`'yi Read ile oku.

**Giriş kriteri:** trip dalgası tamamlandı. **Çıkış kriteri:** import-linter kontratı yeşil.

---

## 1. Dosya envanteri (26 dosya, 3.718 LOC)
```
app/api/v1/endpoints/admin_config.py
app/api/v1/endpoints/admin_integrations.py
app/api/v1/endpoints/admin_health.py
app/api/v1/endpoints/admin_ws.py
app/api/v1/endpoints/error_stream.py
app/api/v1/endpoints/health.py
app/api/v1/endpoints/internal.py
app/api/v1/endpoints/system.py
app/core/services/admin_audit_service.py
app/core/services/konfig_service.py
app/core/services/runtime_config.py
app/core/services/health_service.py
app/core/services/internal_service.py
app/core/services/idempotency_service.py
app/core/services/integration_secrets.py
app/database/repositories/admin_config_repo.py
app/database/repositories/config_repo.py
app/database/repositories/audit_repo.py
app/database/repositories/setting_repository.py
app/core/integrations/__init__.py
app/core/integrations/avl/__init__.py
app/core/integrations/avl/base.py
app/core/integrations/avl/mobiliz.py
app/core/integrations/registry.py
app/workers/tasks/backup_tasks.py
app/workers/tasks/error_digest.py
```
**AÇIK NOT (notification.md ile çapraz-referanslı):** `admin_ws.py`'nin 2 route'u işlevsel olarak notification modülüne ait (WebSocket bildirim köprüsü) ama dosya-içerik taraması burada bıraktı. notification dalgasında (2) bu karar verildiyse, burada YİNE UYGULANIR — iki dosya senkron güncellenir. Karar verilmediyse, bu dalgada içerik okunarak (`app/api/v1/endpoints/admin_ws.py` full read) kesinleştirilir.

## 2. Route envanteri (25 route)
`admin_config.py`(3) + `admin_integrations.py`(2) + `admin_health.py`(3) + `system.py`(7) + `internal.py`(7) + `health.py`(1) + `error_stream.py`(2) = 25. (`admin_ws.py`(2) madde 1'deki karara göre buradan çıkabilir.)

## 3. Tablo sahipliği (2 tablo) — ✅ FAZ0 KARARI UYGULANDI
`admin_audit_log`, `entegrasyon_ayarlari`. `iceri_aktarim_gecmisi` bu modülde DEĞİL — FAZ0 kararıyla import_excel'e taşındı (bkz. import-excel.md §3; kanıt: repository+tek okuyucu zaten import_excel'de, admin_platform'da hiç kullanım yok).

## 4. Bağlaşıklık karnesi
- **out (yüksek — 18 statement):** admin_platform→auth_rbac 7 (en yoğun — `permission_checker.py` her admin endpoint'inde), admin_platform→driver 3, admin_platform→fuel 2, admin_platform→notification 2, admin_platform→import_excel 1, admin_platform→trip 1, admin_platform→fleet 1, admin_platform→ai_assistant 1
- **in:** route_simulation→admin_platform 4, fuel→admin_platform 3, prediction_ml→admin_platform 2, anomaly→admin_platform 2, trip→admin_platform 1, location→admin_platform 1, notification→admin_platform 1
- `internal.py` + `internal_service.py`: bağımsız doğrulama ajanının notu — bu ikili gerçekte Docker-internal Telegram-bot köprüsü, ağırlıklı olarak driver-yüzlü (belge upload, coaching snapshot, sofor seferler, PDF) + bot-token bootstrap. Tek-modüle temiz oturmuyor; admin_platform savunulabilir ama not edilir — `TASKS/modules/driver.md`'ye çapraz-referans, gelecekte ayrı bir "integration-bridge" modülü gerekirse bu ikili aday.

## 5. Taşıma adımları
1. İskelet + `admin_ws.py` kararını uygula (madde 1).
2. `admin_config_repo.py`, `config_repo.py`, `audit_repo.py`, `setting_repository.py` → `infrastructure/repository.py` (4 ayrı dosya).
3. `konfig_service.py`, `runtime_config.py` → `application/` (sistem_konfig CRUD — proje hafızası `runtime_config_epic`'teki "yalancı-UI ilkesi" korunur, davranış değişmez).
4. `health_service.py`, `admin_audit_service.py`, `idempotency_service.py`, `integration_secrets.py` → `application/`.
5. `internal_service.py` → `application/telegram_bridge.py` (madde 4'teki not CLAUDE.md'ye taşınır).
6. `core/integrations/avl/*` (Mobiliz AVL entegrasyonu) → `infrastructure/integrations/avl/`.
7. `backup_tasks.py`, `error_digest.py` → `infrastructure/tasks.py`.
8. Shim'ler + CLAUDE.md.

## 6. Kabul kriterleri
- [ ] admin_ws.py kararı notification.md ile TUTARLI uygulandı
- [ ] 25 (veya 26/24, karara göre) dosya taşındı
- [ ] iceri_aktarim_gecmisi FAZ0 kararı burada da tutarlı
- [ ] internal.py/internal_service.py notu CLAUDE.md'de dokümante
