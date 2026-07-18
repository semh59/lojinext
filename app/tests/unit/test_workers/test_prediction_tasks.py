"""prediction_tasks.py birim testleri."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.prediction_ml.infrastructure.prediction_tasks import run_prediction_task

pytestmark = pytest.mark.unit


def _make_redis_mock(exists=False, cached_payload=None):
    import json

    m = MagicMock()
    m.exists.return_value = exists
    m.get.return_value = json.dumps(cached_payload).encode() if cached_payload else None
    m.setex.return_value = True
    m.lpush.return_value = 1
    return m


def test_run_prediction_task_is_celery_task():
    assert run_prediction_task.name == "prediction.generate"


def test_run_prediction_task_returns_completed():
    """Normal akış: LLM cevap verir, status=completed."""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Yakıt tahmini: 45L/100km")

    with patch(
        "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client", return_value=mock_llm
    ):
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ):
            with patch("v2.modules.prediction_ml.infrastructure.prediction_tasks._persist", new=AsyncMock()):
                result = run_prediction_task.apply(
                    args=["Ankara-İstanbul için yakıt tahmini?"]
                ).get()

    assert result["status"] == "completed"
    assert "answer" in result
    assert "finished_at" in result


def test_run_prediction_task_idempotent():
    """Redis'te key zaten varsa llm.chat çağrılmaz, cache'den döner."""
    cached = {
        "status": "completed",
        "answer": "cached answer",
        "finished_at": "2026-01-01T00:00:00+00:00",
    }
    mock_redis = _make_redis_mock(exists=True, cached_payload=cached)
    mock_llm = AsyncMock()

    with patch(
        "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client", return_value=mock_llm
    ):
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
            return_value=mock_redis,
        ):
            result = run_prediction_task.apply(args=["any question"]).get()

    # get_llm_client() task başında çağrılır ama llm.chat çağrılmaz
    mock_llm.chat.assert_not_called()
    assert result["answer"] == "cached answer"


def test_run_prediction_task_with_context():
    """context parametresi sistem mesajı olarak eklenir."""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Yanıt")

    with patch(
        "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client", return_value=mock_llm
    ):
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ):
            with patch("v2.modules.prediction_ml.infrastructure.prediction_tasks._persist", new=AsyncMock()):
                result = run_prediction_task.apply(
                    args=["Soru?", "Sistem bağlamı"]
                ).get()

    call_kwargs = mock_llm.chat.call_args
    messages = call_kwargs[1].get("messages") or call_kwargs[0][0]
    assert any(m.role == "system" for m in messages)
    assert result["status"] == "completed"


def test_run_prediction_task_llm_error_propagates():
    """LLM her denemede exception → CELERY_EAGER'da exception propagate eder."""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(side_effect=Exception("Groq timeout"))

    with patch(
        "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client", return_value=mock_llm
    ):
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ):
            with patch("v2.modules.prediction_ml.infrastructure.prediction_tasks._persist", new=AsyncMock()):
                with pytest.raises(Exception, match="Groq timeout"):
                    run_prediction_task.apply(args=["soru"]).get(propagate=True)


def test_run_prediction_task_redis_error_ignored():
    """Redis bağlantı hatası → idempotency atlanır, task yine de çalışır."""
    mock_redis = MagicMock()
    mock_redis.exists.side_effect = Exception("Redis down")
    mock_redis.setex.side_effect = Exception("Redis down")
    mock_redis.lpush.side_effect = Exception("Redis down")

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Yanıt")

    with patch(
        "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client", return_value=mock_llm
    ):
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
            return_value=mock_redis,
        ):
            with patch("v2.modules.prediction_ml.infrastructure.prediction_tasks._persist", new=AsyncMock()):
                result = run_prediction_task.apply(args=["soru"]).get()

    assert result["status"] == "completed"


def test_run_prediction_task_no_context():
    """context=None → sadece user mesajı eklenir, system mesajı yok."""
    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="")

    with patch(
        "v2.modules.prediction_ml.infrastructure.prediction_tasks.get_llm_client", return_value=mock_llm
    ):
        with patch(
            "v2.modules.prediction_ml.infrastructure.prediction_tasks.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ):
            with patch("v2.modules.prediction_ml.infrastructure.prediction_tasks._persist", new=AsyncMock()):
                run_prediction_task.apply(args=[""]).get()

    call_kwargs = mock_llm.chat.call_args
    messages = call_kwargs[1].get("messages") or call_kwargs[0][0]
    assert not any(m.role == "system" for m in messages)
