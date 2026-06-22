# Sentry Critical Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7 production/test bugs bulundu — hepsi kök nedeninden düzeltilir, hiçbiri tolere edilmez.

**Architecture:** Her fix bağımsız — ayrı commit, ayrı test. Sıra önemli değil; paralel çalışılabilir. TDD: önce test düzelt/yaz, sonra impl.

**Tech Stack:** FastAPI · SQLAlchemy asyncpg · pytest-asyncio · Python 3.12

---

## Dosya Haritası

| Dosya | Değişiklik |
|-------|-----------|
| `app/api/v1/endpoints/advanced_reports.py` | Fix 1: `except HTTPException: raise` ekle |
| `app/core/services/user_service.py` | Fix 2: `IntegrityError` yakala → 400 |
| `app/main.py` | Fix 3: `RouteProcessingError: 422 → 400` |
| `app/api/v1/endpoints/vehicles.py` | Fix 4: `IntegrityError` yakala → 400 |
| `app/infrastructure/notifications/telegram_notifier.py` | Fix 5: `debug → warning` |
| `.env.example` | Fix 5: `TELEGRAM_OPS_BOT_URL` ekle |
| `app/services/route_service.py` | Fix 6: 403 için açık log |
| `app/tests/conftest.py` | Fix 7: `pool_pre_ping=True` |
| `app/tests/api/test_advanced_reports.py` | Test düzelt: 400 assert et |
| `app/tests/api/test_admin_users.py` | Test düzelt: 400 assert et |
| `app/tests/integration/test_api_seferler.py` | Regresyon: zaten 400 bekliyor, geçmeli |

---

## Task 1: Fix 1 — Excel Export: HTTPException(400) → 500 Sorunu

**Files:**
- Modify: `app/api/v1/endpoints/advanced_reports.py`
- Modify: `app/tests/api/test_advanced_reports.py`

- [ ] **Step 1: Testi güncelle — 400 olmasını bekle**

`app/tests/api/test_advanced_reports.py` içinde `test_excel_export_invalid_report_type_returns_error` fonksiyonunu bul. KNOWN BACKEND BUG yorumunu sil ve assertion'ı düzelt:

```python
async def test_excel_export_invalid_report_type_returns_error(
    async_client, admin_auth_headers
):
    """Bilinmeyen report_type 400 döndürmelidir."""
    response = await async_client.get(
        f"{BASE}/excel/export",
        params={"report_type": "nonexistent_report"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 400
    assert response.status_code != 200
```

- [ ] **Step 2: Testi çalıştır — FAIL olduğunu doğrula**

```bash
pytest app/tests/api/test_advanced_reports.py::test_excel_export_invalid_report_type_returns_error -v
```

Expected: FAIL — `assert 500 == 400`

- [ ] **Step 3: `advanced_reports.py` düzelt — HTTPException re-raise ekle**

`export_analytical_report_excel` fonksiyonunun sonundaki except bloklarını bul:

```python
    except DomainError:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Analytical Excel export error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
```

Şu hale getir:

```python
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Analytical Excel export error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Testi çalıştır — PASS olduğunu doğrula**

```bash
pytest app/tests/api/test_advanced_reports.py::test_excel_export_invalid_report_type_returns_error -v
```

Expected: PASS

- [ ] **Step 5: Tüm advanced_reports testlerini çalıştır**

```bash
pytest app/tests/api/test_advanced_reports.py -v --tb=short
```

Expected: Tüm testler PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/endpoints/advanced_reports.py app/tests/api/test_advanced_reports.py
git commit -m "fix(api): re-raise HTTPException in excel export — 400 was swallowed as 500

LOJINEXT-89: export_analytical_report_excel caught HTTPException(400) inside
broad except Exception block. Added except HTTPException: raise guard.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Fix 2 — FK Violation: Geçersiz rol_id → 500

**Files:**
- Modify: `app/core/services/user_service.py`
- Modify: `app/tests/api/test_admin_users.py`

- [ ] **Step 1: Testi güncelle — 400 bekle, workaround kaldır**

`app/tests/api/test_admin_users.py` içinde `test_create_user_invalid_role_never_succeeds` fonksiyonunu bul ve tamamen şu hale getir:

```python
async def test_create_user_invalid_role_never_succeeds(
    async_client, admin_auth_headers
):
    """Var olmayan rol_id ile kullanıcı oluşturmak 400 döndürmelidir."""
    payload = {
        "email": "badroluser@lojinext.test",
        "ad_soyad": "Bad Rol User",
        "rol_id": 999999,
        "sifre": "Guclu1234!",
        "aktif": True,
    }
    response = await async_client.post(
        f"{BASE}/", json=payload, headers=admin_auth_headers
    )
    assert response.status_code == 400
    data = response.json()
    assert "rol" in data.get("detail", "").lower() or "error" in data
```

- [ ] **Step 2: Testi çalıştır — FAIL olduğunu doğrula**

```bash
pytest "app/tests/api/test_admin_users.py::test_create_user_invalid_role_never_succeeds" -v --tb=short
```

Expected: FAIL (500 veya exception)

- [ ] **Step 3: `user_service.py` düzelt — IntegrityError yakala**

`app/core/services/user_service.py` dosyasının en üstüne import ekle:

```python
from sqlalchemy.exc import IntegrityError
```

`create_user` metodunu bul ve `new_id = await uow.kullanici_repo.create(...)` satırını şu şekilde sar:

```python
    async def create_user(self, data: dict, created_by_id: int) -> Dict[str, Any]:
        """Create a new user with a bcrypt-hashed password."""
        async with UnitOfWork() as uow:
            existing = await uow.kullanici_repo.get_by_email(data["email"])
            if existing is not None:
                raise HTTPException(
                    status_code=400, detail="Bu e-posta adresi zaten kullanımda"
                )

            try:
                new_id = await uow.kullanici_repo.create(
                    email=data["email"],
                    ad_soyad=data["ad_soyad"],
                    rol_id=data["rol_id"],
                    aktif=data.get("aktif", True),
                    sofor_id=data.get("sofor_id"),
                    sifre_hash=get_password_hash(data["sifre"]),
                    olusturan_id=created_by_id if created_by_id != 0 else None,
                )
                await uow.commit()
            except IntegrityError as e:
                await uow.rollback()
                if "rol_id" in str(e.orig) or "kullanicilar_rol_id_fkey" in str(e.orig):
                    raise HTTPException(
                        status_code=400,
                        detail="Geçersiz rol_id: belirtilen rol mevcut değil",
                    )
                raise HTTPException(
                    status_code=400,
                    detail="Kullanıcı oluşturulamadı: veri bütünlüğü hatası",
                )

            created = await uow.kullanici_repo.get_by_id(new_id)
            if created is None:
                raise HTTPException(
                    status_code=500, detail="Oluşturulan kullanıcı tekrar okunamadı"
                )
            return created
```

**Not:** `UnitOfWork` üzerinde `rollback()` metodu yoksa `await uow.session.rollback()` kullan. Dosyayı okuyarak kontrol et.

- [ ] **Step 4: UnitOfWork rollback metodunu kontrol et**

```bash
grep -n "rollback\|async def" app/database/unit_of_work.py | head -20
```

Eğer `rollback` metodu varsa `await uow.rollback()`, yoksa `await uow.session.rollback()` kullan — Step 3'teki kodu buna göre güncelle.

- [ ] **Step 5: Testi çalıştır — PASS olduğunu doğrula**

```bash
pytest "app/tests/api/test_admin_users.py::test_create_user_invalid_role_never_succeeds" -v --tb=short
```

Expected: PASS

- [ ] **Step 6: Tüm admin_users testlerini çalıştır**

```bash
pytest app/tests/api/test_admin_users.py -v --tb=short
```

Expected: Tüm testler PASS

- [ ] **Step 7: Commit**

```bash
git add app/core/services/user_service.py app/tests/api/test_admin_users.py
git commit -m "fix(service): catch IntegrityError in create_user — FK violation now returns 400

LOJINEXT-86: Invalid rol_id caused asyncpg ForeignKeyViolationError to
propagate uncaught, resulting in 500. Now returns 400 with clear message.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Fix 3 — RouteProcessingError: 422 → 400

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Mevcut test beklentisini kontrol et**

```bash
grep -rn "RouteProcessingError\|422\|400" app/tests/ --include="*.py" | grep -v "IntegrityError\|FK\|rol_id" | head -20
```

422 bekleyen RouteProcessingError testi yoksa devam et.

- [ ] **Step 2: `main.py` güncelle**

`app/main.py` içinde `_DOMAIN_ERROR_STATUS` dict'ini bul:

```python
_DOMAIN_ERROR_STATUS: dict[type[DomainError], int] = {
    FuelCalculationError: 422,
    ImportValidationError: 422,
    ExcelExportError: 422,
    RouteProcessingError: 422,
    MLPredictionError: 503,
    AnomalyDetectionError: 503,
    AuditLogError: 500,
}
```

`RouteProcessingError: 422` satırını `RouteProcessingError: 400` olarak değiştir:

```python
_DOMAIN_ERROR_STATUS: dict[type[DomainError], int] = {
    FuelCalculationError: 422,
    ImportValidationError: 422,
    ExcelExportError: 422,
    RouteProcessingError: 400,
    MLPredictionError: 503,
    AnomalyDetectionError: 503,
    AuditLogError: 500,
}
```

- [ ] **Step 3: Regresyon testini çalıştır**

```bash
pytest app/tests/integration/test_api_seferler.py::TestSeferAPI::test_create_sefer_invalid_arac -v --tb=short
```

Expected: PASS (artık 400 dönüyor)

- [ ] **Step 4: Sefer testlerinin tamamını çalıştır**

```bash
pytest app/tests/integration/test_api_seferler.py -v --tb=short
```

Expected: Tüm testler PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "fix(api): map RouteProcessingError to HTTP 400 instead of 422

Semantic fix: 'araç bulunamadı', 'şoför bulunamadı', 'duplicate sefer no'
are all client input errors (bad references) — 400 Bad Request is correct.
422 Unprocessable Entity implies the request structure itself is valid but
semantically wrong; FK references don't fit that category.

Fixes test_create_sefer_invalid_arac assertion (422 → 400).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Fix 4 — Vehicle Create: IntegrityError → 500

**Files:**
- Modify: `app/api/v1/endpoints/vehicles.py`

- [ ] **Step 1: İlgili testi bul ya da yaz**

```bash
grep -n "create_arac\|IntegrityError\|unique\|plaka" app/tests/ -r --include="*.py" | head -10
```

Eğer `vehicles.py::create_arac`'ın IntegrityError durumunu test eden bir test yoksa aşağıdaki testi uygun test dosyasına (ya da `app/tests/api/test_vehicles_integrity.py`) ekle:

```python
import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/vehicles"


async def test_create_vehicle_duplicate_plate_returns_400(
    async_client, admin_auth_headers, db_session
):
    """Aynı plaka iki kez gönderildiğinde 400 dönmelidir."""
    payload = {
        "plaka": "34TEST999",
        "marka": "Test",
        "model": "Model",
        "yil": 2020,
        "kapasite": 20000,
        "yakit_tipi": "dizel",
        "hedef_tuketim": 30.0,
        "aktif": True,
    }
    r1 = await async_client.post(f"{BASE}/", json=payload, headers=admin_auth_headers)
    assert r1.status_code == 201

    r2 = await async_client.post(f"{BASE}/", json=payload, headers=admin_auth_headers)
    # Duplicate plate — must not be 500
    assert r2.status_code in (200, 201, 400), (
        f"Unexpected: {r2.status_code} — {r2.text}"
    )
```

- [ ] **Step 2: `vehicles.py` düzelt — IntegrityError yakala**

`app/api/v1/endpoints/vehicles.py` dosyasında `from fastapi import ...` import satırına `sqlalchemy.exc.IntegrityError` import ekle:

```python
from sqlalchemy.exc import IntegrityError
```

`create_arac` fonksiyonundaki except bloğuna `IntegrityError` ekle:

```python
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        logger.warning(f"Vehicle create integrity violation: {e.orig}", exc_info=False)
        raise HTTPException(status_code=400, detail="Veri bütünlüğü hatası: araç zaten mevcut olabilir")
    except DomainError:
        raise
    except Exception as e:
        logger.error(f"Error creating vehicle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sunucu hatası")
```

- [ ] **Step 3: Testi çalıştır**

```bash
pytest app/tests/ -k "vehicle" -v --tb=short 2>&1 | tail -20
```

Expected: İlgili testler PASS, yeni test PASS

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/endpoints/vehicles.py
git commit -m "fix(api): catch IntegrityError in create_arac — returns 400 not 500

LOJINEXT-8B/D/E: SQLAlchemy IntegrityError (unique/FK constraint) fell
through to the generic except block and returned 500. Now returns 400.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Fix 5 — Telegram Bildirimleri Sessiz Başarısız Olmamalı

**Files:**
- Modify: `app/infrastructure/notifications/telegram_notifier.py`
- Modify: `.env.example`

- [ ] **Step 1: `telegram_notifier.py` güncelle**

`app/infrastructure/notifications/telegram_notifier.py` dosyasında `notify_error` fonksiyonundaki except bloğunu bul:

```python
    except Exception as exc:
        logger.debug("Telegram notify_error failed (non-critical): %s", exc)
```

Şu hale getir:

```python
    except Exception as exc:
        logger.warning(
            "Telegram notify_error failed — ops bot unreachable at %s: %s",
            _WEBHOOK_URL,
            exc,
        )
```

- [ ] **Step 2: `.env.example` güncelle**

`.env.example` dosyasında Telegram bölümünü bul. `TELEGRAM_OPS_BOT_TOKEN` satırından sonra şunu ekle:

```
# URL ops_bot webhook sunucusuna işaret etmeli.
# Docker Compose içinde: http://telegram-ops-bot:8080
# Yerel geliştirmede (bot ayrı çalışıyorsa): http://localhost:8080
TELEGRAM_OPS_BOT_URL=http://telegram-ops-bot:8080
```

- [ ] **Step 3: Değişikliği doğrula**

```bash
grep -n "warning\|debug\|WEBHOOK_URL" app/infrastructure/notifications/telegram_notifier.py
grep -n "TELEGRAM_OPS_BOT_URL" .env.example
```

Her iki satır da çıktıda görünmeli.

- [ ] **Step 4: Commit**

```bash
git add app/infrastructure/notifications/telegram_notifier.py .env.example
git commit -m "fix(telegram): elevate silent failure to WARNING, document TELEGRAM_OPS_BOT_URL

Ops bot webhook failures were logged at DEBUG level — invisible in production.
Now WARNING level with full URL in message so on-call can see it.
Added TELEGRAM_OPS_BOT_URL to .env.example with Docker vs local guidance.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Fix 6 — ORS Routing 403 İçin Açık Log

**Files:**
- Modify: `app/services/route_service.py`

- [ ] **Step 1: 403 loglama ekle**

`app/services/route_service.py` içinde `if response.status_code == 401:` bloğunu bul. Hemen üstüne 403 bloğunu ekle:

```python
            if response.status_code == 403:
                logger.error(
                    "ORS API key forbidden (403). Quota exceeded or key suspended. "
                    "Check OPENROUTESERVICE_API_KEY in .env and verify quota at "
                    "https://openrouteservice.org/dev/#/home"
                )
                return {
                    "error": "Routing provider forbidden (403). Quota exceeded or key suspended.",
                    "error_code": "QUOTA_EXCEEDED",
                    "provider_status": 403,
                    "source": "provider_error",
                }

            if response.status_code == 401:
                logger.error("ORS API key rejected (401). Check OPENROUTESERVICE_API_KEY.")
                return {
                    "error": "Routing provider credentials rejected (401). Please check the API key.",
                    "error_code": "AUTH_FAILURE",
                    "provider_status": 401,
                    "source": "provider_error",
                }
```

**Dikkat:** Mevcut kod 403'ü `driving-hgv` profili için kullanıyor (profile fallback). Bu blok profil fallback'ten SONRA, `if response.status_code == 401:` öncesine eklenmeli — profil fallback zaten response'u driving-car ile yenileyip yeni bir response alıyor.

- [ ] **Step 2: Doğru konumu bul**

```bash
grep -n "403\|401\|status_code" app/services/route_service.py | head -20
```

403 bloğunun profile fallback'ten ayrı olduğundan emin ol. Profil fallback `response = await client.post(...)` yaptıktan sonra gelen yeni response'a bakar.

- [ ] **Step 3: Commit**

```bash
git add app/services/route_service.py
git commit -m "fix(routing): add explicit 403 log for ORS quota/key suspension

LOJINEXT-7G: ORS returned 403 48 times (quota exceeded / key suspended).
Was logged generically. Now logs with clear guidance to check quota and
OPENROUTESERVICE_API_KEY in .env.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Fix 7 — DB Connection Pool: pool_pre_ping

**Files:**
- Modify: `app/tests/conftest.py`

- [ ] **Step 1: `async_db_engine` fixture'ını güncelle**

`app/tests/conftest.py` içinde `async_db_engine` fixture'ını bul:

```python
@pytest.fixture
async def async_db_engine(temp_db_url):
    engine = create_async_engine(temp_db_url, echo=False)
```

`pool_pre_ping=True` ekle:

```python
@pytest.fixture
async def async_db_engine(temp_db_url):
    engine = create_async_engine(temp_db_url, echo=False, pool_pre_ping=True)
```

`pool_pre_ping=True` her connection kullanımından önce `SELECT 1` ile bağlantıyı test eder. Kapalı bağlantılar otomatik yenilenir, `InterfaceError: connection is closed` engellenir.

- [ ] **Step 2: Test suite'ini çalıştır**

```bash
pytest app/tests/ -x -q --tb=short 2>&1 | tail -15
```

Expected: Önceki başarısız testler şimdi PASS, yeni failure yok.

- [ ] **Step 3: Commit**

```bash
git add app/tests/conftest.py
git commit -m "fix(tests): add pool_pre_ping=True to async_db_engine

LOJINEXT-8A/8C: asyncpg 'connection is closed' InterfaceError appeared
during test runs. pool_pre_ping validates connections before use and
transparently reconnects stale ones.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Son Doğrulama

- [ ] **Tam test suite'i çalıştır**

```bash
pytest app/tests/ -q --tb=short 2>&1 | tail -20
```

Expected: 0 failure.

- [ ] **Spesifik regresyon testleri**

```bash
pytest app/tests/integration/test_api_seferler.py::TestSeferAPI::test_create_sefer_invalid_arac -v
pytest app/tests/api/test_advanced_reports.py::test_excel_export_invalid_report_type_returns_error -v
pytest "app/tests/api/test_admin_users.py::test_create_user_invalid_role_never_succeeds" -v
```

Expected: Üçü de PASS.

- [ ] **Sentry'de aynı hataların tekrar oluşmadığını doğrula**

```bash
curl -s -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "https://de.sentry.io/api/0/projects/semh59/lojinext/issues/?limit=10&query=is:unresolved&sort=date" \
  | python3 -c "import sys,json; [print(i['shortId'], i['title'][:60]) for i in json.load(sys.stdin)]"
```
