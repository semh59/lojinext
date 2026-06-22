import asyncio

import pytest

from app.infrastructure.background.job_manager import get_job_manager


class TestBackgroundJobManager:
    """Background Job Manager Verification Tests"""

    @pytest.mark.asyncio
    async def test_submit_async_job(self):
        """Test submitting an async job and retrieving result"""
        manager = get_job_manager()

        async def sample_task(x, y):
            await asyncio.sleep(0.1)
            return x + y

        job_id = await manager.submit(sample_task, 10, 20)
        assert job_id is not None

        # Wait for completion (Job Manager is "fire and forget" but runs in event loop)
        await asyncio.sleep(0.2)

        status = manager.get_status(job_id)
        assert status["status"] == "completed"
        assert status["result"] == 30

    @pytest.mark.asyncio
    async def test_submit_sync_job(self):
        """Test submitting a sync job (should be wrapped)"""
        manager = get_job_manager()

        def sync_task(name):
            return f"Hello {name}"

        job_id = await manager.submit(sync_task, "World")

        await asyncio.sleep(0.1)

        status = manager.get_status(job_id)
        assert status["status"] == "completed"
        assert status["result"] == "Hello World"

    @pytest.mark.asyncio
    async def test_failed_job(self):
        """Test job failure handling"""
        manager = get_job_manager()

        async def failing_task():
            raise ValueError("Intentional Error")

        job_id = await manager.submit(failing_task)

        await asyncio.sleep(0.1)

        status = manager.get_status(job_id)
        assert status["status"] == "failed"
        assert "Intentional Error" in status["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
