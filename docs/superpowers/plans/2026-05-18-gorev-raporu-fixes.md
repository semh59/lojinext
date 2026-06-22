# LojiNext Görev Raporu — Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Doğrulanan 12 güvenlik/kalite sorununu öncelik sırasına göre düzelt; yanlış teşhis edilen Bölüm 7'yi (nav linkleri zaten mevcut) atla.

**Architecture:** Önce production güvenliği (auth, Redis, cache), sonra backend kalitesi (utility, repository, N+1), son olarak frontend ve izleme katmanları. Her task kendi commit'iyle biter.

**Tech Stack:** FastAPI · SQLAlchemy 2 async · Redis · Celery · React/TypeScript · Zod · Vitest · pytest-asyncio · Docker Compose

---

## Doğrulama Notları

- **Bölüm 7 ATLANMIŞ** — EliteLayout.tsx L141 ve L156'da `/monitoring` ve `/predictions` nav linkleri zaten mevcut. Rapor hatalıydı.
- **Bölüm 9 REVİZE** — `docker-compose.prod.yml` Redis servisi zaten `mem_limit: 512m` içeriyor. Eksik olan: Redis `--maxmemory 512mb --maxmemory-policy allkeys-lru` flag'leri ve healthcheck.
- **Bölüm 12 ve 14 ERTELENMİŞ** — Yüksek risk, ayrı planlama gerektirir.

---

## Dosya Haritası

**Oluşturulacak:**
- `app/core/utils/type_helpers.py` — safe_float utility
- `app/core/utils/__init__.py` — paket init
- `app/tests/unit/test_type_helpers.py` — utility testleri
- `app/tests/api/test_admin_users.py` — admin user endpoint testleri
- `app/tests/api/test_admin_ml.py` — admin ML endpoint testleri
- `app/tests/api/test_advanced_reports.py` — rapor endpoint testleri
- `frontend/src/types/prediction.ts` — prediction request tipleri

**Değiştirilecek:**
- `app/core/services/sefer_write_service.py` — `_safe_float` kaldır
- `app/services/prediction_service.py` — `_safe_float` kaldır
- `app/infrastructure/cache/cache_manager.py` — Redis'e geçiş
- `app/database/repositories/kullanici_repo.py` — `get_by_rol_ids` bulk metod
- `app/core/services/notification_service.py` — N+1 düzelt
- `app/database/repositories/rol_repo.py` — BaseRepository'den türet, commit → flush
- `app/database/unit_of_work.py` — `rol_repo` lazy property ekle
- `app/api/v1/endpoints/auth.py` — logout güvenlik düzeltmesi
- `frontend/src/services/api/prediction-service.ts` — `any` tiplerini kaldır
- `frontend/src/services/api/preference-service.ts` — `any` tiplerini kaldır
- `app/workers/tasks/driver_tasks.py` — retry ekle
- `app/workers/tasks/outbox_tasks.py` — retry ekle
- `frontend/src/components/predictions/XaiPanel.tsx` — ensemble ağırlıkları göster
- `frontend/src/pages/DashboardPage.tsx` — `in_progress_count` KPI ekle
- `docker-compose.prod.yml` — Redis `--maxmemory` flag + healthcheck
- `docker-compose.yml` — dev Redis `--maxmemory` flag (zaten var, doğrula)
- `grafana/dashboards/lojinext.json` — eski metrik adlarını güncelle

---

## HAFTA 1 — Production Güvenliği

### Task 1: Auth Logout Güvenlik Düzeltmesi (Bölüm 5)

**Files:**
- Modify: `app/api/v1/endpoints/auth.py:118-140`

- [ ] **Step 1: Mevcut logout kodunu oku**

```bash
sed -n '118,145p' app/api/v1/endpoints/auth.py
```

- [ ] **Step 2: Failing test yaz**

`app/tests/api/test_auth_logout.py` oluştur (dosya yoksa):

```python
import pytest
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio

async def test_logout_blacklist_failure_returns_warning(async_client, user_auth_headers):
    """Blacklist başarısız olursa kullanıcı uyarı almalı, 200 dönmeli."""
    with patch(
        'app.infrastructure.security.token_blacklist.blacklist.add',
        side_effect=Exception("Redis down"),
    ):
        response = await async_client.post(
            "/api/v1/auth/logout", headers=user_auth_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert "warning" in data
    assert "token" in data["warning"].lower()

async def test_logout_blacklist_failure_revokes_session(async_client, user_auth_headers):
    """Blacklist başarısız olursa session yine de iptal edilmeli."""
    with patch(
        'app.infrastructure.security.token_blacklist.blacklist.add',
        side_effect=Exception("Redis down"),
    ) as _, patch(
        'app.core.services.auth_service.AuthService.revoke_session',
        new_callable=AsyncMock,
    ) as mock_revoke:
        await async_client.post("/api/v1/auth/logout", headers=user_auth_headers)
    mock_revoke.assert_called_once()
```

- [ ] **Step 3: Testi çalıştır — FAIL bekleniyor**

```bash
pytest app/tests/api/test_auth_logout.py -v --tb=short
```

- [ ] **Step 4: `auth.py` logout exception handler'ı güncelle**

Şu anki kod (`app/api/v1/endpoints/auth.py` ~L134):
```python
    except Exception as e:
        logger.error(f"Failed to blacklist token during logout: {e}")
    await auth_service.revoke_session(current_user.id)
```

Yeni kod:
```python
    except Exception as e:
        logger.error(f"Failed to blacklist token during logout: {e}")
        await auth_service.revoke_session(current_user.id)
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")
        return {
            "detail": "Logged out",
            "warning": "Token blacklist unavailable — token may remain valid until expiry",
        }
    await auth_service.revoke_session(current_user.id)
```

- [ ] **Step 5: Testi çalıştır — PASS bekleniyor**

```bash
pytest app/tests/api/test_auth_logout.py -v
```

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/endpoints/auth.py app/tests/api/test_auth_logout.py
git commit -m "fix(auth): return warning when token blacklist fails during logout"
```

---

### Task 2: Redis `--maxmemory` Flag (Bölüm 9)

**Files:**
- Modify: `docker-compose.prod.yml` (redis service command)
- Verify: `docker-compose.yml` (dev — zaten var)

- [ ] **Step 1: Prod Redis komutunu oku**

```bash
grep -A 10 "^  redis:" docker-compose.prod.yml
```

Beklenen: `command: redis-server --requirepass ... --appendonly yes` — `--maxmemory` YOK.

- [ ] **Step 2: Dev docker-compose'u doğrula (değişiklik gerekmez)**

```bash
grep "maxmemory" docker-compose.yml
```

Beklenen: `--maxmemory 256mb --maxmemory-policy allkeys-lru` — zaten var.

- [ ] **Step 3: Prod Redis komutunu güncelle**

`docker-compose.prod.yml` içinde Redis `command:` satırını şu şekilde değiştir:

```yaml
  redis:
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD:?REDIS_PASSWORD must be set in prod}
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --save 60 1000
    mem_limit: 512m
    memswap_limit: 512m
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

- [ ] **Step 4: Syntax doğrula**

```bash
docker compose -f docker-compose.prod.yml config > /dev/null && echo "OK"
```

Beklenen: `OK`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "fix(infra): add Redis maxmemory limit and healthcheck to prod compose"
```

---

### Task 3: CacheManager → Redis (Bölüm 2)

**Files:**
- Modify: `app/infrastructure/cache/cache_manager.py`

> ⚠️ Test ortamında `CacheManager` mock'lanıyor mu kontrol et: `grep -rn "CacheManager\|cache_manager" app/tests/` — mock varsa test değişmez, yoksa test Redis'e bağlanmaya çalışır.

- [ ] **Step 1: Mevcut CacheManager'ı oku**

```bash
cat -n app/infrastructure/cache/cache_manager.py
```

- [ ] **Step 2: Failing test yaz**

`app/tests/unit/test_cache_manager_redis.py` oluştur:

```python
import pytest
from unittest.mock import MagicMock, patch
import pickle

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_redis():
    r = MagicMock()
    r.get.return_value = None
    return r

@pytest.fixture
def cache_manager(mock_redis):
    with patch('redis.from_url', return_value=mock_redis):
        from app.infrastructure.cache.cache_manager import CacheManager
        cm = CacheManager()
        cm._redis = mock_redis
        return cm, mock_redis

def test_set_calls_redis_setex(cache_manager):
    cm, mock_redis = cache_manager
    cm.set("key1", {"val": 42}, ttl_seconds=60)
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    assert "cm:key1" in args[0]
    assert args[1] == 60
    assert pickle.loads(args[2]) == {"val": 42}

def test_get_returns_none_on_cache_miss(cache_manager):
    cm, mock_redis = cache_manager
    mock_redis.get.return_value = None
    assert cm.get("missing_key") is None

def test_get_returns_value_on_hit(cache_manager):
    cm, mock_redis = cache_manager
    mock_redis.get.return_value = pickle.dumps({"data": "ok"})
    result = cm.get("key1")
    assert result == {"data": "ok"}

def test_delete_calls_redis_delete(cache_manager):
    cm, mock_redis = cache_manager
    mock_redis.delete.return_value = 1
    assert cm.delete("key1") is True

def test_stats_hit_miss_counted(cache_manager):
    cm, mock_redis = cache_manager
    mock_redis.get.return_value = None
    cm.get("miss_key")
    mock_redis.get.return_value = pickle.dumps("val")
    cm.get("hit_key")
    stats = cm.get_stats()
    assert stats["misses"] >= 1
    assert stats["hits"] >= 1
```

- [ ] **Step 3: Testi çalıştır — FAIL bekleniyor**

```bash
pytest app/tests/unit/test_cache_manager_redis.py -v --tb=short
```

- [ ] **Step 4: CacheManager'ı Redis'e geçir**

`app/infrastructure/cache/cache_manager.py` dosyasını yeniden yaz. Kritik noktalar:
- `__init__`: `self._cache: dict` → `self._redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=False)`
- `set`: `self._cache[key]` → `self._redis.setex(f"cm:{key}", ttl_seconds, pickle.dumps(value))`
- `get`: `self._cache.get(key)` → `pickle.loads(self._redis.get(f"cm:{key}"))`
- `delete`: `del self._cache[key]` → `self._redis.delete(f"cm:{key}")`
- `delete_pattern`: `fnmatch` loop → `self._redis.scan_iter(f"cm:{pattern}")` loop
- `clear`: `self._cache.clear()` → `scan_iter("cm:*")` loop
- Stats (`hits`, `misses`, `sets`) hâlâ `self._lock` korumasında in-memory `_stats` dict'te tutulabilir
- `_evict_if_needed` ve `_cleanup_expired` metodlarını kaldır (Redis TTL halleder)
- `MAX_CACHE_SIZE` sabitini kaldır

Dosyanın yeni içeriği:

```python
"""Application-level cache backed by Redis."""
import pickle
import threading
from typing import Any, Dict, Optional

import redis as redis_lib

from app.config import settings


class CacheManager:
    def __init__(self) -> None:
        self._redis = redis_lib.from_url(settings.REDIS_URL, decode_responses=False)
        self._lock = threading.Lock()
        self._stats: Dict[str, int] = {"hits": 0, "misses": 0, "sets": 0}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._validate_key(key)
        self._redis.setex(f"cm:{key}", ttl_seconds, pickle.dumps(value))
        with self._lock:
            self._stats["sets"] += 1

    def get(self, key: str) -> Optional[Any]:
        self._validate_key(key)
        raw = self._redis.get(f"cm:{key}")
        with self._lock:
            if raw is None:
                self._stats["misses"] += 1
                return None
            self._stats["hits"] += 1
        return pickle.loads(raw)  # noqa: S301

    def delete(self, key: str) -> bool:
        self._validate_key(key)
        return self._redis.delete(f"cm:{key}") > 0

    def delete_pattern(self, pattern: str) -> int:
        count = 0
        for k in self._redis.scan_iter(f"cm:{pattern}"):
            self._redis.delete(k)
            count += 1
        return count

    def clear(self) -> None:
        for k in self._redis.scan_iter("cm:*"):
            self._redis.delete(k)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._stats)

    def keys(self, pattern: str = "*") -> list:
        return [
            k.decode().removeprefix("cm:") if isinstance(k, bytes) else k.removeprefix("cm:")
            for k in self._redis.scan_iter(f"cm:{pattern}")
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_key(key: str) -> None:
        if not key or not isinstance(key, str):
            raise ValueError(f"Cache key must be a non-empty string, got: {key!r}")
```

- [ ] **Step 5: Testi çalıştır — PASS bekleniyor**

```bash
pytest app/tests/unit/test_cache_manager_redis.py -v
```

- [ ] **Step 6: Mevcut cache testlerinin hâlâ geçtiğini doğrula**

```bash
pytest app/tests/ -k "cache" --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add app/infrastructure/cache/cache_manager.py app/tests/unit/test_cache_manager_redis.py
git commit -m "feat(cache): migrate CacheManager from in-memory dict to Redis backend"
```

---

### Task 4: Admin Endpoint Testleri (Bölüm 8)

**Files:**
- Create: `app/tests/api/test_admin_users.py`
- Create: `app/tests/api/test_admin_ml.py`
- Create: `app/tests/api/test_advanced_reports.py`

- [ ] **Step 1: Mevcut admin test dosyalarını gör**

```bash
ls app/tests/api/
grep -rn "admin" app/tests/api/ --include="*.py" -l
```

- [ ] **Step 2: `test_admin_users.py` yaz**

```python
"""Admin user endpoint integration tests."""
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_create_user_sets_olusturan_id(async_client, admin_auth_headers, admin_user):
    """Oluşturan ID 0 değil gerçek admin ID olmalı."""
    response = await async_client.post(
        "/api/v1/admin/users/",
        headers=admin_auth_headers,
        json={
            "kullanici_adi": "newtestuser",
            "email": "newtestuser@loji.test",
            "sifre": "Secure1234!",
            "rol_id": 1,
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["olusturan_id"] == admin_user.id


async def test_create_user_invalid_rol_returns_422(async_client, admin_auth_headers):
    """Olmayan rol ID'si 500 değil 422 dönmeli."""
    response = await async_client.post(
        "/api/v1/admin/users/",
        headers=admin_auth_headers,
        json={
            "kullanici_adi": "badrol",
            "email": "badrol@loji.test",
            "sifre": "Secure1234!",
            "rol_id": 999999,
        },
    )
    assert response.status_code in (422, 400), response.text


async def test_list_users_requires_admin(async_client, user_auth_headers):
    """Normal kullanıcı admin endpoint'e erişememeli."""
    response = await async_client.get("/api/v1/admin/users/", headers=user_auth_headers)
    assert response.status_code == 403


async def test_list_users_returns_list(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/admin/users/", headers=admin_auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 3: `test_admin_ml.py` yaz**

```python
"""Admin ML endpoint integration tests."""
import pytest
from sqlalchemy import select

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_ml_status_returns_200(async_client, admin_auth_headers):
    response = await async_client.get("/api/v1/admin/ml/status", headers=admin_auth_headers)
    assert response.status_code == 200


async def test_ml_status_requires_admin(async_client, user_auth_headers):
    response = await async_client.get("/api/v1/admin/ml/status", headers=user_auth_headers)
    assert response.status_code == 403


async def test_ml_train_requires_admin(async_client, user_auth_headers, test_vehicle):
    response = await async_client.post(
        f"/api/v1/admin/ml/train/{test_vehicle.id}",
        headers=user_auth_headers,
    )
    assert response.status_code == 403


async def test_ml_train_valid_vehicle_accepted(async_client, admin_auth_headers, test_vehicle):
    response = await async_client.post(
        f"/api/v1/admin/ml/train/{test_vehicle.id}",
        headers=admin_auth_headers,
    )
    # 200 (sync) veya 202 (async/queued) kabul edilir
    assert response.status_code in (200, 202), response.text
```

- [ ] **Step 4: `test_advanced_reports.py` yaz**

```python
"""Advanced reports endpoint integration tests."""
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_driver_comparison_pdf_returns_bytes(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/advanced-reports/pdf/driver-comparison",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 100


async def test_excel_export_returns_valid_xlsx(async_client, admin_auth_headers):
    response = await async_client.get(
        "/api/v1/advanced-reports/excel/export",
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    # XLSX magic bytes (ZIP PK header)
    assert response.content[:4] == b"PK\x03\x04"
    assert len(response.content) > 100


async def test_reports_require_auth(async_client):
    response = await async_client.get("/api/v1/advanced-reports/pdf/driver-comparison")
    assert response.status_code == 401
```

- [ ] **Step 5: Testleri çalıştır**

```bash
pytest app/tests/api/test_admin_users.py app/tests/api/test_admin_ml.py app/tests/api/test_advanced_reports.py -v --tb=short
```

Başarısız olanları not et; endpoint'ler gerçekten 500 dönüyorsa ilgili servisi düzelt.

- [ ] **Step 6: Commit**

```bash
git add app/tests/api/test_admin_users.py app/tests/api/test_admin_ml.py app/tests/api/test_advanced_reports.py
git commit -m "test(admin): add integration tests for admin users, ML, and advanced reports endpoints"
```

---

## HAFTA 2 — Backend Kalitesi

### Task 5: `_safe_float` Utility (Bölüm 1)

**Files:**
- Create: `app/core/utils/__init__.py`
- Create: `app/core/utils/type_helpers.py`
- Create: `app/tests/unit/test_type_helpers.py`
- Modify: `app/core/services/sefer_write_service.py`
- Modify: `app/services/prediction_service.py`

- [ ] **Step 1: Paket dizinini oluştur**

```bash
mkdir -p app/core/utils
touch app/core/utils/__init__.py
```

- [ ] **Step 2: Failing test yaz**

`app/tests/unit/test_type_helpers.py`:

```python
"""Tests for shared type conversion utilities."""
import pytest
from app.core.utils.type_helpers import safe_float

pytestmark = pytest.mark.unit


def test_safe_float_none_returns_none():
    assert safe_float(None) is None

def test_safe_float_valid_string():
    assert safe_float("3.14") == pytest.approx(3.14)

def test_safe_float_invalid_string_returns_none():
    assert safe_float("abc") is None

def test_safe_float_zero():
    assert safe_float(0) == 0.0

def test_safe_float_int():
    assert safe_float(42) == 42.0

def test_safe_float_empty_string_returns_none():
    assert safe_float("") is None

def test_safe_float_list_returns_none():
    assert safe_float([1, 2]) is None
```

- [ ] **Step 3: Testi çalıştır — FAIL bekleniyor**

```bash
pytest app/tests/unit/test_type_helpers.py -v
```

- [ ] **Step 4: `type_helpers.py` oluştur**

```python
"""Shared type conversion utilities."""
from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 5: Testleri çalıştır — PASS bekleniyor**

```bash
pytest app/tests/unit/test_type_helpers.py -v
```

- [ ] **Step 6: `sefer_write_service.py`'yi güncelle**

`sefer_write_service.py` dosyasında:

a) Import ekle (dosyanın ilk import bloğuna):
```python
from app.core.utils.type_helpers import safe_float
```

b) `_safe_float` static metodunu sil (L76 civarındaki `@staticmethod def _safe_float` bloğunu kaldır)

c) Tüm `cls._safe_float(` → `safe_float(` olarak değiştir:
```bash
grep -n "cls._safe_float" app/core/services/sefer_write_service.py
```

- [ ] **Step 7: `prediction_service.py`'yi güncelle**

Aynı işlemi tekrarla:
```python
from app.core.utils.type_helpers import safe_float
```
`cls._safe_float(` → `safe_float(` — ilgili satırları bul:
```bash
grep -n "cls._safe_float" app/services/prediction_service.py
```

- [ ] **Step 8: Import kontrolü**

```bash
python -c "from app.core.services.sefer_write_service import SeferWriteService; print('OK')"
python -c "from app.services.prediction_service import PredictionService; print('OK')"
```

- [ ] **Step 9: Mevcut testlerin geçtiğini doğrula**

```bash
pytest app/tests/unit/test_type_helpers.py app/tests/ -k "sefer or prediction" --tb=short -q
```

- [ ] **Step 10: Commit**

```bash
git add app/core/utils/ app/tests/unit/test_type_helpers.py \
        app/core/services/sefer_write_service.py app/services/prediction_service.py
git commit -m "refactor: extract _safe_float to shared app/core/utils/type_helpers.py"
```

---

### Task 6: RolRepository Düzeltmesi (Bölüm 4)

**Files:**
- Modify: `app/database/repositories/rol_repo.py`
- Modify: `app/database/unit_of_work.py`

- [ ] **Step 1: Mevcut rol_repo.py'yi oku**

```bash
cat -n app/database/repositories/rol_repo.py
```

- [ ] **Step 2: UoW'daki mevcut rol_repo kullanımını kontrol et**

```bash
grep -rn "RolRepository\|rol_repo" app/ --include="*.py"
```

`rol_repo` UoW üzerinden kullanılmıyorsa sonraki adımda UoW'a eklenmesi yeterli.

- [ ] **Step 3: Failing test yaz**

`app/tests/unit/test_rol_repository.py` oluştur:

```python
"""Tests for RolRepository UoW compliance."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


async def test_uow_has_rol_repo():
    """UoW'un rol_repo özelliği olmalı."""
    from app.database.unit_of_work import UnitOfWork
    async with UnitOfWork() as uow:
        assert hasattr(uow, "rol_repo"), "UoW has no rol_repo property"


async def test_create_role_uses_flush_not_commit(db_session):
    """create_role commit değil flush kullanmalı."""
    from app.database.repositories.rol_repo import RolRepository
    repo = RolRepository(db_session)

    with patch.object(db_session, "commit", new_callable=AsyncMock) as mock_commit, \
         patch.object(db_session, "flush", new_callable=AsyncMock) as mock_flush, \
         patch.object(db_session, "execute", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value.scalar_one_or_none = MagicMock(return_value=None)
        mock_exec.return_value.scalar_one_or_none = lambda: None
        # add mock
        db_session.add = MagicMock()
        await repo.create_role("test_rol", ["read"])

    mock_commit.assert_not_called()
    mock_flush.assert_called_once()
```

- [ ] **Step 4: Testi çalıştır — FAIL bekleniyor**

```bash
pytest app/tests/unit/test_rol_repository.py -v --tb=short
```

- [ ] **Step 5: `rol_repo.py`'yi düzelt**

```python
"""Data access for the Rol model."""
from typing import List, Optional

from sqlalchemy import select

from app.database.base_repository import BaseRepository
from app.database.models import Rol


class RolRepository(BaseRepository[Rol]):
    async def get_by_name(self, ad: str) -> Optional[Rol]:
        result = await self.session.execute(select(Rol).where(Rol.ad == ad))
        return result.scalar_one_or_none()

    async def create_role(self, ad: str, yetkiler: List[str]) -> Rol:
        """Creates role. Caller (UoW) is responsible for commit."""
        existing = await self.get_by_name(ad)
        if existing:
            raise ValueError(f"Bu isimde bir rol zaten var: {ad!r}")
        role = Rol(ad=ad, yetkiler=yetkiler)
        self.session.add(role)
        await self.session.flush()
        return role
```

- [ ] **Step 6: `unit_of_work.py`'ye `rol_repo` ekle**

`app/database/unit_of_work.py` dosyasında:

a) Import ekle:
```python
from app.database.repositories.rol_repo import RolRepository
```

b) Mevcut `_lazy` tanımlarının yanına:
```python
rol_repo = _lazy("rol_repo", lambda u: RolRepository(u.session))
```

(`_lazy` pattern'i nasıl kullanıldığını görmek için dosyayı önce oku: `cat -n app/database/unit_of_work.py | head -60`)

- [ ] **Step 7: Testleri çalıştır — PASS bekleniyor**

```bash
pytest app/tests/unit/test_rol_repository.py -v
```

- [ ] **Step 8: Import kontrolü**

```bash
python -c "from app.database.unit_of_work import UnitOfWork; print('OK')"
```

- [ ] **Step 9: Commit**

```bash
git add app/database/repositories/rol_repo.py app/database/unit_of_work.py \
        app/tests/unit/test_rol_repository.py
git commit -m "fix(repository): RolRepository extends BaseRepository, flush not commit, add to UoW"
```

---

### Task 7: Notification N+1 Düzeltmesi (Bölüm 3)

**Files:**
- Modify: `app/database/repositories/kullanici_repo.py`
- Modify: `app/core/services/notification_service.py`

- [ ] **Step 1: Mevcut kullanici_repo.py'yi oku**

```bash
grep -n "get_by_rol\|def get" app/database/repositories/kullanici_repo.py | head -20
```

- [ ] **Step 2: Failing test yaz**

`app/tests/unit/test_notification_n1.py` oluştur:

```python
"""Tests for notification service N+1 query fix."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

pytestmark = pytest.mark.asyncio


async def test_notification_uses_single_bulk_query():
    """3 kural için kullanici_repo tek seferde sorgulanmalı."""
    from app.core.services.notification_service import NotificationService

    mock_rules = [
        MagicMock(alici_rol_id=1, kanallar=["UI"]),
        MagicMock(alici_rol_id=2, kanallar=["UI"]),
        MagicMock(alici_rol_id=1, kanallar=["EMAIL"]),
    ]
    mock_users_by_rol = {
        1: [MagicMock(id=10), MagicMock(id=11)],
        2: [MagicMock(id=20)],
    }

    with patch("app.core.services.notification_service.UnitOfWork") as mock_uow_cls:
        mock_uow = AsyncMock()
        mock_uow_cls.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_uow.notification_repo.get_rules_by_event = AsyncMock(return_value=mock_rules)
        mock_uow.kullanici_repo.get_by_rol_ids = AsyncMock(return_value=mock_users_by_rol)
        mock_uow.session.add_all = MagicMock()
        mock_uow.session.flush = AsyncMock()

        service = NotificationService()
        test_event = MagicMock()
        test_event.type.value = "TEST_EVENT"
        await service.handle_event(test_event)

        # Tek bulk çağrı
        mock_uow.kullanici_repo.get_by_rol_ids.assert_called_once()
        # Tekil get_by_rol_id çağrısı olmamalı
        assert not hasattr(mock_uow.kullanici_repo, "get_by_rol_id") or \
               mock_uow.kullanici_repo.get_by_rol_id.call_count == 0
```

- [ ] **Step 3: Testi çalıştır — FAIL bekleniyor**

```bash
pytest app/tests/unit/test_notification_n1.py -v --tb=short
```

- [ ] **Step 4: `kullanici_repo.py`'ye bulk metod ekle**

`app/database/repositories/kullanici_repo.py` dosyasına ekle:

```python
from typing import Dict, List
from sqlalchemy import select

async def get_by_rol_ids(self, rol_ids: List[int]) -> Dict[int, List]:
    """Fetch users for multiple role IDs in a single query."""
    if not rol_ids:
        return {}
    result = await self.session.execute(
        select(Kullanici).where(
            Kullanici.rol_id.in_(rol_ids),
            Kullanici.aktif == True,  # noqa: E712
        )
    )
    users = result.scalars().all()
    grouped: Dict[int, List] = {}
    for user in users:
        grouped.setdefault(user.rol_id, []).append(user)
    return grouped
```

- [ ] **Step 5: `notification_service.py` `handle_event`'i güncelle**

Mevcut loop'u şu şekilde değiştir:

```python
async def handle_event(self, event):
    async with UnitOfWork() as uow:
        rules = await uow.notification_repo.get_rules_by_event(event.type)
        if not rules:
            return

        rol_ids = list({rule.alici_rol_id for rule in rules})
        users_by_rol = await uow.kullanici_repo.get_by_rol_ids(rol_ids)

        header, content = self._format_message(event)
        notifications = []

        for rule in rules:
            users = users_by_rol.get(rule.alici_rol_id, [])
            for user in users:
                for channel in rule.kanallar:
                    notifications.append(BildirimGecmisi(
                        kullanici_id=user.id,
                        baslik=header,
                        icerik=content,
                        olay_tipi=event.type.value,
                        kanal=channel,
                        durum=BildirimDurumu.SENT,
                    ))

        if notifications:
            uow.session.add_all(notifications)
            await uow.session.flush()

        for notif in notifications:
            if notif.kanal == "UI":
                await self._push_ws(notif, event)
```

- [ ] **Step 6: Testleri çalıştır — PASS bekleniyor**

```bash
pytest app/tests/unit/test_notification_n1.py -v
pytest app/tests/ -k "notification" --tb=short -q
```

- [ ] **Step 7: Commit**

```bash
git add app/database/repositories/kullanici_repo.py \
        app/core/services/notification_service.py \
        app/tests/unit/test_notification_n1.py
git commit -m "perf(notification): fix N+1 query with bulk get_by_rol_ids"
```

---

## HAFTA 3 — Frontend & İzleme

### Task 8: Frontend Tip Güvenliği (Bölüm 6)

**Files:**
- Create: `frontend/src/types/prediction.ts`
- Modify: `frontend/src/services/api/prediction-service.ts`
- Modify: `frontend/src/services/api/preference-service.ts`

- [ ] **Step 1: Mevcut dosyaları oku**

```bash
sed -n '65,90p' frontend/src/services/api/prediction-service.ts
sed -n '1,25p' frontend/src/services/api/preference-service.ts
```

- [ ] **Step 2: `prediction.ts` tip dosyasını oluştur**

`frontend/src/types/prediction.ts`:

```typescript
export interface PredictRequest {
  arac_id: number;
  mesafe_km: number;
  agirlik_ton: number;
  rota_tipi?: 'sehir_ici' | 'sehirler_arasi' | 'karisik';
}

export interface ExplainRequest {
  sefer_id: number;
}
```

- [ ] **Step 3: `prediction-service.ts`'i güncelle**

`data: any` olan `predict` ve `explain` metodlarını değiştir:

```typescript
import type { PredictRequest, ExplainRequest } from '../../types/prediction'

// predict metodunda:
predict: async (data: PredictRequest) => {
    const response = await axiosInstance.post('/predictions/predict', data);
    return response.data;
},

// explain metodunda:
explain: async (data: ExplainRequest) => {
    const response = await axiosInstance.post('/predictions/explain', data);
    return response.data;
},
```

- [ ] **Step 4: `preference-service.ts`'i güncelle**

`deger: any` alanlarını değiştir:

```typescript
// Dosyanın başına (import'lardan sonra):
interface PreferenceValue {
  deger: string | number | boolean | null;
}

// Fonksiyon imzalarında any yerine PreferenceValue['deger'] kullan
```

- [ ] **Step 5: TypeScript kontrolü**

```bash
cd frontend && npx tsc --noEmit
```

Beklenen: Hata yok.

- [ ] **Step 6: Build kontrolü**

```bash
cd frontend && npm run build
```

Beklenen: Başarılı build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/prediction.ts \
        frontend/src/services/api/prediction-service.ts \
        frontend/src/services/api/preference-service.ts
git commit -m "fix(frontend): replace any types in prediction and preference services"
```

---

### Task 9: XaiPanel ve Dashboard Derinleştirme (Bölüm 11)

**Files:**
- Modify: `frontend/src/components/predictions/XaiPanel.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Mevcut XaiPanel'i oku**

```bash
cat -n frontend/src/components/predictions/XaiPanel.tsx
```

- [ ] **Step 2: Mevcut DashboardPage KPI alanlarını oku**

```bash
grep -n "in_progress\|active_count\|tripStats\|kpi" frontend/src/pages/DashboardPage.tsx | head -20
```

- [ ] **Step 3: `XaiPanel.tsx`'i güncelle**

`getEnsembleStatus` API'si zaten `prediction-service.ts:95`'te mevcut.

```tsx
import { useQuery } from '@tanstack/react-query'
import { predictionService } from '@/services/api/prediction-service'

export function XaiPanel() {
  const { data: ensemble, isLoading } = useQuery({
    queryKey: ['predictions-ensemble'],
    queryFn: () => predictionService.getEnsembleStatus(),
  })

  if (isLoading) {
    return (
      <div className="glass rounded-2xl border border-border p-6">
        <p className="text-secondary text-sm">Ensemble verisi yükleniyor...</p>
      </div>
    )
  }

  const weights = ensemble?.model_weights ?? {}

  return (
    <div className="glass rounded-2xl border border-border p-6 space-y-4">
      <h3 className="font-semibold text-primary">Model Ağırlıkları</h3>
      {Object.entries(weights).map(([model, weight]) => (
        <div key={model} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-secondary capitalize">{model}</span>
            <span className="font-medium">{(Number(weight) * 100).toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-500"
              style={{ width: `${Number(weight) * 100}%` }}
            />
          </div>
        </div>
      ))}
      {Object.keys(weights).length === 0 && (
        <p className="text-secondary text-sm">Henüz eğitim verisi yok.</p>
      )}
    </div>
  )
}
```

- [ ] **Step 4: DashboardPage'e `in_progress_count` KPI ekle**

`DashboardPage.tsx` kpi items dizisine ekle (backend `in_progress_count` döndürüyor, `active_count` değil):

```tsx
{
  label: t('dashboard.active_trips', 'Yoldaki Sefer'),
  value: tripStats?.in_progress_count ?? '—',
  icon: Route,
  color: 'text-purple-500',
  bgColor: 'bg-purple-500/10',
},
```

(`Route` ikonu `lucide-react`'ten import et; zaten kullanılıyorsa ekleme)

- [ ] **Step 5: Build kontrolü**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/predictions/XaiPanel.tsx \
        frontend/src/pages/DashboardPage.tsx
git commit -m "feat(frontend): implement XaiPanel ensemble weights, add active trip KPI"
```

---

### Task 10: Grafana Metrik İsimleri (Bölüm 13)

**Files:**
- Modify: `grafana/dashboards/lojinext.json`

- [ ] **Step 1: Mevcut metrik isimlerini bul**

```bash
grep -n "celery_tasks_total\|celery_queue_length" grafana/dashboards/lojinext.json
```

- [ ] **Step 2: Metrik adlarını güncelle**

`lojinext.json` içindeki tüm oluşumları değiştir:

| Eski | Yeni |
|------|------|
| `celery_tasks_total{...,state="RECEIVED"}` | `celery_task_received_total{...}` |
| `celery_tasks_total{...,state="STARTED"}` | `celery_task_started_total{...}` |
| `celery_tasks_total{...,state="FAILURE"}` | `celery_task_failed_total{...}` |
| `celery_tasks_total{...,state="SUCCESS"}` | `celery_task_succeeded_total{...}` |
| `celery_queue_length` | `celery_queue_prefetch_count` |

```bash
sed -i 's/celery_tasks_total{job="celery_exporter",state="RECEIVED"}/celery_task_received_total{job="celery_exporter"}/g' grafana/dashboards/lojinext.json
sed -i 's/celery_tasks_total{job="celery_exporter",state="STARTED"}/celery_task_started_total{job="celery_exporter"}/g' grafana/dashboards/lojinext.json
sed -i 's/celery_tasks_total{job="celery_exporter",state="FAILURE"}/celery_task_failed_total{job="celery_exporter"}/g' grafana/dashboards/lojinext.json
```

Kalan `celery_tasks_total` oluşumlarını manuel kontrol et:
```bash
grep -n "celery_tasks_total" grafana/dashboards/lojinext.json
```

- [ ] **Step 3: JSON syntax doğrula**

```bash
python -c "import json; json.load(open('grafana/dashboards/lojinext.json')); print('JSON OK')"
```

- [ ] **Step 4: Commit**

```bash
git add grafana/dashboards/lojinext.json
git commit -m "fix(grafana): update Celery metric names for celery-exporter v0.10+"
```

---

### Task 11: Celery Retry Eksiklikleri (Bölüm 10)

**Files:**
- Modify: `app/workers/tasks/driver_tasks.py`
- Modify: `app/workers/tasks/outbox_tasks.py`

- [ ] **Step 1: Her iki dosyayı oku**

```bash
cat -n app/workers/tasks/driver_tasks.py
cat -n app/workers/tasks/outbox_tasks.py
```

- [ ] **Step 2: `driver_tasks.py`'yi güncelle**

Her `@celery_app.task` dekoratörüne retry konfigürasyonu ekle. Task içindeki try/except'i şu örüntüye göre güncelle:

```python
@celery_app.task(
    bind=True,
    name="tasks.driver.<task_name>",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def my_driver_task(self, ...):
    try:
        # mevcut iş mantığı
        ...
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
    except Exception:
        logger.exception("Driver task failed permanently")
        raise
```

**ÖNEMLİ:** Business logic hataları (ValueError, ValidationError) retry edilmemeli — sadece geçici ağ/timeout hatalarını retry et.

- [ ] **Step 3: `outbox_tasks.py`'yi güncelle**

Aynı retry pattern'i uygula. `outbox_tasks.py` için `max_retries=5` uygun olabilir (relay kritik).

- [ ] **Step 4: Import kontrolü**

```bash
python -c "from app.workers.tasks.driver_tasks import *; print('OK')"
python -c "from app.workers.tasks.outbox_tasks import *; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks/driver_tasks.py app/workers/tasks/outbox_tasks.py
git commit -m "feat(celery): add retry config to driver_tasks and outbox_tasks"
```

---

## Son Doğrulama

- [ ] **Tüm backend testleri**

```bash
pytest --tb=short -q
```

Beklenen: 70%+ coverage, sıfır failure.

- [ ] **Frontend build**

```bash
cd frontend && npm run build && npx vitest --run
```

- [ ] **Lint ve tip kontrol**

```bash
ruff check app --select E,F,W,I
mypy app --ignore-missing-imports --no-strict-optional
cd frontend && npx tsc --noEmit
```

- [ ] **Alembic drift yok**

```bash
alembic check
```

---

## Ertelenen Bölümler

| Bölüm | Neden ertelendi |
|-------|----------------|
| 12 — `sefer_write_service` bölünmesi | 1258 satır, 27 fonksiyon, `cls` referansları — yanlış bölünürse `ImportError`. Ayrı plan gerektirir. |
| 14 — `report_service` UoW geçişi | Geniş refactor; 11 repo bağımlılığı. Risk/fayda oranı şu an uygun değil. |
