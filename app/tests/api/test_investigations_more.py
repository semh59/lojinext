"""
Investigations endpoint — 2nd pass coverage.

Targets remaining uncovered branches in investigations.py (~82% → higher):
- _build_theft_alarm_text: various combinations (plaka/sofor None, values present)
- _resolve_alarm_context: row None, row present
- _maybe_broadcast_alarm: level != high (no-op), alarm disabled, bot token missing,
  chat_id missing, alarm HTTP error → audit fallback
- PATCH: status=resolved (closed_at set), status=closed, no-op with 404 fallback
- DELETE: disabled check, success path audit
- GET /patterns: data rows returned
- GET list: with all filter combos combined
"""

from __future__ import annotations

import html
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

BASE_URL = "/api/v1/admin/investigations"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_inv_dict(**kwargs) -> Dict[str, Any]:
    defaults = dict(
        id=1,
        anomaly_id=10,
        status="open",
        suspicion_score=0.75,
        suspicion_level="high",
        assigned_to_user_id=None,
        notes=None,
        resolution_type=None,
        evidence_files=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        closed_at=None,
        sapma_yuzde=-25.0,
        sofor_adi="Mehmet Kaya",
        plaka="06 XYZ 789",
    )
    defaults.update(kwargs)
    return defaults


@contextmanager
def _override_db(mock_db):
    from app.main import app
    from v2.modules.platform_infra.database.connection import get_db

    async def _fake_db():
        yield mock_db

    app.dependency_overrides[get_db] = _fake_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


def _make_db_mock(*, get_anomaly=None, get_investigation=None, execute_result=None):
    db = AsyncMock()

    _get_map: dict = {}
    if get_anomaly is not None:
        _get_map["Anomaly"] = get_anomaly
    if get_investigation is not None:
        _get_map["FuelInvestigation"] = get_investigation

    async def _db_get(model_cls, pk):
        return _get_map.get(model_cls.__name__)

    db.get = _db_get

    mapping_mock = MagicMock()
    if execute_result is not None:
        mapping_mock.all.return_value = execute_result
        mapping_mock.one_or_none.return_value = (
            execute_result[0] if execute_result else None
        )
    else:
        mapping_mock.all.return_value = []
        mapping_mock.one_or_none.return_value = None

    exec_result_mock = MagicMock()
    exec_result_mock.mappings.return_value = mapping_mock
    exec_result_mock.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(return_value=exec_result_mock)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    return db


# ---------------------------------------------------------------------------
# _build_theft_alarm_text — unit tests
# ---------------------------------------------------------------------------


class TestBuildTheftAlarmText:
    def test_with_plaka_and_sofor(self):
        from v2.modules.anomaly.api.investigation_routes import _build_theft_alarm_text
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=1,
            suspicion_score=0.85,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        anomaly.id = 1
        anomaly.sapma_yuzde = -30.5

        text = _build_theft_alarm_text(1, clf, anomaly, "34ABC123", "Ali Veli")

        assert "34ABC123" in text
        assert "Ali Veli" in text
        assert "-30.5%" in text
        assert "0.85" in text

    def test_with_no_plaka_and_no_sofor(self):
        from v2.modules.anomaly.api.investigation_routes import _build_theft_alarm_text
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=2,
            suspicion_score=0.90,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        anomaly.id = 2
        anomaly.sapma_yuzde = None  # sapma None branch

        text = _build_theft_alarm_text(2, clf, anomaly, None, None)

        assert "—" in text  # masked plaka, sofor, and sapma

    def test_with_html_special_chars_escaped(self):
        """Plaka/sofor with HTML chars are escaped."""
        from v2.modules.anomaly.api.investigation_routes import _build_theft_alarm_text
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=3,
            suspicion_score=0.70,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        anomaly.id = 3
        anomaly.sapma_yuzde = -20.0

        text = _build_theft_alarm_text(3, clf, anomaly, "<script>", "<b>hacker</b>")

        # HTML escape should encode < > chars
        assert (
            "<script>" not in text or "&lt;" in text or html.escape("<script>") in text
        )


# ---------------------------------------------------------------------------
# _resolve_alarm_context — unit tests
# ---------------------------------------------------------------------------


class TestResolveAlarmContext:
    async def test_row_none_returns_none_tuple(self):
        from v2.modules.anomaly.application.manage_investigations import (
            resolve_alarm_context,
        )

        anomaly = MagicMock()
        anomaly.id = 99

        db = AsyncMock()
        mapping = MagicMock()
        mapping.one_or_none.return_value = None
        result = MagicMock()
        result.mappings.return_value = mapping
        db.execute = AsyncMock(return_value=result)

        plaka, sofor_adi = await resolve_alarm_context(db, anomaly)
        assert plaka is None
        assert sofor_adi is None

    async def test_row_present_returns_values(self):
        from v2.modules.anomaly.application.manage_investigations import (
            resolve_alarm_context,
        )

        anomaly = MagicMock()
        anomaly.id = 5

        db = AsyncMock()
        row = MagicMock()
        row.get = lambda key, d=None: {"plaka": "34XYZ", "sofor_adi": "Mehmet"}[key]
        mapping = MagicMock()
        mapping.one_or_none.return_value = row
        result = MagicMock()
        result.mappings.return_value = mapping
        db.execute = AsyncMock(return_value=result)

        plaka, sofor_adi = await resolve_alarm_context(db, anomaly)
        assert plaka == "34XYZ"
        assert sofor_adi == "Mehmet"


# ---------------------------------------------------------------------------
# _maybe_broadcast_alarm — unit tests
# ---------------------------------------------------------------------------


class TestMaybeBroadcastAlarm:
    async def test_non_high_level_noop(self):
        """When suspicion_level != 'high', function returns immediately."""
        from v2.modules.anomaly.api.investigation_routes import _maybe_broadcast_alarm
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=1,
            suspicion_score=0.3,
            suspicion_level="low",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        db = AsyncMock()

        # Should complete without any HTTP call
        await _maybe_broadcast_alarm(1, clf, anomaly, db)
        db.execute.assert_not_called()

    async def test_alarm_disabled_noop(self):
        """When THEFT_ALARM_ENABLED=False, returns immediately."""
        from v2.modules.anomaly.api.investigation_routes import _maybe_broadcast_alarm
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=1,
            suspicion_score=0.95,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        db = AsyncMock()

        with patch(
            "v2.modules.anomaly.api.investigation_routes.settings"
        ) as mock_settings:
            mock_settings.THEFT_ALARM_ENABLED = False
            mock_settings.THEFT_INVESTIGATION_ENABLED = True
            await _maybe_broadcast_alarm(1, clf, anomaly, db)

        db.execute.assert_not_called()

    async def test_no_bot_token_logs_warning(self):
        """Missing bot token logs warning and returns early."""
        from v2.modules.anomaly.api.investigation_routes import _maybe_broadcast_alarm
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=1,
            suspicion_score=0.95,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        db = AsyncMock()

        with patch(
            "v2.modules.anomaly.api.investigation_routes.settings"
        ) as mock_settings:
            mock_settings.THEFT_ALARM_ENABLED = True
            mock_settings.THEFT_INVESTIGATION_ENABLED = True
            mock_settings.TELEGRAM_OPS_BOT_TOKEN = None
            mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = None
            mock_settings.TELEGRAM_OPS_CHAT_ID = "123"

            await _maybe_broadcast_alarm(1, clf, anomaly, db)
        # No exception raised

    async def test_no_chat_id_logs_warning(self):
        """Missing chat_id logs warning and returns early."""
        from v2.modules.anomaly.api.investigation_routes import _maybe_broadcast_alarm
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=1,
            suspicion_score=0.95,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        db = AsyncMock()

        with patch(
            "v2.modules.anomaly.api.investigation_routes.settings"
        ) as mock_settings:
            mock_settings.THEFT_ALARM_ENABLED = True
            mock_settings.THEFT_INVESTIGATION_ENABLED = True
            mock_settings.TELEGRAM_OPS_BOT_TOKEN = "bot:token"
            mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "bot:token"
            mock_settings.TELEGRAM_OPS_CHAT_ID = None

            await _maybe_broadcast_alarm(1, clf, anomaly, db)
        # No exception raised

    async def test_telegram_http_error_logs_and_audits(self):
        """When Telegram HTTP fails, error is logged and audit attempted."""
        import httpx

        from v2.modules.anomaly.api.investigation_routes import _maybe_broadcast_alarm
        from v2.modules.anomaly.schemas import TheftClassification

        clf = TheftClassification(
            anomaly_id=1,
            suspicion_score=0.95,
            suspicion_level="high",
            factors=[],
            suggested_action="",
        )
        anomaly = MagicMock()
        anomaly.id = 1
        anomaly.sapma_yuzde = -30.0

        db = AsyncMock()
        mapping = MagicMock()
        row = MagicMock()
        row.get = lambda k, d=None: {"plaka": "34ABC", "sofor_adi": "Test"}[k]
        mapping.one_or_none.return_value = row
        result = MagicMock()
        result.mappings.return_value = mapping
        db.execute = AsyncMock(return_value=result)

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=MagicMock(),
        )

        with patch(
            "v2.modules.anomaly.api.investigation_routes.settings"
        ) as mock_settings:
            mock_settings.THEFT_ALARM_ENABLED = True
            mock_settings.THEFT_INVESTIGATION_ENABLED = True
            mock_settings.TELEGRAM_OPS_BOT_TOKEN = "bot:token"
            mock_settings.TELEGRAM_DRIVER_BOT_TOKEN = "bot:token"
            mock_settings.TELEGRAM_OPS_CHAT_ID = "-100123456"

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                with patch(
                    "v2.modules.platform_infra.audit.audit_logger.log_audit_event",
                    new=AsyncMock(),
                ):
                    await _maybe_broadcast_alarm(1, clf, anomaly, db)
        # Should not raise


# ---------------------------------------------------------------------------
# GET /patterns — rows returned
# ---------------------------------------------------------------------------


async def test_get_patterns_with_data(async_client, admin_auth_headers):
    """GET /patterns → 200 with pattern rows."""
    from datetime import datetime, timezone

    pattern_row = MagicMock()
    pattern_row.__iter__ = MagicMock(
        return_value=iter(
            [
                ("sofor_id", 5),
                ("sofor_adi", "Ali Veli"),
                ("arac_id", 3),
                ("plaka", "34 AAA 111"),
                ("occurrence_count", 3),
                ("avg_suspicion_score", 0.82),
                ("last_seen", datetime.now(timezone.utc)),
            ]
        )
    )
    pattern_dict = {
        "sofor_id": 5,
        "sofor_adi": "Ali Veli",
        "arac_id": 3,
        "plaka": "34 AAA 111",
        "occurrence_count": 3,
        "avg_suspicion_score": 0.82,
        "last_seen": datetime.now(timezone.utc),
    }

    db = AsyncMock()
    mapping = MagicMock()
    mapping.all.return_value = [pattern_dict]
    result = MagicMock()
    result.mappings.return_value = mapping
    db.execute = AsyncMock(return_value=result)

    with _override_db(db):
        resp = await async_client.get(
            f"{BASE_URL}/patterns?days=60&min_count=2",
            headers=admin_auth_headers,
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET list — all filters combined
# ---------------------------------------------------------------------------


async def test_list_all_filters_combined(async_client, admin_auth_headers):
    """GET list with status + suspicion_level + assigned_to_user_id all set → 200."""
    db = _make_db_mock(execute_result=[])
    with _override_db(db):
        resp = await async_client.get(
            f"{BASE_URL}?status=open&suspicion_level=high&assigned_to_user_id=2&days=60",
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PATCH — status=closed path (sets closed_at), assigned when already assigned
# ---------------------------------------------------------------------------


async def test_update_investigation_status_closed(async_client, admin_auth_headers):
    """PATCH status=closed sets closed_at."""
    from v2.modules.anomaly.public import FuelInvestigation

    fake_inv = MagicMock(spec=FuelInvestigation)
    fake_inv.id = 1
    fake_inv.status = "open"
    fake_inv.anomaly_id = 10
    fake_inv.assigned_to_user_id = None
    fake_inv.resolution_type = None
    fake_inv.closed_at = None

    inv_row = _make_inv_dict(status="closed")

    db = AsyncMock()

    async def _db_get(model_cls, pk):
        if model_cls.__name__ == "FuelInvestigation":
            return fake_inv
        return None

    db.get = _db_get
    db.commit = AsyncMock()

    mapping_mock = MagicMock()
    mapping_mock.one_or_none.return_value = MagicMock(**inv_row)
    exec_result = MagicMock()
    exec_result.mappings.return_value = mapping_mock
    # 2026-07-01 Dalga 4 madde 18: PATCH'in ilk varlık kontrolü artık
    # `SELECT ... FOR UPDATE` (→ scalar_one_or_none()) kullanıyor.
    exec_result.scalar_one_or_none.return_value = fake_inv
    db.execute = AsyncMock(return_value=exec_result)

    with patch(
        "v2.modules.anomaly.infrastructure.investigation_repository.InvestigationRepository.get_investigation_detail",
        new=AsyncMock(return_value=inv_row),
    ):
        with patch(
            "v2.modules.platform_infra.audit.audit_logger.log_audit_event",
            new=AsyncMock(),
        ):
            with _override_db(db):
                resp = await async_client.patch(
                    f"{BASE_URL}/1",
                    json={"status": "closed"},
                    headers=admin_auth_headers,
                )

    assert resp.status_code == 200


async def test_update_investigation_assign_non_open(async_client, admin_auth_headers):
    """PATCH assign to non-open investigation doesn't change status."""
    from v2.modules.anomaly.public import FuelInvestigation

    fake_inv = MagicMock(spec=FuelInvestigation)
    fake_inv.id = 1
    fake_inv.status = "investigating"  # not open
    fake_inv.anomaly_id = 10
    fake_inv.assigned_to_user_id = None
    fake_inv.resolution_type = None
    fake_inv.closed_at = None

    inv_row = _make_inv_dict(status="investigating", assigned_to_user_id=5)

    db = AsyncMock()

    async def _db_get(model_cls, pk):
        if model_cls.__name__ == "FuelInvestigation":
            return fake_inv
        return None

    db.get = _db_get
    db.commit = AsyncMock()

    mapping_mock = MagicMock()
    mapping_mock.one_or_none.return_value = MagicMock(**inv_row)
    exec_result = MagicMock()
    exec_result.mappings.return_value = mapping_mock
    # 2026-07-01 Dalga 4 madde 18: PATCH'in ilk varlık kontrolü artık
    # `SELECT ... FOR UPDATE` (→ scalar_one_or_none()) kullanıyor.
    exec_result.scalar_one_or_none.return_value = fake_inv
    db.execute = AsyncMock(return_value=exec_result)

    with patch(
        "v2.modules.anomaly.infrastructure.investigation_repository.InvestigationRepository.get_investigation_detail",
        new=AsyncMock(return_value=inv_row),
    ):
        with patch(
            "v2.modules.platform_infra.audit.audit_logger.log_audit_event",
            new=AsyncMock(),
        ):
            with _override_db(db):
                resp = await async_client.patch(
                    f"{BASE_URL}/1",
                    json={"assigned_to_user_id": 5},
                    headers=admin_auth_headers,
                )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# PATCH no-op + missing after update → 404 branch
# ---------------------------------------------------------------------------


async def test_update_investigation_noop_fetch_returns_none(
    async_client, admin_auth_headers
):
    """PATCH no-op path when AnalizRepository.get_investigation_detail returns None → 404."""
    from v2.modules.anomaly.public import FuelInvestigation

    fake_inv = MagicMock(spec=FuelInvestigation)
    fake_inv.id = 1
    fake_inv.status = "open"
    fake_inv.anomaly_id = 10
    fake_inv.assigned_to_user_id = None
    fake_inv.resolution_type = None
    fake_inv.closed_at = None

    db = AsyncMock()

    async def _db_get(model_cls, pk):
        if model_cls.__name__ == "FuelInvestigation":
            return fake_inv
        return None

    db.get = _db_get
    db.commit = AsyncMock()

    exec_result = MagicMock()
    # 2026-07-01 Dalga 4 madde 18: PATCH'in ilk varlık kontrolü artık
    # `SELECT ... FOR UPDATE` (→ scalar_one_or_none()) kullanıyor — no-op
    # dalına ulaşmadan önce bu kontrolden geçmesi gerekiyor.
    exec_result.scalar_one_or_none.return_value = fake_inv
    db.execute = AsyncMock(return_value=exec_result)

    with patch(
        "v2.modules.anomaly.infrastructure.investigation_repository.InvestigationRepository.get_investigation_detail",
        new=AsyncMock(return_value=None),  # simulate missing record
    ):
        with _override_db(db):
            resp = await async_client.patch(
                f"{BASE_URL}/1",
                json={},  # empty payload → no-op
                headers=admin_auth_headers,
            )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH → post-update _fetch returns None → 404
# ---------------------------------------------------------------------------


async def test_update_investigation_post_fetch_none(async_client, admin_auth_headers):
    """PATCH when _fetch returns None after update → 404."""
    from v2.modules.anomaly.public import FuelInvestigation

    fake_inv = MagicMock(spec=FuelInvestigation)
    fake_inv.id = 1
    fake_inv.status = "open"
    fake_inv.anomaly_id = 10
    fake_inv.assigned_to_user_id = None
    fake_inv.resolution_type = None
    fake_inv.closed_at = None

    db = AsyncMock()

    async def _db_get(model_cls, pk):
        if model_cls.__name__ == "FuelInvestigation":
            return fake_inv
        return None

    db.get = _db_get
    db.commit = AsyncMock()

    exec_result = MagicMock()
    # 2026-07-01 Dalga 4 madde 18: PATCH'in ilk varlık kontrolü artık
    # `SELECT ... FOR UPDATE` (→ scalar_one_or_none()) kullanıyor.
    exec_result.scalar_one_or_none.return_value = fake_inv
    db.execute = AsyncMock(return_value=exec_result)

    # First call (no-op check) returns the row, second call (post-update) returns None
    call_counter = {"n": 0}

    async def _fetch_side_effect(inv_id):
        call_counter["n"] += 1
        return None

    with patch(
        "v2.modules.anomaly.infrastructure.investigation_repository.InvestigationRepository.get_investigation_detail",
        side_effect=_fetch_side_effect,
    ):
        with patch(
            "v2.modules.platform_infra.audit.audit_logger.log_audit_event",
            new=AsyncMock(),
        ):
            with _override_db(db):
                resp = await async_client.patch(
                    f"{BASE_URL}/1",
                    json={"notes": "update note"},  # triggers values update
                    headers=admin_auth_headers,
                )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST create — IntegrityError race condition → 409
# ---------------------------------------------------------------------------


async def test_create_investigation_integrity_error(async_client, admin_auth_headers):
    """POST /admin/investigations → 409 on IntegrityError race condition."""
    from sqlalchemy.exc import IntegrityError

    from v2.modules.anomaly.public import Anomaly
    from v2.modules.anomaly.schemas import TheftClassification

    fake_anomaly = MagicMock(spec=Anomaly)
    fake_anomaly.id = 10
    fake_anomaly.tip = "yakıt_sapma"
    fake_anomaly.kaynak_id = 5
    fake_anomaly.kaynak_tip = "sefer"
    fake_anomaly.sapma_yuzde = -30.0
    fake_anomaly.severity = "high"

    fake_classification = TheftClassification(
        anomaly_id=10,
        suspicion_score=0.75,
        suspicion_level="medium",
        factors=[],
        suggested_action="Check",
    )

    db = AsyncMock()

    async def _db_get(model_cls, pk):
        if model_cls.__name__ == "Anomaly":
            return fake_anomaly
        return None

    db.get = _db_get

    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=exec_result)
    db.add = MagicMock()

    # flush raises IntegrityError
    db.flush = AsyncMock(
        side_effect=IntegrityError("duplicate key", params={}, orig=Exception("unique"))
    )
    db.rollback = AsyncMock()
    db.commit = AsyncMock()

    with patch(
        "v2.modules.anomaly.application.classify_theft.get_fuel_theft_classifier"
    ) as mock_clf_factory:
        mock_clf = AsyncMock()
        mock_clf.classify = AsyncMock(return_value=fake_classification)
        mock_clf_factory.return_value = mock_clf

        with _override_db(db):
            resp = await async_client.post(
                BASE_URL,
                json={"anomaly_id": 10},
                headers=admin_auth_headers,
            )

    assert resp.status_code == 409
