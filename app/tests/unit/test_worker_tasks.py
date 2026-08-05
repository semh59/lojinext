"""
Unit Tests — Celery Worker Tasks (main backend)
Mocks: outbox_service.

dlq_tasks (prediction.drain_dlq) and prediction_tasks (prediction.generate)
moved to v2/services/prediction_ml_service's own Celery app (Task 5,
2026-08-04) -- their tests moved with them to
v2/services/prediction_ml_service/tests/test_dlq_tasks.py and
test_prediction_tasks.py. driver_tasks (orphan Celery task, never
registered to a worker, no .delay()/.apply_async() caller anywhere) was
deleted 2026-07-18 as dead code, taking its tests with it.
"""

from unittest.mock import AsyncMock, MagicMock, patch


class TestRelayOutboxEvents:
    def test_relays_events(self):
        """No exception when relay_pending_events is called."""
        mock_service = MagicMock()
        mock_service.relay_pending_events = AsyncMock(return_value=3)

        with patch(
            "v2.modules.shared_kernel.infrastructure.outbox.get_outbox_service",
            return_value=mock_service,
        ):
            from v2.modules.shared_kernel.infrastructure.outbox_tasks import (
                relay_outbox_events,
            )

            relay_outbox_events.run()  # should complete without exception

    def test_no_events(self):
        """No exception when relay_pending_events returns 0."""
        mock_service = MagicMock()
        mock_service.relay_pending_events = AsyncMock(return_value=0)

        with patch(
            "v2.modules.shared_kernel.infrastructure.outbox.get_outbox_service",
            return_value=mock_service,
        ):
            from v2.modules.shared_kernel.infrastructure.outbox_tasks import (
                relay_outbox_events,
            )

            relay_outbox_events.run()
