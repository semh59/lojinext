"""Celery task registration and basic behavior tests."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestCeleryTasks:
    def test_service_exists(self):
        """celery_app is importable and is a Celery instance."""
        from app.infrastructure.background.celery_app import celery_app

        assert celery_app is not None
        # Has the standard Celery attributes
        assert hasattr(celery_app, "task")
        assert hasattr(celery_app, "conf")

    def test_relay_outbox_events_is_registered(self):
        """relay_outbox_events task is registered with the correct name."""
        from app.workers.tasks.outbox_tasks import relay_outbox_events

        assert relay_outbox_events.name == "infrastructure.relay_outbox_events"

    def test_error_digest_task_is_registered(self):
        """error_digest task is registered with the correct name."""
        from app.workers.tasks.error_digest import error_digest

        assert error_digest.name == "monitoring.error_digest"

    def test_prediction_task_is_registered(self):
        """run_prediction_task is registered with correct name."""
        from v2.modules.prediction_ml.infrastructure.prediction_tasks import (
            run_prediction_task,
        )

        assert run_prediction_task.name == "prediction.generate"

    def test_prediction_task_max_retries(self):
        """run_prediction_task has max_retries=3."""
        from v2.modules.prediction_ml.infrastructure.prediction_tasks import (
            run_prediction_task,
        )

        assert run_prediction_task.max_retries == 3

    def test_relay_outbox_events_max_retries(self):
        """relay_outbox_events task has max_retries=5."""
        from app.workers.tasks.outbox_tasks import relay_outbox_events

        assert relay_outbox_events.max_retries == 5

    def test_relay_outbox_events_acks_late(self):
        """relay_outbox_events uses acks_late=True for at-least-once delivery."""
        from app.workers.tasks.outbox_tasks import relay_outbox_events

        assert relay_outbox_events.acks_late is True

    async def test_basic_initialization(self):
        """celery_app conf has a broker_url set."""
        from app.infrastructure.background.celery_app import celery_app

        # In test env, CELERY_EAGER mode or redis URL is configured
        assert celery_app.conf.broker_url is not None

    def test_relay_outbox_events_retries_on_connection_error(self):
        """relay_outbox_events raises (retries) when a ConnectionError occurs."""
        from app.workers.tasks.outbox_tasks import relay_outbox_events

        # engine is imported locally inside the task; mock it at source
        mock_engine = MagicMock()
        mock_engine.sync_engine = MagicMock()

        import app.database.connection as db_connection_mod

        orig_engine = db_connection_mod.engine
        db_connection_mod.engine = mock_engine
        try:
            # CELERY_EAGER=True in test env: apply() runs the task inline.
            # asyncio.run raising ConnectionError should surface as an exception.
            with patch("asyncio.run", side_effect=ConnectionError("Redis down")):
                with pytest.raises(Exception):
                    relay_outbox_events.apply().get(propagate=True)
        finally:
            db_connection_mod.engine = orig_engine

    def test_error_digest_task_ignore_result(self):
        """error_digest is configured with ignore_result=True (fire-and-forget)."""
        from app.workers.tasks.error_digest import error_digest

        assert error_digest.ignore_result is True

    async def test_edge_case_none(self):
        """celery_app beat_schedule is a dict (may be empty but present)."""
        from app.infrastructure.background.celery_app import celery_app

        assert isinstance(celery_app.conf.beat_schedule, dict)

    async def test_return_type_validation(self):
        """All registered task names in the app are strings."""
        from app.infrastructure.background.celery_app import celery_app

        for name in celery_app.tasks:
            assert isinstance(name, str)

    async def test_integration_with_mock(self):
        """relay_outbox_events can be found by name in the celery task registry."""
        from app.infrastructure.background.celery_app import celery_app

        assert "infrastructure.relay_outbox_events" in celery_app.tasks
