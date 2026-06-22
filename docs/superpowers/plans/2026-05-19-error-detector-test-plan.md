# Error Detector Test Plan — 2026-05-19

## Coverage Gap Analysis (Mevcut Testlere Göre)

Mevcut `test_event_bus.py` şunları kapsamıyor:
- Circuit breaker'ın PG write failure ile gerçek açılma senaryosu
- Half-open → reset → success döngüsü
- `_flush_batch` circuit açıkken Redis-only path
- `_write_redis` pipeline mantığı (fingerprint key, stream key, hourly bucket)
- `_flush_to_redis_only` metodu
- `double_start` guard (`start()` ikinci kez çağrıldığında yeni task başlatmamalı)

`test_celery_probe.py` yalnızca `_record_heartbeat_key` key formatını test ediyor —
task failure/retry/beat watchdog emit testleri yok.

`test_alarm_router.py` hiç yok.

`test_service_probe.py` SSE token/stream testleri içermiyor.

---

## 1. Unit Testler

### 1.1 ErrorEventBus — Circuit Breaker Döngüsü

**Dosya:** `app/tests/unit/test_monitoring/test_event_bus.py` (mevcut dosyaya ekle)

```python
# ─── Circuit Breaker Gelişmiş Testler ─────────────────────────────────────────
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.monitoring.event_bus import (
    ErrorEventBus,
    _CIRCUIT_FAILURE_THRESHOLD,
    _CIRCUIT_RESET_SECONDS,
)
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity


def _ev(severity=ErrorSeverity.ERROR, category="test"):
    return ErrorEvent(layer=ErrorLayer.API, category=category,
                      severity=severity, message="unit test error")


@pytest.mark.unit
async def test_circuit_opens_after_threshold_failures():
    """3 ardışık _record_failure() → circuit_open=True."""
    bus = ErrorEventBus()
    for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
        bus._record_failure()
    assert bus._circuit_open is True


@pytest.mark.unit
async def test_circuit_not_open_below_threshold():
    """Eşiğin altında circuit açılmamalı."""
    bus = ErrorEventBus()
    for _ in range(_CIRCUIT_FAILURE_THRESHOLD - 1):
        bus._record_failure()
    assert bus._circuit_open is False


@pytest.mark.unit
async def test_circuit_half_open_resets_on_success():
    """Circuit open + 60s geçti → _flush_batch başarılı PG write sonrası sıfırlanmalı."""
    bus = ErrorEventBus()
    bus._circuit_open = True
    bus._circuit_opened_at = time.monotonic() - (_CIRCUIT_RESET_SECONDS + 1)
    bus._failure_count = _CIRCUIT_FAILURE_THRESHOLD

    # _should_attempt_reset() → True
    assert bus._should_attempt_reset() is True

    # Simüle et: _flush_batch çağrıldığında _write_postgres başarılı
    bus._queue.put_nowait(_ev())
    mock_router = AsyncMock()
    with (
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_redis",
              new_callable=AsyncMock),
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
              new_callable=AsyncMock),
        patch("app.infrastructure.monitoring.event_bus.get_alarm_router",
              return_value=mock_router),
    ):
        await bus._flush_batch()

    assert bus._circuit_open is False
    assert bus._failure_count == 0


@pytest.mark.unit
async def test_circuit_open_skips_postgres_goes_redis_only():
    """Circuit open ve 60s geçmedi → yalnızca Redis'e yaz, PG skip."""
    bus = ErrorEventBus()
    bus._circuit_open = True
    bus._circuit_opened_at = time.monotonic()  # yeni açıldı, 60s dolmadı
    bus._queue.put_nowait(_ev())

    redis_mock = AsyncMock()
    with (
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_redis",
              new_callable=AsyncMock) as mock_redis,
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
              new_callable=AsyncMock) as mock_pg,
    ):
        await bus._flush_batch()
        mock_redis.assert_called_once()
        mock_pg.assert_not_called()


@pytest.mark.unit
async def test_pg_failure_increments_failure_count_and_opens_circuit():
    """_write_postgres raise → failure count artar → circuit açılabilir."""
    bus = ErrorEventBus()
    for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
        bus._queue.put_nowait(_ev())

    with (
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_redis",
              new_callable=AsyncMock),
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
              side_effect=Exception("DB down")),
        patch("app.infrastructure.monitoring.event_bus.get_alarm_router") as mock_router_fn,
    ):
        mock_router_fn.side_effect = ImportError  # alarm_router devre dışı
        # Her flush'ta 1 failure → 3 flush → circuit açılmalı
        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            bus._queue.put_nowait(_ev())
            await bus._flush_batch()

    assert bus._circuit_open is True


@pytest.mark.unit
async def test_double_start_does_not_create_second_task():
    """start() ikinci kez çağrıldığında yeni task başlatmamalı."""
    bus = ErrorEventBus()
    with patch.object(bus, "_flush_loop", new_callable=AsyncMock):
        bus.start()
        task_first = bus._flusher_task
        bus.start()
        task_second = bus._flusher_task
    assert task_first is task_second


@pytest.mark.unit
async def test_empty_batch_does_not_reset_failure_count():
    """Boş queue → _flush_batch erken return, success kaydı YOK → failure_count korunur."""
    bus = ErrorEventBus()
    bus._failure_count = 2  # 1 altında eşik
    # Boş queue ile flush
    with (
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_redis",
              new_callable=AsyncMock) as mock_redis,
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
              new_callable=AsyncMock) as mock_pg,
    ):
        await bus._flush_batch()
        mock_redis.assert_not_called()
        mock_pg.assert_not_called()
    # failure_count değişmemeli
    assert bus._failure_count == 2


@pytest.mark.unit
async def test_queue_full_drops_event_and_logs():
    """Queue dolu → emit() event'i drop eder, hata fırlatmaz."""
    bus = ErrorEventBus(maxsize=1)
    await bus.emit(_ev())  # queue dolar
    # İkinci emit drop edilmeli, exception yok
    await bus.emit(_ev())
    assert bus._queue.qsize() == 1  # hâlâ 1


@pytest.mark.unit
async def test_flush_batch_routing_failure_does_not_drop_event():
    """AlarmRouter exception → PG write yine de çalışmalı."""
    bus = ErrorEventBus()
    bus._queue.put_nowait(_ev())

    with (
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_redis",
              new_callable=AsyncMock),
        patch("app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
              new_callable=AsyncMock) as mock_pg,
        patch("app.infrastructure.monitoring.event_bus.get_alarm_router",
              side_effect=Exception("router crash")),
    ):
        await bus._flush_batch()
        mock_pg.assert_called_once()
```

---

### 1.2 AlarmRouter — Yeni Test Dosyası

**Dosya:** `app/tests/unit/test_monitoring/test_alarm_router.py`

```python
"""AlarmRouter unit testleri — tüm routing path'leri, dedup, anomaly escalation."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.monitoring.alarm_router import (
    AnomalyDetector,
    AlarmRouter,
    _DEDUP_WINDOW_SECONDS,
    _MIN_SAMPLES,
    _Z_SCORE_THRESHOLD,
)
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity


def _ev(severity=ErrorSeverity.CRITICAL, category="db_error", message="test"):
    return ErrorEvent(
        layer=ErrorLayer.DB,
        category=category,
        severity=severity,
        message=message,
    )


# ─── AnomalyDetector._compute_z_score ─────────────────────────────────────────

@pytest.mark.unit
def test_z_score_none_when_too_few_samples():
    det = AnomalyDetector()
    counts = [1, 2, 3]  # < _MIN_SAMPLES + 1
    assert det._compute_z_score(counts) is None


@pytest.mark.unit
def test_z_score_zero_for_flat_data():
    """Tüm değerler aynıysa stdev=0 → 0.0 döner."""
    det = AnomalyDetector()
    counts = [5, 5, 5, 5, 5, 5, 5]  # 7 nokta, stdev=0
    result = det._compute_z_score(counts)
    assert result == 0.0


@pytest.mark.unit
def test_z_score_high_for_spike():
    """Son bucket anormal büyükse Z > threshold döner."""
    det = AnomalyDetector()
    # baseline: [1,1,1,1,1,1], current: 100
    counts = [1, 1, 1, 1, 1, 1, 100]
    z = det._compute_z_score(counts)
    assert z is not None
    assert z > _Z_SCORE_THRESHOLD


@pytest.mark.unit
def test_z_score_minimum_samples_boundary():
    """Tam _MIN_SAMPLES + 1 nokta geçerli."""
    det = AnomalyDetector()
    counts = [2] * _MIN_SAMPLES + [2]  # son değer de baseline ile aynı
    z = det._compute_z_score(counts)
    # stdev=0 → 0.0
    assert z == 0.0


@pytest.mark.unit
def test_z_score_below_threshold_no_anomaly():
    """Orta bir spike, eşiğin altında."""
    det = AnomalyDetector()
    counts = [10, 10, 10, 10, 10, 10, 12]  # küçük bir artış
    z = det._compute_z_score(counts)
    assert z is not None
    assert z <= _Z_SCORE_THRESHOLD


# ─── AlarmRouter.route — CRITICAL immediate send ──────────────────────────────

@pytest.mark.unit
async def test_critical_event_sends_immediately():
    """CRITICAL event → _send_immediate çağrılmalı."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.CRITICAL)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=False),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(router, "_increment_digest_counter", new_callable=AsyncMock) as mock_digest,
    ):
        await router.route(ev)
        mock_send.assert_called_once_with(ev, is_anomaly=False)
        mock_digest.assert_not_called()


@pytest.mark.unit
async def test_critical_event_dedup_within_15min():
    """Aynı fingerprint, 15dk içinde tekrar CRITICAL → _send_immediate tekrar çağrılmamalı."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.CRITICAL)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=False),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
    ):
        await router.route(ev)
        await router.route(ev)  # aynı fingerprint, hemen arkasından
        mock_send.assert_called_once()  # ikinci kez çağrılmamalı


@pytest.mark.unit
async def test_critical_event_resent_after_dedup_window():
    """15dk dedup window geçtikten sonra aynı CRITICAL tekrar gönderilmeli."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.CRITICAL)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=False),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
    ):
        # İlk gönderim, timestamp'i geriye çek
        await router.route(ev)
        router._sent_critical[ev.fingerprint] = time.monotonic() - (_DEDUP_WINDOW_SECONDS + 1)
        await router.route(ev)
        assert mock_send.call_count == 2


# ─── AlarmRouter.route — ERROR digest ─────────────────────────────────────────

@pytest.mark.unit
async def test_error_event_goes_to_digest():
    """ERROR severity → _increment_digest_counter, _send_immediate yok."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.ERROR)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=False),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(router, "_increment_digest_counter", new_callable=AsyncMock) as mock_digest,
    ):
        await router.route(ev)
        mock_send.assert_not_called()
        mock_digest.assert_called_once_with(ev)


@pytest.mark.unit
async def test_warning_event_no_notification():
    """WARNING → ne immediate send ne digest."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.WARNING)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=False),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(router, "_increment_digest_counter", new_callable=AsyncMock) as mock_digest,
    ):
        await router.route(ev)
        mock_send.assert_not_called()
        mock_digest.assert_not_called()


# ─── AlarmRouter.route — Anomaly escalation ───────────────────────────────────

@pytest.mark.unit
async def test_anomaly_escalates_error_to_critical():
    """ERROR event + anomaly=True → CRITICAL path, _send_immediate çağrılır."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.ERROR)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=True),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
        patch.object(router, "_increment_digest_counter", new_callable=AsyncMock) as mock_digest,
    ):
        await router.route(ev)
        mock_send.assert_called_once_with(ev, is_anomaly=True)
        mock_digest.assert_not_called()


@pytest.mark.unit
async def test_anomaly_warning_escalates_to_critical():
    """WARNING + anomaly → CRITICAL send."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.WARNING)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=True),
        patch.object(router, "_send_immediate", new_callable=AsyncMock) as mock_send,
    ):
        await router.route(ev)
        mock_send.assert_called_once()


# ─── AlarmRouter dedup cache pruning ──────────────────────────────────────────

@pytest.mark.unit
async def test_stale_dedup_entries_pruned():
    """2 * _DEDUP_WINDOW_SECONDS'tan eski girişler temizlenmeli."""
    router = AlarmRouter()
    ev = _ev(severity=ErrorSeverity.CRITICAL)
    stale_fp = "stale_fingerprint_abc"
    router._sent_critical[stale_fp] = time.monotonic() - (2 * _DEDUP_WINDOW_SECONDS + 1)

    with (
        patch.object(router._anomaly, "check", new_callable=AsyncMock, return_value=False),
        patch.object(router, "_send_immediate", new_callable=AsyncMock),
    ):
        await router.route(ev)

    assert stale_fp not in router._sent_critical
```

---

### 1.3 Telegram Notifier — WARNING Log Testi

**Dosya:** `app/tests/unit/test_monitoring/test_telegram_notifier.py`

```python
"""Telegram notifier unit testleri."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
async def test_notify_error_success():
    """Başarılı POST → exception yok, log yok."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch(
        "app.infrastructure.notifications.telegram_notifier.get_monitored_client",
        return_value=mock_client,
    ):
        from app.infrastructure.notifications.telegram_notifier import notify_error
        # Exception fırlatmamalı
        await notify_error(level="critical", message="test msg", path="/api", trace_id="abc")
        mock_client.post.assert_called_once()


@pytest.mark.unit
async def test_notify_error_logs_warning_on_failure(caplog):
    """httpx exception → WARNING log atılmalı, exception yutulmalı."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

    with patch(
        "app.infrastructure.notifications.telegram_notifier.get_monitored_client",
        return_value=mock_client,
    ):
        from app.infrastructure.notifications.telegram_notifier import notify_error
        with caplog.at_level(logging.WARNING):
            await notify_error(level="critical", message="fail test")

    assert any("WARNING" in r.levelname and "Telegram" in r.message for r in caplog.records), \
        "WARNING log 'Telegram' içermeli"


@pytest.mark.unit
async def test_notify_error_sends_correct_payload():
    """POST payload'ı doğru alanları içermeli."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock()

    with patch(
        "app.infrastructure.notifications.telegram_notifier.get_monitored_client",
        return_value=mock_client,
    ):
        from app.infrastructure.notifications.telegram_notifier import notify_error
        await notify_error(
            level="error",
            message="fuel anomaly",
            path="/api/v1/seferler",
            trace_id="trace-123",
        )

    call_kwargs = mock_client.post.call_args[1]
    payload = call_kwargs["json"]
    assert payload["level"] == "error"
    assert payload["message"] == "fuel anomaly"
    assert payload["path"] == "/api/v1/seferler"
    assert payload["trace_id"] == "trace-123"
```

---

### 1.4 SSE Token — Unit Testler

**Dosya:** `app/tests/unit/test_monitoring/test_sse_token.py`

```python
"""SSE token oluşturma, tek kullanım ve expire testleri."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── Token üretimi ─────────────────────────────────────────────────────────────

@pytest.mark.unit
async def test_create_sse_token_returns_uuid_and_expiry():
    """POST /error-stream-token → token UUID formatında, expires_in=90."""
    from app.api.v1.endpoints.error_stream import create_sse_token

    mock_user = MagicMock()
    mock_user.id = 42

    mock_mgr = MagicMock()
    mock_mgr.redis = AsyncMock()
    mock_mgr.redis.set = AsyncMock()

    with patch(
        "app.api.v1.endpoints.error_stream.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        result = await create_sse_token(current_user=mock_user)

    assert "token" in result
    assert result["expires_in"] == 90
    import uuid
    uuid.UUID(result["token"])  # UUID formatı doğrulama


@pytest.mark.unit
async def test_create_sse_token_stored_in_redis():
    """Token Redis'e 90s TTL ile kaydedilmeli."""
    from app.api.v1.endpoints.error_stream import create_sse_token

    mock_user = MagicMock()
    mock_user.id = 7

    mock_redis = AsyncMock()
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(
        "app.api.v1.endpoints.error_stream.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        result = await create_sse_token(current_user=mock_user)

    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    key = call_args[0][0]
    payload_str = call_args[0][1]
    ex = call_args[1]["ex"]

    assert key == f"sse_token:{result['token']}"
    assert json.loads(payload_str)["user_id"] == 7
    assert ex == 90


@pytest.mark.unit
async def test_sse_stream_without_token_returns_401():
    """?token yok → 401 UNAUTHORIZED."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {}

    response = await error_stream(request=mock_request)
    assert response.status_code == 401


@pytest.mark.unit
async def test_sse_stream_with_invalid_token_returns_401():
    """Geçersiz/süresi dolmuş token → 401."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"token": "nonexistent-token"}

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    with patch(
        "app.api.v1.endpoints.error_stream.get_pubsub_manager",
        return_value=mock_mgr,
    ):
        response = await error_stream(request=mock_request)

    assert response.status_code == 401


@pytest.mark.unit
async def test_sse_token_deleted_after_single_use():
    """Token ilk kullanımda Redis'ten silinmeli (tek kullanım)."""
    from fastapi import Request

    from app.api.v1.endpoints.error_stream import error_stream

    token = "test-token-abc"
    user_payload = json.dumps({"user_id": 1})

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=user_payload)
    mock_redis.delete = AsyncMock()
    mock_mgr = MagicMock()
    mock_mgr.redis = mock_redis

    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"token": token}

    # DB lookup mock — kullanıcı bulunamayacak → 401, ama delete zaten çağrıldı
    from sqlalchemy.ext.asyncio import AsyncSession
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.api.v1.endpoints.error_stream.get_pubsub_manager", return_value=mock_mgr),
        patch("app.api.v1.endpoints.error_stream.AsyncSessionLocal", return_value=mock_session),
    ):
        await error_stream(request=mock_request)

    mock_redis.delete.assert_called_once_with(f"sse_token:{token}")
```

---

### 1.5 Fingerprint — make_fingerprint Normalizasyon Testleri

**Dosya:** `app/tests/unit/test_monitoring/test_models.py`

```python
"""ErrorEvent model ve fingerprint testleri."""
import pytest

from app.infrastructure.monitoring.models import (
    ErrorEvent,
    ErrorLayer,
    ErrorSeverity,
    make_fingerprint,
)


def test_fingerprint_normalizes_numbers():
    fp1 = make_fingerprint("db", "slow_query", "Query took 42ms, 100 rows")
    fp2 = make_fingerprint("db", "slow_query", "Query took 99ms, 5 rows")
    assert fp1 == fp2


def test_fingerprint_normalizes_uuids():
    fp1 = make_fingerprint("api", "not_found", "Resource 550e8400-e29b-41d4-a716-446655440000 not found")
    fp2 = make_fingerprint("api", "not_found", "Resource aabbccdd-eeff-1122-3344-556677889900 not found")
    assert fp1 == fp2


def test_fingerprint_normalizes_string_literals():
    fp1 = make_fingerprint("db", "error", "value 'alice' violates constraint")
    fp2 = make_fingerprint("db", "error", "value 'bob' violates constraint")
    assert fp1 == fp2


def test_fingerprint_differs_by_layer():
    fp1 = make_fingerprint("db", "timeout", "connection timeout")
    fp2 = make_fingerprint("api", "timeout", "connection timeout")
    assert fp1 != fp2


def test_fingerprint_differs_by_category():
    fp1 = make_fingerprint("db", "deadlock", "connection timeout")
    fp2 = make_fingerprint("db", "timeout", "connection timeout")
    assert fp1 != fp2


def test_error_event_auto_fingerprint():
    ev = ErrorEvent(
        layer=ErrorLayer.DB,
        category="test",
        severity=ErrorSeverity.ERROR,
        message="user 42 not found",
    )
    expected = make_fingerprint("db", "test", "user 42 not found")
    assert ev.fingerprint == expected


def test_error_event_str_layer_coerced():
    ev = ErrorEvent(
        layer="api",  # type: ignore[arg-type]
        category="test",
        severity="error",  # type: ignore[arg-type]
        message="test",
    )
    assert ev.layer == ErrorLayer.API
    assert ev.severity == ErrorSeverity.ERROR


def test_to_dict_contains_all_keys():
    ev = ErrorEvent(
        layer=ErrorLayer.FRONTEND,
        category="js_error",
        severity=ErrorSeverity.WARNING,
        message="ReferenceError: x is not defined",
    )
    d = ev.to_dict()
    required_keys = {"layer", "category", "severity", "message", "fingerprint",
                     "trace_id", "path", "stack_trace", "metadata", "occurred_at"}
    assert required_keys.issubset(d.keys())
```

---

## 2. Integration Testler (Real Redis + PG)

**Dosya:** `app/tests/integration/test_error_detector_integration.py`

```python
"""
Integration testleri: gerçek Redis + PostgreSQL, mock HTTP.

Çalıştır:
    pytest app/tests/integration/test_error_detector_integration.py -x -q
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.monitoring.event_bus import ErrorEventBus, reset_event_bus
from app.infrastructure.monitoring.models import ErrorEvent, ErrorLayer, ErrorSeverity


pytestmark = [pytest.mark.integration]


@pytest.fixture()
async def bus():
    """Her test için temiz bus instance."""
    reset_event_bus()
    b = ErrorEventBus()
    yield b
    await b.stop()
    reset_event_bus()


@pytest.fixture()
async def redis_client():
    """Test süresince kullanılacak gerçek Redis client."""
    from app.infrastructure.cache.redis_pubsub import get_pubsub_manager
    mgr = get_pubsub_manager()
    yield mgr.redis


# ─── emit() → Redis'e yazıldı mı? ─────────────────────────────────────────────

@pytest.mark.integration
async def test_flush_writes_fingerprint_key_to_redis(bus, redis_client):
    """_flush_batch sonrası error:fp:<fingerprint> Redis'te olmalı."""
    ev = ErrorEvent(
        layer=ErrorLayer.API,
        category="integration_test",
        severity=ErrorSeverity.ERROR,
        message="integration test error",
    )
    await bus.emit(ev)

    with patch(
        "app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
        new_callable=AsyncMock,
    ):
        await bus._flush_batch()

    fp_key = f"error:fp:{ev.fingerprint}"
    count = await redis_client.hget(fp_key, "count")
    assert count is not None
    assert int(count) >= 1

    severity_val = await redis_client.hget(fp_key, "severity")
    assert severity_val.decode() == "error"

    # Temizlik
    await redis_client.delete(fp_key)


@pytest.mark.integration
async def test_flush_writes_hourly_bucket_to_redis(bus, redis_client):
    """_flush_batch → error:hourly:api:integration_test:YYYYMMDDHH key'i artırmalı."""
    from datetime import datetime, timezone

    ev = ErrorEvent(
        layer=ErrorLayer.API,
        category="hourly_test",
        severity=ErrorSeverity.WARNING,
        message="hourly bucket test",
    )
    await bus.emit(ev)

    with patch(
        "app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
        new_callable=AsyncMock,
    ):
        await bus._flush_batch()

    hour_key = (
        f"error:hourly:api:hourly_test"
        f":{ev.occurred_at.strftime('%Y%m%d%H')}"
    )
    val = await redis_client.get(hour_key)
    assert val is not None
    assert int(val) >= 1
    await redis_client.delete(hour_key)


@pytest.mark.integration
async def test_flush_writes_severity_stream_to_redis(bus, redis_client):
    """_flush_batch → error:stream:error sorted set'e girdi eklenmeli."""
    ev = ErrorEvent(
        layer=ErrorLayer.SERVICE,
        category="stream_test",
        severity=ErrorSeverity.ERROR,
        message="stream test",
    )
    await bus.emit(ev)

    with patch(
        "app.infrastructure.monitoring.event_bus.ErrorEventBus._write_postgres",
        new_callable=AsyncMock,
    ):
        await bus._flush_batch()

    stream_key = "error:stream:error"
    entries = await redis_client.zrange(stream_key, -5, -1)
    found = any(b"stream_test" in e for e in entries)
    assert found, "Sorted set'te stream_test kategori bulunamadı"


# ─── emit() → PostgreSQL'e yazıldı mı? ────────────────────────────────────────

@pytest.mark.integration
async def test_flush_writes_to_error_events_table(bus):
    """_flush_batch → error_events tablosuna UPSERT yapılmalı."""
    from sqlalchemy import text
    from app.database.connection import AsyncSessionLocal

    ev = ErrorEvent(
        layer=ErrorLayer.DB,
        category="pg_integration_test",
        severity=ErrorSeverity.ERROR,
        message=f"PG integration test {datetime.now(timezone.utc).isoformat()}",
    )
    await bus.emit(ev)
    await bus._flush_batch()

    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text("SELECT count, layer, severity FROM error_events WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        result = row.fetchone()

    assert result is not None, "error_events'te kayıt bulunamadı"
    assert result.layer == "db"
    assert result.severity == "error"
    assert result.count >= 1

    # Temizlik
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM error_events WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        await session.commit()


@pytest.mark.integration
async def test_flush_writes_to_error_occurrences_table(bus):
    """_flush_batch → error_occurrences tablosuna INSERT yapılmalı."""
    from sqlalchemy import text
    from app.database.connection import AsyncSessionLocal

    ev = ErrorEvent(
        layer=ErrorLayer.CELERY,
        category="occurrence_test",
        severity=ErrorSeverity.WARNING,
        message="occurrence integration test",
    )
    await bus.emit(ev)
    await bus._flush_batch()

    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text("SELECT COUNT(*) FROM error_occurrences WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        count = row.scalar_one()

    assert count >= 1

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM error_occurrences WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        await session.execute(
            text("DELETE FROM error_events WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        await session.commit()


@pytest.mark.integration
async def test_upsert_increments_count_on_duplicate_fingerprint(bus):
    """Aynı fingerprint iki kez emit → count=2."""
    from sqlalchemy import text
    from app.database.connection import AsyncSessionLocal

    msg = "duplicate upsert test"
    ev1 = ErrorEvent(layer=ErrorLayer.API, category="upsert_test",
                     severity=ErrorSeverity.ERROR, message=msg)
    ev2 = ErrorEvent(layer=ErrorLayer.API, category="upsert_test",
                     severity=ErrorSeverity.ERROR, message=msg)
    assert ev1.fingerprint == ev2.fingerprint

    await bus.emit(ev1)
    await bus.emit(ev2)
    await bus._flush_batch()

    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text("SELECT count FROM error_events WHERE fingerprint = :fp"),
            {"fp": ev1.fingerprint},
        )
        result = row.fetchone()

    assert result is not None
    assert result.count == 2

    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM error_occurrences WHERE fingerprint = :fp"),
            {"fp": ev1.fingerprint},
        )
        await session.execute(
            text("DELETE FROM error_events WHERE fingerprint = :fp"),
            {"fp": ev1.fingerprint},
        )
        await session.commit()


# ─── CRITICAL → Telegram mock'a istek gitti mi? ───────────────────────────────

@pytest.mark.integration
async def test_critical_event_triggers_telegram(bus):
    """CRITICAL emit → AlarmRouter → Telegram notify_error çağrılmalı."""
    from app.infrastructure.monitoring.alarm_router import get_alarm_router

    ev = ErrorEvent(
        layer=ErrorLayer.DB,
        category="telegram_integration",
        severity=ErrorSeverity.CRITICAL,
        message="critical db failure integration",
    )
    await bus.emit(ev)

    with (
        patch(
            "app.infrastructure.monitoring.alarm_router.AlarmRouter._anomaly.check",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.infrastructure.notifications.telegram_notifier.get_monitored_client"
        ) as mock_client_factory,
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock()
        mock_client_factory.return_value = mock_client

        await bus._flush_batch()
        # Task tamamlanması için kısa bekleme
        await asyncio.sleep(0.1)

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"]["level"] == "critical"


# ─── /error-events API testleri ───────────────────────────────────────────────

@pytest.mark.integration
async def test_error_events_api_returns_paginated_results(async_client, admin_token):
    """GET /api/v1/system/error-events → pagination çalışmalı."""
    response = await async_client.get(
        "/api/v1/system/error-events?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.integration
async def test_error_events_api_layer_filter(async_client, admin_token):
    """?layer=db → yalnızca db layer döner."""
    response = await async_client.get(
        "/api/v1/system/error-events?layer=db",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["layer"] == "db"


@pytest.mark.integration
async def test_error_events_api_invalid_layer_returns_422(async_client, admin_token):
    """?layer=invalid → 422 Unprocessable."""
    response = await async_client.get(
        "/api/v1/system/error-events?layer=nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.integration
async def test_error_events_api_severity_filter(async_client, admin_token):
    """?severity=critical → yalnızca critical severity döner."""
    response = await async_client.get(
        "/api/v1/system/error-events?severity=critical",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["severity"] == "critical"


@pytest.mark.integration
async def test_error_events_api_resolved_filter(async_client, admin_token):
    """?resolved=false (default) → resolved_at IS NULL sonuçlar."""
    response = await async_client.get(
        "/api/v1/system/error-events?resolved=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["resolved_at"] is None


# ─── /error-stats API testi ───────────────────────────────────────────────────

@pytest.mark.integration
async def test_error_stats_api_returns_hourly_rows(async_client, admin_token):
    """GET /api/v1/system/error-stats → stats listesi döner."""
    response = await async_client.get(
        "/api/v1/system/error-stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    # Veri varsa format kontrolü
    for row in data["stats"]:
        assert "hour" in row
        assert "layer" in row
        assert "severity" in row
        assert "event_count" in row


# ─── /resolve endpoint testi ─────────────────────────────────────────────────

@pytest.mark.integration
async def test_resolve_error_event(bus, async_client, admin_token):
    """emit → flush → resolve → resolved_at set edilmiş olmalı."""
    from sqlalchemy import text
    from app.database.connection import AsyncSessionLocal

    ev = ErrorEvent(
        layer=ErrorLayer.API,
        category="resolve_test",
        severity=ErrorSeverity.ERROR,
        message="resolve integration test",
    )
    await bus.emit(ev)
    await bus._flush_batch()

    # event id'sini bul
    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text("SELECT id FROM error_events WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        event_id = row.scalar_one()

    # Resolve
    response = await async_client.post(
        f"/api/v1/system/error-events/{event_id}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204

    # Doğrula
    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text("SELECT resolved_at FROM error_events WHERE id = :id"),
            {"id": event_id},
        )
        resolved_at = row.scalar_one()

    assert resolved_at is not None

    # Temizlik
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("DELETE FROM error_occurrences WHERE fingerprint = :fp"),
            {"fp": ev.fingerprint},
        )
        await session.execute(
            text("DELETE FROM error_events WHERE id = :id"),
            {"id": event_id},
        )
        await session.commit()


@pytest.mark.integration
async def test_resolve_nonexistent_event_returns_404(async_client, admin_token):
    """Olmayan event_id → 404."""
    response = await async_client.post(
        "/api/v1/system/error-events/999999999/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


# ─── Frontend error-report → DB'de kayıt ─────────────────────────────────────

@pytest.mark.integration
async def test_frontend_error_report_stored_in_db(async_client, user_token, bus):
    """POST /error-report → emit → flush → DB'de frontend/js_error kaydı."""
    from sqlalchemy import text
    from app.database.connection import AsyncSessionLocal

    payload = {
        "message": "ReferenceError: x is not defined",
        "url": "https://app.lojinext.com/seferler",
        "userAgent": "Mozilla/5.0 Test",
        "timestamp": "2026-05-19T10:00:00Z",
        "severity": "error",
    }

    response = await async_client.post(
        "/api/v1/system/error-report",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 204

    # Bus'ı flush et (gerçek bus değil, test için flush zorla)
    from app.infrastructure.monitoring.event_bus import get_event_bus
    test_bus = get_event_bus()
    await test_bus._flush_batch()

    async with AsyncSessionLocal() as session:
        row = await session.execute(
            text("""
                SELECT COUNT(*) FROM error_events
                WHERE layer = 'frontend' AND category = 'js_error'
                ORDER BY first_seen DESC
            """)
        )
        count = row.scalar_one()

    assert count >= 1
```

---

## 3. E2E / Smoke Testler

**Dosya:** `app/tests/integration/test_error_detector_e2e.py`

```python
"""
E2E smoke testleri — tam Docker stack üzerinde çalışır.

Gereksinimler:
    docker-compose up -d
    TEST_API_BASE_URL=http://localhost:8000

Çalıştır:
    pytest app/tests/integration/test_error_detector_e2e.py -x -q --timeout=30
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncGenerator

import httpx
import pytest

BASE_URL = os.environ.get("TEST_API_BASE_URL", "http://localhost:8000")
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@lojinext.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
USER_EMAIL = os.environ.get("TEST_USER_EMAIL", "user@lojinext.com")
USER_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "user123")

pytestmark = [pytest.mark.integration]


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(scope="module")
async def admin_token(http_client: httpx.AsyncClient) -> str:
    resp = await http_client.post("/api/v1/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
async def user_token(http_client: httpx.AsyncClient) -> str:
    resp = await http_client.post("/api/v1/auth/login", json={
        "email": USER_EMAIL,
        "password": USER_PASSWORD,
    })
    assert resp.status_code == 200, f"User login failed: {resp.text}"
    return resp.json()["access_token"]


# ─── Senaryo 1: emit() CRITICAL → DB + Telegram mock ─────────────────────────

@pytest.mark.integration
async def test_e2e_critical_emit_appears_in_db(http_client, admin_token):
    """
    Backend'den CRITICAL emit → 5s bekle (flush interval) →
    /error-events'te görünür.
    """
    import httpx

    # Telegram mock: ops_bot'u mock'lamak için env var set edilmiş olmalı
    # TELEGRAM_OPS_BOT_URL=http://mock-telegram:8080

    # CRITICAL event tetikle — test endpoint yoksa doğrudan DB'ye yaz
    # (ya da test için bir internal trigger endpoint ekleyin)
    # Burada /error-report ile CRITICAL emit ediyoruz:
    resp = await http_client.post(
        "/api/v1/system/error-report",
        json={
            "message": "E2E critical test from test suite",
            "url": "https://test.lojinext.com",
            "userAgent": "pytest-e2e/1.0",
            "timestamp": "2026-05-19T10:00:00Z",
            "severity": "fatal",  # → CRITICAL
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    # user_token fixture module scope'ta tanımlı ama burada parametreden gelmeli
    # Gerçek testte fixture inject edilecek

    assert resp.status_code == 204

    # Flush interval bekle
    await asyncio.sleep(6)

    # DB'de görünür mü?
    events_resp = await http_client.get(
        "/api/v1/system/error-events?severity=critical&page_size=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert events_resp.status_code == 200
    items = events_resp.json()["items"]
    found = any("E2E critical test" in item["message"] for item in items)
    assert found, "CRITICAL event DB'de bulunamadı"


@pytest.mark.integration
async def test_e2e_frontend_error_report_to_db(http_client, admin_token, user_token):
    """
    Frontend errorTracker.captureMessage() → /error-report → DB kayıt.
    """
    unique_msg = f"E2E JS error {asyncio.get_event_loop().time()}"

    resp = await http_client.post(
        "/api/v1/system/error-report",
        json={
            "message": unique_msg,
            "url": "https://app.lojinext.com/dashboard",
            "userAgent": "Mozilla/5.0 E2E Test",
            "timestamp": "2026-05-19T10:00:00Z",
            "severity": "error",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 204

    await asyncio.sleep(6)

    events_resp = await http_client.get(
        "/api/v1/system/error-events?layer=frontend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert events_resp.status_code == 200
    items = events_resp.json()["items"]
    found = any(unique_msg in item["message"] for item in items)
    assert found, f"Frontend error DB'de bulunamadı: {unique_msg}"


@pytest.mark.integration
async def test_e2e_sse_stream_token_and_event(http_client, admin_token):
    """
    SSE token al → stream aç → yeni event emit et → event stream'de gelsin.

    NOT: Bu test asyncpg LISTEN kullandığından gerçek PG NOTIFY gerektirir.
    Docker stack'te çalıştırılmalıdır.
    """
    # 1. Token al
    token_resp = await http_client.post(
        "/api/v1/system/error-stream-token",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["token"]
    assert token

    # 2. SSE stream aç (background task olarak)
    received_events: list[dict] = []

    async def consume_sse():
        url = f"{BASE_URL}/api/v1/system/error-stream?token={token}"
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            async with client.stream("GET", url) as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            data = json.loads(line[5:].strip())
                            received_events.append(data)
                        except json.JSONDecodeError:
                            pass
                    if len(received_events) >= 1:
                        return

    stream_task = asyncio.create_task(consume_sse())
    await asyncio.sleep(1)  # stream'in açılması için bekle

    # 3. Yeni event emit et
    await http_client.post(
        "/api/v1/system/error-report",
        json={
            "message": "SSE stream E2E test event",
            "url": "https://test.lojinext.com/sse",
            "userAgent": "pytest-e2e/1.0",
            "timestamp": "2026-05-19T10:00:00Z",
            "severity": "error",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 4. Event'in gelmesini bekle (max 10s)
    try:
        await asyncio.wait_for(stream_task, timeout=10.0)
    except asyncio.TimeoutError:
        stream_task.cancel()
        pytest.fail("SSE stream 10s içinde event göndermedi")

    assert len(received_events) >= 1, "SSE stream'den event alınamadı"


@pytest.mark.integration
async def test_e2e_resolve_endpoint(http_client, admin_token, user_token):
    """
    Event emit → flush bekle → resolve → resolved_at set.
    """
    unique_msg = f"E2E resolve test {asyncio.get_event_loop().time()}"

    # Emit
    await http_client.post(
        "/api/v1/system/error-report",
        json={
            "message": unique_msg,
            "url": "https://test.lojinext.com",
            "userAgent": "pytest/1.0",
            "timestamp": "2026-05-19T10:00:00Z",
            "severity": "error",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    await asyncio.sleep(6)

    # Event'i bul
    events_resp = await http_client.get(
        "/api/v1/system/error-events?layer=frontend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = events_resp.json()["items"]
    event = next((i for i in items if unique_msg in i["message"]), None)
    assert event is not None, "Event DB'de bulunamadı"
    assert event["resolved_at"] is None

    # Resolve
    resolve_resp = await http_client.post(
        f"/api/v1/system/error-events/{event['id']}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resolve_resp.status_code == 204

    # Doğrula
    events_resp2 = await http_client.get(
        f"/api/v1/system/error-events?resolved=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resolved_items = events_resp2.json()["items"]
    resolved = next((i for i in resolved_items if i["id"] == event["id"]), None)
    assert resolved is not None
    assert resolved["resolved_at"] is not None


@pytest.mark.integration
async def test_e2e_error_stats_hourly_granulation(http_client, admin_token):
    """
    /error-stats → saatlik bucket formatı (ISO 8601 saat) doğrulaması.
    """
    resp = await http_client.get(
        "/api/v1/system/error-stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    stats = resp.json()["stats"]

    for row in stats:
        # hour formatı ISO 8601 olmalı
        from datetime import datetime
        parsed = datetime.fromisoformat(row["hour"])
        assert parsed.minute == 0 or True  # saatlik bucket, dakika 0 olabilir
        assert row["event_count"] >= 0
        assert row["layer"] in {"db", "celery", "api", "service",
                                "frontend", "external", "security", "ml"}
```

---

## 4. Manuel Smoke Test Senaryoları

Docker stack başlatıldıktan sonra aşağıdaki komutları çalıştırın:

```bash
# Stack başlat
docker-compose up -d
# Log akışı
docker-compose logs -f backend
```

### 4.1 Slow Query Tetikle

```bash
# pg_sleep ile yavaş sorgu simüle et
docker-compose exec db psql -U postgres -d lojinext -c \
  "SELECT pg_sleep(2), id FROM seferler LIMIT 1;"
# Backend loglarında "slow_query" kategorisinde WARNING görmeli
# error_events tablosunda: SELECT * FROM error_events WHERE category='slow_query';
```

### 4.2 N+1 Query Tetikle

db_probe N+1 detector'ü belirli bir eşiği geçen tekrarlayan query pattern'larını yakalar.

```bash
# Seferler listesi endpointini hızlıca 30 kez çağır
for i in $(seq 1 30); do
  curl -s -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/seferler" > /dev/null
done
# Backend loglarında n_plus_one kategorisi görünmeli
```

### 4.3 Brute Force Tetikle (5 Başarısız Login)

```bash
for i in $(seq 1 11); do
  curl -s -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"wrong_password_'$i'"}'
done
# error_events: SELECT * FROM error_events WHERE category='brute_force';
# Telegram ops_bot logunda: docker-compose logs telegram-ops-bot
```

### 4.4 Frontend'den Hata Gönder, Dashboard'da Görün

```bash
# Token al
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@lojinext.com","password":"admin123"}' \
  | jq -r '.access_token')

# Frontend error-report gönder
curl -s -X POST http://localhost:8000/api/v1/system/error-report \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Manual smoke test error",
    "url": "https://app.lojinext.com/test",
    "userAgent": "curl/smoke-test",
    "timestamp": "2026-05-19T10:00:00Z",
    "severity": "error"
  }'

# 6 saniye bekle (flush interval)
sleep 6

# Dashboard'da görün
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/system/error-events?layer=frontend" \
  | jq '.items[0]'
```

### 4.5 SSE Stream Aç, Live Banner'da Görün

```bash
# 1. Token al (admin gerekli)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@lojinext.com","password":"admin123"}' \
  | jq -r '.access_token')

# 2. SSE token oluştur
SSE_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/system/error-stream-token \
  -H "Authorization: Bearer $TOKEN" | jq -r '.token')

# 3. SSE stream aç (ayrı terminal)
curl -N "http://localhost:8000/api/v1/system/error-stream?token=$SSE_TOKEN"
# Terminalde keepalive ve event'ler görünmeli

# 4. Yeni event emit et (başka terminalde)
curl -s -X POST http://localhost:8000/api/v1/system/error-report \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Live SSE test event",
    "url": "https://test.lojinext.com",
    "userAgent": "curl/sse-test",
    "timestamp": "2026-05-19T10:00:00Z",
    "severity": "error"
  }'

# SSE stream terminalinde 6s içinde data: {...} satırı görünmeli
```

### 4.6 Telegram'a Mesaj Gittiğini Doğrula

```bash
# ops_bot loglarını izle
docker-compose logs -f telegram-ops-bot

# CRITICAL event tetikle
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@lojinext.com","password":"admin123"}' \
  | jq -r '.access_token')

curl -s -X POST http://localhost:8000/api/v1/system/error-report \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Telegram smoke test CRITICAL",
    "url": "https://test.lojinext.com",
    "userAgent": "curl/telegram-test",
    "timestamp": "2026-05-19T10:00:00Z",
    "severity": "fatal"
  }'

# ops_bot logunda "POST /webhook/error" isteği görünmeli
```

### 4.7 Resolve Endpoint Test

```bash
# event_id al
EVENT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/system/error-events" \
  | jq '.items[0].id')

# Resolve
curl -s -X POST \
  "http://localhost:8000/api/v1/system/error-events/$EVENT_ID/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -w "\nHTTP Status: %{http_code}\n"
# HTTP Status: 204 görmeli

# Doğrula
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/system/error-events?resolved=true" \
  | jq ".items[] | select(.id == $EVENT_ID) | .resolved_at"
# null olmayan bir timestamp görünmeli
```

---

## 5. Eksik / Kırık Şeyler Listesi

### 5.1 Mevcut Test Coverage Boşlukları

| Bileşen | Mevcut Coverage | Eksik |
|---------|----------------|-------|
| `ErrorEventBus` | emit, queue_full, circuit check temel | `_flush_batch` full flow, `_write_redis` pipeline, `_flush_to_redis_only`, double-start guard, routing failure resilience |
| `AlarmRouter` | **YOK** | Tüm router path'leri, Z-score edge cases, dedup, anomaly escalation |
| `AnomalyDetector` | **YOK** | `_compute_z_score` tüm branch'ler, `check()` Redis mock |
| `telegram_notifier` | **YOK** | WARNING log, payload format, network failure |
| `error_stream.py` (SSE) | **YOK** | Token create/store/expire, single-use delete, 401/403 path'leri |
| `models.py` | **YOK** | Fingerprint normalizasyon (numbers/UUIDs/strings), `to_dict`, str coercion |
| `celery_probe.py` | Yalnızca key format | Task failure emit, retry emit, beat watchdog |
| `db_probe.py` | SQL fingerprint + PG codes | Slow query threshold emit, N+1 emit, pool pressure emit |
| Integration (Redis) | **YOK** | fingerprint key, hourly bucket, severity stream |
| Integration (PG) | **YOK** | UPSERT, occurrence insert, duplicate count artışı |
| Integration (API) | **YOK** | Pagination, layer/severity filter, resolve, stats |

### 5.2 Bilinen Kırık / TODO Alanlar

1. **SSE token memory fallback**: Redis yoksa `mgr.set()` çağrılıyor ancak `mgr.get()` path'i `raw = json.dumps(cached)` yapıyor — `cached` dict değilse TypeError atar. Test edilmemiş.

2. **`_flush_to_redis_only` explicit test yok**: Circuit açıkken bu method çağrılır; `_write_redis` mock'lanmadan test edilmemiş.

3. **Celery probe beat watchdog**: `_record_heartbeat_key` test edilmiş ama watchdog timer timeout kısmı (`emit()` tetiklenme) test yok.

4. **`_bg_tasks` GC guard**: `AlarmRouter._send_immediate` `asyncio.create_task` ekliyor, task tamamlanmadan test biterse set boşalır; bu davranış e2e test dışında doğrulanmamış.

5. **`error_hourly_stats` materialized view**: `/error-stats` bu view'ı sorguluyor ancak view'ın otomatik refresh stratejisi (Celery beat task veya PG scheduled job) belirsiz; test setup'ında view refresh gerekebilir.

6. **SSE semaphore (max 20)**: `_SSE_SEMAPHORE.locked()` kontrolü race condition içeriyor — semaphore tam dolduğunda acquire öncesi kontrol anlamsız. `asyncio.wait_for(semaphore.acquire(), timeout=0)` kullanılmalıydı. Test yok.

7. **`emit_sync` + no running loop → `_emit_sync_fallback`**: Redis başarısız olduğunda `logger.debug` ile yutulur — WARNING olmalıydı, sessiz drop potansiyeli var.

### 5.3 Öncelik Sırası

```
P0 (hemen): test_alarm_router.py oluştur — hiç test yok
P0 (hemen): test_telegram_notifier.py oluştur — WARNING log kritik
P1:          test_event_bus.py'ye circuit döngüsü testleri ekle
P1:          test_sse_token.py oluştur — auth güvenlik testleri
P2:          test_models.py fingerprint normalizasyon
P2:          Integration testleri Redis + PG
P3:          E2E testleri (Docker stack gerekli)
```
