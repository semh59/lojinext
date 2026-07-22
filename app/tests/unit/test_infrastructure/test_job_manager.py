"""
Unit tests for BackgroundJobManager.

Uses asyncio.create_task-compatible patterns; tests await tasks to completion
before asserting on final status.

Redis is replaced with an in-memory fake via BackgroundJobManager._redis_override
so tests run without a live Redis instance.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.background.job_manager import (
    AsyncJobStatus,
    BackgroundJobManager,
    get_job_manager,
)

pytestmark = pytest.mark.unit


class _FakeRedis:
    """Minimal in-memory Redis substitute for unit tests."""

    def __init__(self):
        self._store: dict = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value, ex=None):  # noqa: ARG002
        self._store[key] = value


@pytest.fixture(autouse=True)
def reset_job_manager():
    """Reset the singleton and inject an in-memory fake Redis between tests."""
    BackgroundJobManager._instance = None
    BackgroundJobManager._redis_override = _FakeRedis()
    yield
    BackgroundJobManager._instance = None
    BackgroundJobManager._redis_override = None


class TestAsyncJobStatusEnum:
    def test_values_match_public_contract(self):
        """2026-07-01 prod-grade denetimi P2 (Tier B madde 9): PROCESSING/
        SUCCESS/FAILED eskiden admin_predictions.py/fuel.py/trips.py'de 6
        yerde ayrı string literal olarak tekrarlanıyordu. Artık merkezi bir
        enum var — bu test sözleşmenin (literal değerlerin) değişmediğini
        kilitliyor (frontend bu tam string'leri bekliyor)."""
        assert AsyncJobStatus.PROCESSING.value == "PROCESSING"
        assert AsyncJobStatus.SUCCESS.value == "SUCCESS"
        assert AsyncJobStatus.FAILED.value == "FAILED"
        # str, Enum karışımı — JSON serileştirmede/response'ta doğrudan
        # düz string gibi davranmalı (FastAPI JSONResponse content= içinde
        # kullanılabilir olması için).
        assert AsyncJobStatus.PROCESSING == "PROCESSING"


class TestJobManager:
    async def test_basic_initialization(self):
        """BackgroundJobManager initialises with an empty tasks dict."""
        mgr = BackgroundJobManager()

        assert isinstance(mgr._tasks, dict)
        assert len(mgr._tasks) == 0

    async def test_happy_path(self):
        """submit() returns a job_id; completed job has status 'completed'."""
        mgr = BackgroundJobManager()

        async def simple_task():
            return "task_result"

        job_id = await mgr.submit(simple_task)
        assert isinstance(job_id, str)
        assert len(job_id) > 0

        # Wait for the task to complete
        await asyncio.sleep(0)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert status["status"] == "completed"
        assert status["result"] == "task_result"
        assert status["error"] is None

    async def test_error_handling(self):
        """Failed job records status 'failed' and stores error message."""
        mgr = BackgroundJobManager()

        async def failing_task():
            raise ValueError("task failed badly")

        job_id = await mgr.submit(failing_task)

        # Wait for the task
        try:
            await mgr._tasks[job_id]
        except Exception:
            pass

        status = mgr.get_status(job_id)
        assert status["status"] == "failed"
        assert "task failed badly" in status["error"]
        assert status["result"] is None

    async def test_edge_case_empty(self):
        """get_status() for unknown job_id returns 'unknown' status."""
        mgr = BackgroundJobManager()

        status = mgr.get_status("nonexistent-job-id")

        assert status["status"] == "unknown"
        assert status["result"] is None
        assert status["error"] is None

    async def test_edge_case_none(self):
        """Sync callable is also accepted by submit()."""
        mgr = BackgroundJobManager()

        def sync_task():
            return "sync_done"

        job_id = await mgr.submit(sync_task)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert status["status"] == "completed"
        assert status["result"] == "sync_done"

    async def test_integration_with_mock(self):
        """Multiple jobs can be submitted concurrently and all complete."""
        mgr = BackgroundJobManager()

        async def counter_task(n: int):
            return n * 2

        job_ids = []
        for i in range(3):
            jid = await mgr.submit(counter_task, i)
            job_ids.append(jid)

        # Wait for all tasks
        await asyncio.gather(*[mgr._tasks[jid] for jid in job_ids])

        for i, jid in enumerate(job_ids):
            status = mgr.get_status(jid)
            assert status["status"] == "completed"
            assert status["result"] == i * 2

    async def test_return_type_validation(self):
        """get_status() returns dict with all expected keys."""
        mgr = BackgroundJobManager()

        async def noop():
            return None

        job_id = await mgr.submit(noop)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert isinstance(status, dict)
        expected_keys = {
            "id",
            "status",
            "result",
            "error",
            "created_at",
            "finished_at",
            "timestamp",
        }
        assert expected_keys.issubset(set(status.keys()))

    def test_service_exists(self):
        """get_job_manager() returns a BackgroundJobManager instance."""
        mgr = get_job_manager()

        assert isinstance(mgr, BackgroundJobManager)

    async def test_singleton_pattern(self):
        """Two instantiations return the same object."""
        mgr1 = BackgroundJobManager()
        mgr2 = BackgroundJobManager()

        assert mgr1 is mgr2

    async def test_job_has_created_at_timestamp(self):
        """submitted job gets a created_at timestamp."""
        mgr = BackgroundJobManager()

        async def noop():
            return True

        job_id = await mgr.submit(noop)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert status["created_at"] is not None
        # Should be a valid ISO timestamp string
        datetime.fromisoformat(status["created_at"])

    async def test_finished_at_set_after_completion(self):
        """finished_at is populated once the job completes."""
        mgr = BackgroundJobManager()

        async def quick():
            return "done"

        job_id = await mgr.submit(quick)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert status["finished_at"] is not None
        datetime.fromisoformat(status["finished_at"])

    async def test_cleanup_is_noop(self):
        """cleanup() is a no-op; Redis TTL (24 h) handles expiry automatically."""
        mgr = BackgroundJobManager()

        async def quick():
            return "done"

        job_id = await mgr.submit(quick)
        await mgr._tasks[job_id]

        mgr.cleanup(max_age_seconds=0)

        # Job still visible (TTL not expired, no manual deletion)
        status = mgr.get_status(job_id)
        assert status["status"] == "completed"

    async def test_kwargs_forwarded_to_task(self):
        """Keyword arguments are forwarded correctly to the async function."""
        mgr = BackgroundJobManager()

        async def add(a: int, b: int = 0) -> int:
            return a + b

        job_id = await mgr.submit(add, 10, b=5)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert status["result"] == 15

    async def test_get_status_detects_stale_running_job_after_worker_restart(self):
        """2026-07-01 prod-grade denetimi P1 (Dalga 3 madde 17): job durumu
        sadece in-process asyncio task'a bağlıydı — worker restart olduğunda
        Redis'teki kayıt sonsuza dek 'running' kalıyordu, frontend
        `useTaskStatus` sonsuz poll ediyordu. Artık her job bir `heartbeat_at`
        taşıyor; `get_status()` 'running' bir job'ın heartbeat'i çok eskiyse
        (worker restart varsayımı) kaydı kendiliğinden 'failed'e çeviriyor.
        """
        mgr = BackgroundJobManager()
        job_id = "stale-job-1"
        stale_ts = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
        mgr._write_job(
            job_id,
            {
                "status": "running",
                "result": None,
                "error": None,
                "created_at": stale_ts,
                "finished_at": None,
                "heartbeat_at": stale_ts,
            },
        )

        status = mgr.get_status(job_id)

        assert status["status"] == "failed"
        assert status["error"]
        assert "restart" in status["error"].lower()

    async def test_get_status_does_not_flag_fresh_running_job_as_stale(self):
        """Regresyon guard'ı: gerçekten hâlâ çalışan (yakın zamanlı heartbeat)
        bir job yanlışlıkla 'failed'e çevrilmemeli."""
        mgr = BackgroundJobManager()
        job_id = "fresh-running-job"
        fresh_ts = datetime.now(timezone.utc).isoformat()
        mgr._write_job(
            job_id,
            {
                "status": "running",
                "result": None,
                "error": None,
                "created_at": fresh_ts,
                "finished_at": None,
                "heartbeat_at": fresh_ts,
            },
        )

        status = mgr.get_status(job_id)

        assert status["status"] == "running"

    async def test_task_does_not_inherit_callers_session_context(self):
        """Regression: asyncio.create_task() copies the caller's context by
        default. If the caller is a request handler with an active
        UnitOfWork (its _session_ctx contextvar set), the submitted task
        used to "re-enter" that same UoW and reuse the request's
        AsyncSession (UnitOfWork.__aenter__'s reuse-on-re-entry logic) —
        that session gets torn down once the request returns while the
        background task keeps running on it, so asyncpg raises "cannot
        perform operation: another operation is in progress" (caught live
        in CI run 29192467229, GET /trips/{id}/cost-analysis). submit()
        must run the task in a context where _session_ctx is reset to its
        default (None) so func's own UnitOfWork opens an independent
        session."""
        from v2.modules.platform_infra.database.db_session import _session_ctx

        mgr = BackgroundJobManager()
        seen_session_ctx = {}

        async def reads_session_ctx():
            seen_session_ctx["value"] = _session_ctx.get()
            return "done"

        # Simulate an active request-scoped UnitOfWork session at the
        # moment submit() is called.
        token = _session_ctx.set("fake-request-session")  # type: ignore[arg-type]
        try:
            job_id = await mgr.submit(reads_session_ctx)
            await mgr._tasks[job_id]
        finally:
            _session_ctx.reset(token)

        assert seen_session_ctx["value"] is None

    async def test_task_still_inherits_correlation_id(self):
        """Regression guard for the fix above: only _session_ctx should be
        reset — correlation_id/user_id (used for audit-log attribution of
        background-job side effects) must still propagate to the task."""
        from v2.modules.platform_infra.context.request_context import (
            get_correlation_id,
            set_correlation_id,
        )

        mgr = BackgroundJobManager()
        seen_correlation_id = {}

        async def reads_correlation_id():
            seen_correlation_id["value"] = get_correlation_id()
            return "done"

        set_correlation_id("test-correlation-id-123")
        job_id = await mgr.submit(reads_correlation_id)
        await mgr._tasks[job_id]

        assert seen_correlation_id["value"] == "test-correlation-id-123"

    async def test_non_json_result_is_stringified(self):
        """Results that are not JSON-serializable are stored as strings."""
        mgr = BackgroundJobManager()

        class _Unserializable:
            pass

        async def returns_object():
            return _Unserializable()

        job_id = await mgr.submit(returns_object)
        await mgr._tasks[job_id]

        status = mgr.get_status(job_id)
        assert status["status"] == "completed"
        assert isinstance(status["result"], str)
