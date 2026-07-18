"""
Unit Tests — Celery Worker Tasks
Mock'lar: Redis, AsyncSession, outbox_service, UnitOfWork
CELERY_EAGER=True (settings.py) → görevler senkron çalışır.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ── dlq_tasks ─────────────────────────────────────────────────────────────────


class TestDrainPredictionDlq:
    def test_empty_queue(self):
        """Boş kuyrukta {drained: 0} döner."""
        mock_redis = MagicMock()
        mock_redis.rpop.return_value = None  # kuyruk boş

        with patch(
            "app.workers.tasks.dlq_tasks.redis.Redis.from_url", return_value=mock_redis
        ):
            from app.workers.tasks.dlq_tasks import drain_prediction_dlq

            result = drain_prediction_dlq.run()

        assert result == {"drained": 0}

    def test_items_in_queue(self):
        """Kuyruktaki her öğeyi log'lar, drained sayısını döner."""
        import json

        payloads = [
            json.dumps({"task_id": "abc", "error": "timeout"}).encode(),
            json.dumps({"task_id": "def", "error": "oom"}).encode(),
            None,  # kuyruk bitiyor
        ]
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = payloads

        with patch(
            "app.workers.tasks.dlq_tasks.redis.Redis.from_url", return_value=mock_redis
        ):
            from app.workers.tasks.dlq_tasks import drain_prediction_dlq

            result = drain_prediction_dlq.run()

        assert result["drained"] == 2
        assert "timestamp" in result

    def test_malformed_json_item(self):
        """Bozuk JSON öğe handled gracefully, drained=1."""
        payloads = [b"not-valid-json", None]
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = payloads

        with patch(
            "app.workers.tasks.dlq_tasks.redis.Redis.from_url", return_value=mock_redis
        ):
            from app.workers.tasks.dlq_tasks import drain_prediction_dlq

            result = drain_prediction_dlq.run()

        assert result["drained"] == 1

    def test_requeue_flag_noop(self):
        """requeue=True geçilince hata olmaz (şu an sadece log)."""
        import json

        payloads = [
            json.dumps({"task_id": "xyz"}).encode(),
            None,
        ]
        mock_redis = MagicMock()
        mock_redis.rpop.side_effect = payloads

        with patch(
            "app.workers.tasks.dlq_tasks.redis.Redis.from_url", return_value=mock_redis
        ):
            from app.workers.tasks.dlq_tasks import drain_prediction_dlq

            result = drain_prediction_dlq.run(requeue=True)

        assert result["drained"] == 1


# ── outbox_tasks ──────────────────────────────────────────────────────────────


class TestRelayOutboxEvents:
    def test_relays_events(self):
        """relay_pending_events çağrıldığında hata çıkmaz."""
        mock_service = MagicMock()
        mock_service.relay_pending_events = AsyncMock(return_value=3)

        with patch(
            "app.infrastructure.events.outbox_service.get_outbox_service",
            return_value=mock_service,
        ):
            from app.workers.tasks.outbox_tasks import relay_outbox_events

            relay_outbox_events.run()  # should complete without exception

    def test_no_events(self):
        """relay_pending_events 0 döndüğünde de hata olmaz."""
        mock_service = MagicMock()
        mock_service.relay_pending_events = AsyncMock(return_value=0)

        with patch(
            "app.infrastructure.events.outbox_service.get_outbox_service",
            return_value=mock_service,
        ):
            from app.workers.tasks.outbox_tasks import relay_outbox_events

            relay_outbox_events.run()


# ── driver_tasks: orphan Celery task (v2.modules.driver.infrastructure.
# driver_tasks) SİLİNDİ 2026-07-18 — hiçbir zaman worker'a kayıtlı olmayan,
# hiçbir .delay()/.apply_async() çağıranı olmayan dead code'du (bkz.
# v2/modules/driver/CLAUDE.md). Bu testler dosyasıyla birlikte kaldırıldı.


# ── prediction_tasks ──────────────────────────────────────────────────────────


class TestRunPredictionTask:
    def test_cache_hit_returns_cached_result(self):
        """Redis'te sonuç varsa DB'ye gitmeden döner."""
        import json

        cached = {
            "status": "completed",
            "answer": "Cached answer",
            "finished_at": "2025-01-01T00:00:00",
        }
        mock_redis = MagicMock()
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = json.dumps(cached).encode()

        mock_llm = MagicMock()

        with (
            patch(
                "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
                return_value=mock_redis,
            ),
            patch(
                "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client",
                return_value=mock_llm,
            ),
        ):
            from v2.modules.prediction_ml.infrastructure.prediction_tasks import (
                run_prediction_task,
            )

            result = run_prediction_task.run("test question")

        assert result["status"] == "completed"
        assert result["answer"] == "Cached answer"
        mock_llm.chat.assert_not_called()

    def test_successful_prediction(self):
        """LLM cevap verirse sonuç cache'e yazılır ve döner."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = False
        mock_redis.setex.return_value = True

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(return_value="Yakıt tüketimi normaldir.")

        async def fake_persist(**_kwargs):
            pass

        with (
            patch(
                "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
                return_value=mock_redis,
            ),
            patch(
                "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client",
                return_value=mock_llm,
            ),
            patch("v2.modules.prediction_ml.infrastructure.prediction_tasks._persist", new=AsyncMock()),
        ):
            from v2.modules.prediction_ml.infrastructure.prediction_tasks import (
                run_prediction_task,
            )

            result = run_prediction_task.run(
                "Yakıt neden yüksek?", context="TIR takip sistemi"
            )

        assert result["status"] == "completed"
        assert "Yakıt tüketimi" in result["answer"]

    def test_failed_prediction_dlq_path(self):
        """_persist doğrudan test: status=failed kaydı yazar."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.AsyncSessionLocal",
            return_value=mock_session,
        ):
            from v2.modules.prediction_ml.infrastructure.prediction_tasks import (
                _persist,
            )

            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                _persist(task_id="abc-123", status="failed", error="LLM timeout")
            )
            loop.close()

        mock_session.commit.assert_awaited_once()

    def test_persist_best_effort_db_failure(self):
        """DB yazımı başarısız olursa _persist sessizce geçer."""
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.AsyncSessionLocal"
        ) as mock_session_cls:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB conn failed"))
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            from v2.modules.prediction_ml.infrastructure.prediction_tasks import (
                _persist,
            )

            # Should not raise. asyncio.run() — get_event_loop() Py3.12+'da çalışan
            # loop yokken RuntimeError verir (üretim kodu zaten asyncio.run kullanır).
            asyncio.run(_persist(task_id="abc", status="success", answer="test"))
