"""Additional coverage for coaching_tasks.py — _send_high_priority_to_telegram,
_run_evaluate_pending (rows present), weekly_coaching_digest task execution,
high-priority + telegram_id + COACHING_ENABLED path."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.tasks.coaching_tasks import (
    _run_digest,
    _run_evaluate_pending,
    _send_high_priority_to_telegram,
    weekly_coaching_digest,
)

pytestmark = pytest.mark.unit


# ─── _send_high_priority_to_telegram ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_telegram_no_token():
    """No bot token → returns False immediately."""
    with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
        mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = ""
        result = await _send_high_priority_to_telegram("123", "headline", "suggestion")
    assert result is False


@pytest.mark.asyncio
async def test_send_telegram_success():
    """Successful HTTP call → returns True."""

    with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
        mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "fake-token"

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch(
            "app.workers.tasks.coaching_tasks.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await _send_high_priority_to_telegram(
                "987654", "Test headline", "Use cruise control"
            )

    assert result is True
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args[1]["json"]
    assert call_kwargs["chat_id"] == "987654"
    assert "HTML" == call_kwargs["parse_mode"]


@pytest.mark.asyncio
async def test_send_telegram_http_error_returns_false():
    """HTTP error → returns False, does not raise."""
    import httpx

    with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
        mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "fake-token"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))

        with patch(
            "app.workers.tasks.coaching_tasks.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = await _send_high_priority_to_telegram("123", "Headline", None)

    assert result is False


@pytest.mark.asyncio
async def test_send_telegram_no_suggestion_omits_line():
    """top_suggestion=None → body does not contain suggestion line."""

    with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
        mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "fake-token"

        posted_json = {}

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        async def fake_post(url, json=None, **kwargs):
            posted_json.update(json or {})
            return mock_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with patch(
            "app.workers.tasks.coaching_tasks.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await _send_high_priority_to_telegram("321", "Only headline", None)

    assert "Öneri" not in posted_json.get("text", "")


@pytest.mark.asyncio
async def test_send_telegram_html_escapes_special_chars():
    """HTML special characters are escaped in the message body."""

    with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
        mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "fake-token"

        sent_texts = []

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        async def fake_post(url, json=None, **kwargs):
            sent_texts.append(json.get("text", ""))
            return mock_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with patch(
            "app.workers.tasks.coaching_tasks.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await _send_high_priority_to_telegram(
                "111", "<script>alert(1)</script>", "&suggestion"
            )

    assert "<script>" not in sent_texts[0]
    assert "&amp;" in sent_texts[0] or "&lt;" in sent_texts[0]


# ─── _run_digest — high priority + COACHING_ENABLED + telegram_id ─────────────


@pytest.mark.asyncio
async def test_run_digest_high_priority_sends_telegram():
    """high_priority + telegram_id + COACHING_ENABLED=True → sent=1."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 5, "telegram_id": "555"}]
    )

    mock_insight = MagicMock()
    mock_insight.priority = "high"
    mock_insight.headline = "Yüksek tüketim"
    mock_insight.insights = [MagicMock(suggestion="Hız düşür")]

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(return_value=mock_insight)

    with patch(
        "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
        return_value=mock_engine,
    ):
        with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
            with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
                mock_settings.COACHING_ENABLED = True
                mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "token"

                with patch(
                    "app.workers.tasks.coaching_tasks._send_high_priority_to_telegram",
                    new_callable=AsyncMock,
                    return_value=True,
                ) as mock_send:
                    result = await _run_digest()

    assert result["sent"] == 1
    assert result["high_priority"] == 1
    mock_send.assert_called_once_with("555", "Yüksek tüketim", "Hız düşür")


@pytest.mark.asyncio
async def test_run_digest_high_priority_coaching_disabled():
    """COACHING_ENABLED=False → Telegram not sent even with telegram_id."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 3, "telegram_id": "999"}]
    )

    mock_insight = MagicMock()
    mock_insight.priority = "high"
    mock_insight.headline = "Kötü davranış"
    mock_insight.insights = []

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(return_value=mock_insight)

    with patch(
        "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
        return_value=mock_engine,
    ):
        with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
            with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
                mock_settings.COACHING_ENABLED = False
                result = await _run_digest()

    assert result["sent"] == 0


@pytest.mark.asyncio
async def test_run_digest_high_priority_no_insights():
    """high priority with empty insights list → top suggestion is None, sent=0 if not enabled."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.sofor_repo.get_all = AsyncMock(
        return_value=[{"id": 7, "telegram_id": "777"}]
    )

    mock_insight = MagicMock()
    mock_insight.priority = "high"
    mock_insight.headline = "No insights"
    mock_insight.insights = []  # empty

    mock_engine = AsyncMock()
    mock_engine.generate_coaching = AsyncMock(return_value=mock_insight)

    with patch(
        "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
        return_value=mock_engine,
    ):
        with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
            with patch("app.workers.tasks.coaching_tasks.settings") as mock_settings:
                mock_settings.COACHING_ENABLED = True
                mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "token"

                with patch(
                    "app.workers.tasks.coaching_tasks._send_high_priority_to_telegram",
                    new_callable=AsyncMock,
                    return_value=True,
                ) as mock_send:
                    await _run_digest()

    # Called with None as top suggestion
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0]
    assert call_args[2] is None


# ─── _run_evaluate_pending — rows present ────────────────────────────────────


@pytest.mark.asyncio
async def test_run_evaluate_pending_evaluates_rows():
    """Rows found → score fetched, delta computed, evaluated_at updated."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    delivery = MagicMock()
    delivery.id = 10
    delivery.sofor_id = 42
    delivery.score_before = 80.0
    delivery.sent_at = cutoff - timedelta(days=1)

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.sofor_repo = MagicMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [delivery]
    mock_uow.session.execute = AsyncMock(return_value=mock_result)

    mock_svc = AsyncMock()
    mock_svc.get_score_breakdown = AsyncMock(return_value={"total": 88.0})

    with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
        with patch(
            "app.core.services.sofor_service.SoforService",
            return_value=mock_svc,
        ):
            result = await _run_evaluate_pending()

    assert result["evaluated"] == 1
    assert result["errors"] == 0


@pytest.mark.asyncio
async def test_run_evaluate_pending_score_before_zero():
    """score_before=0 → delta=0.0 (no division by zero)."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    delivery = MagicMock()
    delivery.id = 20
    delivery.sofor_id = 55
    delivery.score_before = 0.0
    delivery.sent_at = cutoff - timedelta(days=1)

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.sofor_repo = MagicMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [delivery]
    mock_uow.session.execute = AsyncMock(return_value=mock_result)

    mock_svc = AsyncMock()
    mock_svc.get_score_breakdown = AsyncMock(return_value={"total": 75.0})

    with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
        with patch(
            "app.core.services.sofor_service.SoforService",
            return_value=mock_svc,
        ):
            result = await _run_evaluate_pending()

    assert result["evaluated"] == 1


@pytest.mark.asyncio
async def test_run_evaluate_pending_error_counted():
    """Service exception per delivery → errors incremented, continues."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)

    delivery = MagicMock()
    delivery.id = 30
    delivery.sofor_id = 66
    delivery.score_before = 70.0
    delivery.sent_at = cutoff - timedelta(days=1)

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.commit = AsyncMock()
    mock_uow.sofor_repo = MagicMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [delivery]
    mock_uow.session.execute = AsyncMock(return_value=mock_result)

    mock_svc = AsyncMock()
    mock_svc.get_score_breakdown = AsyncMock(side_effect=Exception("DB error"))

    with patch("app.database.unit_of_work.UnitOfWork", return_value=mock_uow):
        with patch(
            "app.core.services.sofor_service.SoforService",
            return_value=mock_svc,
        ):
            result = await _run_evaluate_pending()

    assert result["errors"] == 1
    assert result["evaluated"] == 0


# ─── weekly_coaching_digest task smoke ───────────────────────────────────────


def test_weekly_coaching_digest_runs():
    """Task executes synchronously with mocked _run_digest."""
    with patch(
        "app.workers.tasks.coaching_tasks._run_digest",
        new_callable=AsyncMock,
        return_value={
            "processed": 0,
            "high_priority": 0,
            "sent": 0,
            "errors": 0,
            "total": 0,
            "timeout_partial": False,
        },
    ):
        result = weekly_coaching_digest()

    assert result["processed"] == 0


def test_evaluate_pending_deliveries_runs():
    """evaluate_pending_deliveries executes synchronously."""
    from app.workers.tasks.coaching_tasks import evaluate_pending_deliveries

    with patch(
        "app.workers.tasks.coaching_tasks._run_evaluate_pending",
        new_callable=AsyncMock,
        return_value={"evaluated": 0, "skipped": 0, "errors": 0},
    ):
        result = evaluate_pending_deliveries()

    assert result["errors"] == 0
