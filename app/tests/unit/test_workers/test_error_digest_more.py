"""Additional coverage for error_digest.py — _check_queue_depth, _create_partition,
create_monthly_partition, db_health_check, _db_health_check."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.platform_infra.background.error_digest import (
    _check_queue_depth,
    _create_partition,
    _db_health_check,
    _run_digest,
    create_monthly_partition,
    db_health_check,
)

pytestmark = pytest.mark.unit


# ─── _check_queue_depth ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_queue_depth_no_reserved():
    """inspect.reserved() returns None → function returns without emitting."""
    mock_inspect = MagicMock()
    mock_inspect.reserved = MagicMock(return_value=None)
    mock_app = MagicMock()
    mock_app.control.inspect.return_value = mock_inspect

    with patch("v2.modules.platform_infra.background.celery_app.celery_app", mock_app):
        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_aemit:
            await _check_queue_depth()
            mock_aemit.assert_not_called()


@pytest.mark.asyncio
async def test_check_queue_depth_low_queue():
    """Total tasks <= 100 → no event emitted."""
    mock_inspect = MagicMock()
    mock_inspect.reserved = MagicMock(return_value={"worker1": ["t1", "t2"]})
    mock_app = MagicMock()
    mock_app.control.inspect.return_value = mock_inspect

    with patch("v2.modules.platform_infra.background.celery_app.celery_app", mock_app):
        with patch(
            "v2.modules.platform_infra.monitoring.aemit", new_callable=AsyncMock
        ) as mock_aemit:
            await _check_queue_depth()
            mock_aemit.assert_not_called()


@pytest.mark.asyncio
async def test_check_queue_depth_warning_level():
    """Total 150 tasks (> 100 but <= 500) → WARNING severity emitted."""
    mock_inspect = MagicMock()
    mock_inspect.reserved = MagicMock(return_value={"worker1": ["t"] * 150})
    mock_app = MagicMock()
    mock_app.control.inspect.return_value = mock_inspect

    captured = []

    async def capture_emit(ev):
        captured.append(ev)

    with patch("v2.modules.platform_infra.background.celery_app.celery_app", mock_app):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture_emit):
            await _check_queue_depth()

    assert len(captured) == 1
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert captured[0].severity == ErrorSeverity.WARNING
    assert "150" in captured[0].message


@pytest.mark.asyncio
async def test_check_queue_depth_error_level():
    """Total 600 tasks (> 500) → ERROR severity emitted."""
    mock_inspect = MagicMock()
    mock_inspect.reserved = MagicMock(return_value={"worker1": ["t"] * 600})
    mock_app = MagicMock()
    mock_app.control.inspect.return_value = mock_inspect

    captured = []

    async def capture_emit(ev):
        captured.append(ev)

    with patch("v2.modules.platform_infra.background.celery_app.celery_app", mock_app):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture_emit):
            await _check_queue_depth()

    assert len(captured) == 1
    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert captured[0].severity == ErrorSeverity.ERROR


@pytest.mark.asyncio
async def test_check_queue_depth_exception_silenced():
    """Any exception in _check_queue_depth is silently logged (debug level)."""
    with patch(
        "v2.modules.platform_infra.background.celery_app.celery_app",
        side_effect=Exception("celery unavailable"),
    ):
        # Must not raise
        await _check_queue_depth()


# ─── _create_partition ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_partition_december_wraps_year():
    """December → two partitions created (current=Dec, next=Jan+1)."""
    import datetime
    import types

    # Build a fake datetime module whose date.today() returns Dec 1
    fake_date = MagicMock(spec=datetime.date)
    fake_date.today.return_value = datetime.date(2026, 12, 1)
    fake_date.side_effect = datetime.date  # constructor passthrough

    fake_dt_module = types.ModuleType("datetime")
    fake_dt_module.date = fake_date

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch.dict("sys.modules", {"datetime": fake_dt_module}):
        with patch(
            "v2.modules.platform_infra.database.connection.AsyncSessionLocal",
            return_value=mock_session,
        ):
            await _create_partition()

    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_partition_mid_year():
    """Normal month → both current and next month partitions created."""
    import datetime
    import types

    fake_date = MagicMock(spec=datetime.date)
    fake_date.today.return_value = datetime.date(2026, 6, 15)
    fake_date.side_effect = datetime.date

    fake_dt_module = types.ModuleType("datetime")
    fake_dt_module.date = fake_date

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    with patch.dict("sys.modules", {"datetime": fake_dt_module}):
        with patch(
            "v2.modules.platform_infra.database.connection.AsyncSessionLocal",
            return_value=mock_session,
        ):
            await _create_partition()

    # Two partitions → two executes
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_create_partition_execute_exception_continues():
    """Individual partition creation failure is logged, not re-raised; commit still called."""
    import datetime
    import types

    fake_date = MagicMock(spec=datetime.date)
    fake_date.today.return_value = datetime.date(2026, 3, 1)
    fake_date.side_effect = datetime.date

    fake_dt_module = types.ModuleType("datetime")
    fake_dt_module.date = fake_date

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(side_effect=Exception("partition exists"))
    mock_session.commit = AsyncMock()

    with patch.dict("sys.modules", {"datetime": fake_dt_module}):
        with patch(
            "v2.modules.platform_infra.database.connection.AsyncSessionLocal",
            return_value=mock_session,
        ):
            await _create_partition()

    mock_session.commit.assert_called_once()


def test_create_monthly_partition_task_name():
    """Task is registered with the correct name."""
    assert create_monthly_partition.name == "monitoring.create_monthly_partition"


# ─── db_health_check Celery task ──────────────────────────────────────────────


def test_db_health_check_celery_task_name():
    """Task is registered with the correct name."""
    assert db_health_check.name == "monitoring.db_health_check"


def test_db_health_check_greenlet_runtime_error_suppressed():
    """RuntimeError with 'greenlet' substring is caught and logged, not re-raised."""
    with patch(
        "v2.modules.platform_infra.background.error_digest._db_health_check",
        side_effect=RuntimeError("greenlet_spawn not called"),
    ):
        # Should not raise
        db_health_check()


def test_db_health_check_different_loop_runtime_error_suppressed():
    """RuntimeError with 'different loop' is caught."""
    with patch(
        "v2.modules.platform_infra.background.error_digest._db_health_check",
        side_effect=RuntimeError("attached to a different loop"),
    ):
        db_health_check()


def test_db_health_check_other_runtime_error_reraises():
    """RuntimeError without greenlet/loop fingerprint is re-raised."""
    with patch(
        "v2.modules.platform_infra.background.error_digest._db_health_check",
        side_effect=RuntimeError("some other error"),
    ):
        with pytest.raises(RuntimeError, match="some other error"):
            db_health_check()


# ─── _db_health_check async ───────────────────────────────────────────────────


def _make_row(
    pid=123,
    duration_sec=60,
    query_excerpt="SELECT 1",
    state="active",
    wait_sec=10,
    blocked_pid=1,
    blocking_pid=2,
    blocked_query="SELECT 2",
    relname="seferler",
    n_dead_tup=10000,
    n_live_tup=40000,
    dead_pct=20.0,
):
    row = MagicMock()
    row.pid = pid
    row.duration_sec = duration_sec
    row.query_excerpt = query_excerpt
    row.state = state
    row.wait_sec = wait_sec
    row.blocked_pid = blocked_pid
    row.blocking_pid = blocking_pid
    row.blocked_query = blocked_query
    row.relname = relname
    row.n_dead_tup = n_dead_tup
    row.n_live_tup = n_live_tup
    row.dead_pct = dead_pct
    return row


@pytest.mark.asyncio
async def test_db_health_check_long_running_tx_emits():
    """Long-running TX rows → aemit called for each."""
    long_tx_row = _make_row(duration_sec=60)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # 3 execute calls: long_tx, lock_wait, bloat
    mock_session.execute = AsyncMock(
        side_effect=[
            iter([long_tx_row]),  # long running tx
            iter([]),  # lock wait
            iter([]),  # bloat
        ]
    )

    emitted = []

    async def capture(ev):
        emitted.append(ev)

    with patch("v2.modules.platform_infra.database.connection.AsyncSessionLocal", return_value=mock_session):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture):
            await _db_health_check()

    assert len(emitted) == 1
    assert "long_running_tx" in emitted[0].category


@pytest.mark.asyncio
async def test_db_health_check_critical_tx_severity():
    """TX lasting > 120s → CRITICAL severity."""
    critical_row = _make_row(duration_sec=150)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        side_effect=[
            iter([critical_row]),
            iter([]),
            iter([]),
        ]
    )

    emitted = []

    async def capture(ev):
        emitted.append(ev)

    with patch("v2.modules.platform_infra.database.connection.AsyncSessionLocal", return_value=mock_session):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture):
            await _db_health_check()

    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert emitted[0].severity == ErrorSeverity.CRITICAL


@pytest.mark.asyncio
async def test_db_health_check_lock_wait_emits():
    """Lock wait rows → aemit called with lock_wait category."""
    lock_row = _make_row(wait_sec=5)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        side_effect=[
            iter([]),  # no long tx
            iter([lock_row]),  # one lock wait
            iter([]),  # no bloat
        ]
    )

    emitted = []

    async def capture(ev):
        emitted.append(ev)

    with patch("v2.modules.platform_infra.database.connection.AsyncSessionLocal", return_value=mock_session):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture):
            await _db_health_check()

    assert len(emitted) == 1
    assert "lock_wait" in emitted[0].category


@pytest.mark.asyncio
async def test_db_health_check_lock_wait_critical_above_15s():
    """Lock wait > 15s → CRITICAL severity."""
    lock_row = _make_row(wait_sec=20)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        side_effect=[
            iter([]),
            iter([lock_row]),
            iter([]),
        ]
    )

    emitted = []

    async def capture(ev):
        emitted.append(ev)

    with patch("v2.modules.platform_infra.database.connection.AsyncSessionLocal", return_value=mock_session):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture):
            await _db_health_check()

    from v2.modules.platform_infra.monitoring.models import ErrorSeverity

    assert emitted[0].severity == ErrorSeverity.CRITICAL


@pytest.mark.asyncio
async def test_db_health_check_table_bloat_emits():
    """Bloat rows → aemit called with table_bloat category."""
    bloat_row = _make_row(relname="seferler", dead_pct=25.0, n_dead_tup=10000)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        side_effect=[
            iter([]),
            iter([]),
            iter([bloat_row]),
        ]
    )

    emitted = []

    async def capture(ev):
        emitted.append(ev)

    with patch("v2.modules.platform_infra.database.connection.AsyncSessionLocal", return_value=mock_session):
        with patch("v2.modules.platform_infra.monitoring.aemit", side_effect=capture):
            await _db_health_check()

    assert len(emitted) == 1
    assert "table_bloat" in emitted[0].category
    assert "seferler" in emitted[0].message


@pytest.mark.asyncio
async def test_run_digest_triggers_check_beat_and_queue_depth():
    """_run_digest calls check_beat_health and _check_queue_depth after sending digest."""
    redis_mock = AsyncMock()
    # Return one key as str so split works (aioredis returns str by default)
    redis_mock.keys = AsyncMock(return_value=["error:digest:api:auth"])
    pipe = MagicMock()
    pipe.hgetall = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[{"count": "1", "message_sample": "error"}])
    del_pipe = MagicMock()
    del_pipe.delete = MagicMock(return_value=del_pipe)
    del_pipe.execute = AsyncMock(return_value=[1])
    redis_mock.pipeline = MagicMock(side_effect=[pipe, del_pipe])

    mock_sess = AsyncMock()
    mock_sess.__aenter__ = AsyncMock(return_value=mock_sess)
    mock_sess.__aexit__ = AsyncMock(return_value=False)
    mock_sess.execute = AsyncMock()
    mock_sess.commit = AsyncMock()

    with patch("v2.modules.platform_infra.cache.redis_pubsub.get_pubsub_manager") as mock_mgr:
        mock_mgr.return_value.redis = redis_mock
        with patch("v2.modules.platform_infra.background.error_digest._drain_sync_fallback"):
            with patch(
                "v2.modules.notification.public.notify_error",
                new_callable=AsyncMock,
            ):
                with patch(
                    "v2.modules.platform_infra.database.connection.AsyncSessionLocal",
                    return_value=mock_sess,
                ):
                    with patch(
                        "v2.modules.platform_infra.monitoring.celery_probe.check_beat_health",
                        new_callable=AsyncMock,
                    ) as mock_beat:
                        with patch(
                            "v2.modules.platform_infra.background.error_digest._check_queue_depth",
                            new_callable=AsyncMock,
                        ) as mock_depth:
                            await _run_digest()

    mock_beat.assert_called_once()
    mock_depth.assert_called_once()
