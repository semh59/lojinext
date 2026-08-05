"""prediction_tasks.py unit tests.

Moved with the service extraction (Task 5, 2026-08-04). Rewired against
the real current source: the LLM call is `cross_module_client.ai_chat`
now (a plain coroutine function called directly), not a
`get_llm_client().chat(...)` client object -- and messages are plain
dicts (`{"role": ..., "content": ...}`), not objects with a `.role`
attribute.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prediction_ml_service.infrastructure.prediction_tasks import run_prediction_task

pytestmark = pytest.mark.unit

TASKS_MODULE = "prediction_ml_service.infrastructure.prediction_tasks"


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
    """Normal flow: LLM answers, status=completed."""
    mock_ai_chat = AsyncMock(return_value="Yakit tahmini: 45L/100km")

    with (
        patch(f"{TASKS_MODULE}.ai_chat", mock_ai_chat),
        patch(
            f"{TASKS_MODULE}.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ),
        patch(f"{TASKS_MODULE}._persist", new=AsyncMock()),
    ):
        result = run_prediction_task.apply(
            args=["Ankara-Istanbul icin yakit tahmini?"]
        ).get()

    assert result["status"] == "completed"
    assert "answer" in result
    assert "finished_at" in result


def test_run_prediction_task_idempotent():
    """Key already exists in Redis -> ai_chat not called, returns cached."""
    cached = {
        "status": "completed",
        "answer": "cached answer",
        "finished_at": "2026-01-01T00:00:00+00:00",
    }
    mock_redis = _make_redis_mock(exists=True, cached_payload=cached)
    mock_ai_chat = AsyncMock()

    with (
        patch(f"{TASKS_MODULE}.ai_chat", mock_ai_chat),
        patch(f"{TASKS_MODULE}.redis.Redis.from_url", return_value=mock_redis),
    ):
        result = run_prediction_task.apply(args=["any question"]).get()

    mock_ai_chat.assert_not_called()
    assert result["answer"] == "cached answer"


def test_run_prediction_task_with_context():
    """context param is added as a system message."""
    mock_ai_chat = AsyncMock(return_value="Yanit")

    with (
        patch(f"{TASKS_MODULE}.ai_chat", mock_ai_chat),
        patch(
            f"{TASKS_MODULE}.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ),
        patch(f"{TASKS_MODULE}._persist", new=AsyncMock()),
    ):
        result = run_prediction_task.apply(args=["Soru?", "Sistem baglami"]).get()

    call_kwargs = mock_ai_chat.call_args.kwargs
    messages = call_kwargs["messages"]
    assert any(m["role"] == "system" for m in messages)
    assert result["status"] == "completed"


def test_run_prediction_task_llm_error_propagates():
    """LLM raises on every attempt -> under CELERY_EAGER, exception propagates."""
    mock_ai_chat = AsyncMock(side_effect=Exception("Groq timeout"))

    with (
        patch(f"{TASKS_MODULE}.ai_chat", mock_ai_chat),
        patch(
            f"{TASKS_MODULE}.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ),
        patch(f"{TASKS_MODULE}._persist", new=AsyncMock()),
    ):
        with pytest.raises(Exception, match="Groq timeout"):
            run_prediction_task.apply(args=["soru"]).get(propagate=True)


def test_run_prediction_task_redis_error_ignored():
    """Redis connection error -> idempotency check skipped, task still runs."""
    mock_redis = MagicMock()
    mock_redis.exists.side_effect = Exception("Redis down")
    mock_redis.setex.side_effect = Exception("Redis down")
    mock_redis.lpush.side_effect = Exception("Redis down")

    mock_ai_chat = AsyncMock(return_value="Yanit")

    with (
        patch(f"{TASKS_MODULE}.ai_chat", mock_ai_chat),
        patch(f"{TASKS_MODULE}.redis.Redis.from_url", return_value=mock_redis),
        patch(f"{TASKS_MODULE}._persist", new=AsyncMock()),
    ):
        result = run_prediction_task.apply(args=["soru"]).get()

    assert result["status"] == "completed"


def test_run_prediction_task_no_context():
    """context=None -> only the user message is added, no system message."""
    mock_ai_chat = AsyncMock(return_value="")

    with (
        patch(f"{TASKS_MODULE}.ai_chat", mock_ai_chat),
        patch(
            f"{TASKS_MODULE}.redis.Redis.from_url",
            return_value=_make_redis_mock(),
        ),
        patch(f"{TASKS_MODULE}._persist", new=AsyncMock()),
    ):
        run_prediction_task.apply(args=[""]).get()

    call_kwargs = mock_ai_chat.call_args.kwargs
    messages = call_kwargs["messages"]
    assert not any(m["role"] == "system" for m in messages)
