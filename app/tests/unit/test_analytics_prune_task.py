"""analytics.prune_page_views task wrapper testi."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_prune_task_invokes_repo_and_returns_count():
    @asynccontextmanager
    async def fake_scope():
        yield MagicMock()

    with (
        patch("app.workers.tasks.analytics_tasks.session_scope", fake_scope),
        patch("app.workers.tasks.analytics_tasks.PageViewRepository") as repo_cls,
    ):
        repo_cls.return_value.prune_older_than = AsyncMock(return_value=7)
        from app.workers.tasks.analytics_tasks import prune_page_views

        result = prune_page_views.run()

    assert result == {"deleted": 7}
