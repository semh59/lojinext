"""dlq_tasks.py unit tests.

Split off app/tests/unit/test_worker_tasks.py (Task 5, 2026-08-04):
prediction.drain_dlq moved to this service's own dlq_tasks.py, path-only
change (Redis DLQ draining logic itself is unchanged).
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

DLQ_MODULE = "prediction_ml_service.infrastructure.dlq_tasks"


class TestDrainPredictionDlq:
    def test_empty_queue(self):
        """Empty queue returns {drained: 0}."""
        mock_redis = MagicMock()
        mock_redis.rpop.return_value = None

        with patch(f"{DLQ_MODULE}.redis.Redis.from_url", return_value=mock_redis):
            from prediction_ml_service.infrastructure.dlq_tasks import (
                drain_prediction_dlq,
            )

            result = drain_prediction_dlq.run()

        assert result == {"drained": 0}

    def test_items_in_queue(self):
        """Logs each queued item, returns the drained count."""
        import json

        payloads = [
            json.dumps({"task_id": "abc", "error": "timeout"}).encode(),
            json.dumps({"task_id": "def", "error": "oom"}).encode(),
            None,  # queue empty
        ]
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = payloads

        with patch(f"{DLQ_MODULE}.redis.Redis.from_url", return_value=mock_redis):
            from prediction_ml_service.infrastructure.dlq_tasks import (
                drain_prediction_dlq,
            )

            result = drain_prediction_dlq.run()

        assert result["drained"] == 2
        assert "timestamp" in result

    def test_malformed_json_item(self):
        """Malformed JSON item handled gracefully, drained=1."""
        payloads = [b"not-valid-json", None]
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = payloads

        with patch(f"{DLQ_MODULE}.redis.Redis.from_url", return_value=mock_redis):
            from prediction_ml_service.infrastructure.dlq_tasks import (
                drain_prediction_dlq,
            )

            result = drain_prediction_dlq.run()

        assert result["drained"] == 1

    def test_requeue_flag_noop(self):
        """requeue=True does not raise (currently just logs + requeues)."""
        import json

        payloads = [
            json.dumps({"task_id": "xyz"}).encode(),
            None,
        ]
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = payloads

        with patch(f"{DLQ_MODULE}.redis.Redis.from_url", return_value=mock_redis):
            from prediction_ml_service.infrastructure.dlq_tasks import (
                drain_prediction_dlq,
            )

            result = drain_prediction_dlq.run(requeue=True)

        assert result["drained"] == 1
