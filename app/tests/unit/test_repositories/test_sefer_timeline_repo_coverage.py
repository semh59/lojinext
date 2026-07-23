"""Coverage tests for v2/modules/trip/infrastructure/sefer_timeline_repo.py.

Tests all free-function helpers and get_sefer_timeline using a mock session
(no real DB required). ``AuditRepository`` was dissolved to module-level
free functions when this file moved from admin_platform to trip (table
ownership correction, dalga 15 — see the module's own docstring).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from v2.modules.trip.infrastructure import sefer_timeline_repo

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: build a mock SeferLog row
# ---------------------------------------------------------------------------


def _make_log(
    log_id=1,
    sefer_id=10,
    islem_tipi="UPDATE",
    eski_deger=None,
    yeni_deger=None,
    degistiren_id=None,
    created_at=None,
):
    log = MagicMock()
    log.id = log_id
    log.sefer_id = sefer_id
    log.islem_tipi = islem_tipi
    log.eski_deger = eski_deger
    log.yeni_deger = yeni_deger
    log.degistiren_id = degistiren_id
    log.created_at = created_at or datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    return log


def _make_uow(session):
    """A minimal stand-in for UnitOfWork exposing only `.session`."""
    uow = MagicMock()
    uow.session = session
    return uow


# ---------------------------------------------------------------------------
# _safe_parse_json
# ---------------------------------------------------------------------------


class TestSafeParseJson:
    def test_none_returns_empty_dict(self):
        assert sefer_timeline_repo._safe_parse_json(None) == {}

    def test_empty_string_returns_empty_dict(self):
        assert sefer_timeline_repo._safe_parse_json("") == {}

    def test_valid_json_dict(self):
        result = sefer_timeline_repo._safe_parse_json('{"durum": "Aktif", "km": 500}')
        assert result == {"durum": "Aktif", "km": 500}

    def test_json_list_returns_empty_dict(self):
        # JSON array is not a dict → returns {}
        result = sefer_timeline_repo._safe_parse_json("[1, 2, 3]")
        assert result == {}

    def test_invalid_json_returns_empty_dict(self):
        result = sefer_timeline_repo._safe_parse_json("{broken json")
        assert result == {}

    def test_json_scalar_returns_empty_dict(self):
        result = sefer_timeline_repo._safe_parse_json('"just a string"')
        assert result == {}


# ---------------------------------------------------------------------------
# _normalize_event_type
# ---------------------------------------------------------------------------


class TestNormalizeEventType:
    def test_insert_returns_create(self):
        result = sefer_timeline_repo._normalize_event_type("INSERT", [])
        assert result == "CREATE"

    def test_delete_returns_delete(self):
        result = sefer_timeline_repo._normalize_event_type("DELETE", [])
        assert result == "DELETE"

    def test_update_with_durum_change_returns_status_change(self):
        changes = [{"alan": "durum", "eski": "Aktif", "yeni": "Tamamlandi"}]
        result = sefer_timeline_repo._normalize_event_type("UPDATE", changes)
        assert result == "STATUS_CHANGE"

    def test_update_with_tahmini_tuketim_change_returns_prediction_refresh(self):
        changes = [{"alan": "tahmini_tuketim", "eski": None, "yeni": 130.5}]
        result = sefer_timeline_repo._normalize_event_type("UPDATE", changes)
        assert result == "PREDICTION_REFRESH"

    def test_update_with_tahmin_meta_change_returns_prediction_refresh(self):
        changes = [{"alan": "tahmin_meta", "eski": None, "yeni": {"model": "ensemble"}}]
        result = sefer_timeline_repo._normalize_event_type("UPDATE", changes)
        assert result == "PREDICTION_REFRESH"

    def test_update_with_tuketim_change_returns_reconciliation(self):
        changes = [{"alan": "tuketim", "eski": None, "yeni": 128.0}]
        result = sefer_timeline_repo._normalize_event_type("UPDATE", changes)
        assert result == "RECONCILIATION"

    def test_update_with_periyot_id_change_returns_reconciliation(self):
        changes = [{"alan": "periyot_id", "eski": None, "yeni": 5}]
        result = sefer_timeline_repo._normalize_event_type("UPDATE", changes)
        assert result == "RECONCILIATION"

    def test_generic_update_returns_update(self):
        changes = [{"alan": "mesafe_km", "eski": 400, "yeni": 450}]
        result = sefer_timeline_repo._normalize_event_type("UPDATE", changes)
        assert result == "UPDATE"

    def test_update_no_changes_returns_update(self):
        result = sefer_timeline_repo._normalize_event_type("UPDATE", [])
        assert result == "UPDATE"


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def test_create_summary(self):
        result = sefer_timeline_repo._build_summary("CREATE", {}, {})
        assert "olusturuldu" in result.lower()

    def test_delete_summary(self):
        result = sefer_timeline_repo._build_summary("DELETE", {}, {})
        assert "silindi" in result.lower()

    def test_status_change_summary(self):
        result = sefer_timeline_repo._build_summary(
            "STATUS_CHANGE",
            {"durum": "Aktif"},
            {"durum": "Tamamlandi"},
        )
        assert "Aktif" in result
        assert "Tamamlandi" in result

    def test_prediction_refresh_summary(self):
        result = sefer_timeline_repo._build_summary("PREDICTION_REFRESH", {}, {})
        assert "tahmin" in result.lower()

    def test_reconciliation_summary(self):
        result = sefer_timeline_repo._build_summary("RECONCILIATION", {}, {})
        assert "uzlastirma" in result.lower() or "guncellendi" in result.lower()

    def test_update_summary(self):
        result = sefer_timeline_repo._build_summary("UPDATE", {}, {})
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _extract_changes
# ---------------------------------------------------------------------------


class TestExtractChanges:
    def test_detects_value_change(self):
        old = {"durum": "Aktif", "km": 400}
        new = {"durum": "Tamamlandi", "km": 400}
        changes = sefer_timeline_repo._extract_changes(old, new)
        fields = {c["alan"] for c in changes}
        assert "durum" in fields
        assert "km" not in fields

    def test_ignores_updated_at_and_created_at(self):
        old = {"updated_at": "2024-01-01", "created_at": "2024-01-01", "km": 400}
        new = {"updated_at": "2024-01-02", "created_at": "2024-01-01", "km": 500}
        changes = sefer_timeline_repo._extract_changes(old, new)
        fields = {c["alan"] for c in changes}
        assert "updated_at" not in fields
        assert "created_at" not in fields
        assert "km" in fields

    def test_detects_new_key(self):
        old = {}
        new = {"tahmini_tuketim": 130.0}
        changes = sefer_timeline_repo._extract_changes(old, new)
        assert any(c["alan"] == "tahmini_tuketim" for c in changes)

    def test_no_changes_when_equal(self):
        data = {"km": 400, "durum": "Aktif"}
        changes = sefer_timeline_repo._extract_changes(data, data.copy())
        assert changes == []


# ---------------------------------------------------------------------------
# _extract_prediction_block
# ---------------------------------------------------------------------------


class TestExtractPredictionBlock:
    def test_returns_none_when_no_prediction_fields(self):
        result = sefer_timeline_repo._extract_prediction_block(
            {"km": 400}, {"km": 450}
        )
        assert result is None

    def test_returns_block_when_tahmini_tuketim_present(self):
        old = {"tahmini_tuketim": 120.0}
        new = {"tahmini_tuketim": 135.0}
        result = sefer_timeline_repo._extract_prediction_block(old, new)
        assert result is not None
        assert result["onceki_tahmini_tuketim"] == 120.0
        assert result["tahmini_tuketim"] == 135.0

    def test_returns_block_when_tahmin_meta_present(self):
        old = {}
        new = {"tahmin_meta": {"model": "ensemble"}}
        result = sefer_timeline_repo._extract_prediction_block(old, new)
        assert result is not None
        assert result["tahmin_meta"] == {"model": "ensemble"}


# ---------------------------------------------------------------------------
# get_sefer_timeline
# ---------------------------------------------------------------------------


class TestGetSeferTimeline:
    async def test_returns_empty_list_when_no_logs(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=999, uow=_make_uow(mock_session)
        )
        assert result == []

    async def test_insert_log_is_create_type(self):
        new_data = json.dumps({"durum": "Aktif", "mesafe_km": 450})
        log = _make_log(
            log_id=1,
            sefer_id=5,
            islem_tipi="INSERT",
            eski_deger=None,
            yeni_deger=new_data,
            degistiren_id=None,
        )

        mock_session = AsyncMock()

        # First execute: SeferLog query
        sefer_result = MagicMock()
        sefer_result.scalars.return_value.all.return_value = [log]

        # Second execute: Kullanici query (no user_ids → skipped)
        mock_session.execute = AsyncMock(return_value=sefer_result)

        timeline = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=5, uow=_make_uow(mock_session)
        )
        assert len(timeline) == 1
        assert timeline[0]["tip"] == "CREATE"
        assert timeline[0]["id"] == 1

    async def test_delete_log_is_delete_type(self):
        old_data = json.dumps({"durum": "Aktif"})
        log = _make_log(
            log_id=2,
            sefer_id=5,
            islem_tipi="DELETE",
            eski_deger=old_data,
            yeni_deger=None,
            degistiren_id=None,
        )

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [log]
        mock_session.execute = AsyncMock(return_value=result)

        timeline = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=5, uow=_make_uow(mock_session)
        )
        assert timeline[0]["tip"] == "DELETE"

    async def test_status_change_update_log(self):
        old_data = json.dumps({"durum": "Aktif", "mesafe_km": 400})
        new_data = json.dumps({"durum": "Tamamlandi", "mesafe_km": 400})
        log = _make_log(
            log_id=3,
            sefer_id=5,
            islem_tipi="UPDATE",
            eski_deger=old_data,
            yeni_deger=new_data,
            degistiren_id=None,
        )

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [log]
        mock_session.execute = AsyncMock(return_value=result)

        timeline = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=5, uow=_make_uow(mock_session)
        )
        assert timeline[0]["tip"] == "STATUS_CHANGE"
        assert "Tamamlandi" in timeline[0]["ozet"]

    async def test_user_map_populated_from_degistiren_id(self):
        old_data = json.dumps({"durum": "Aktif"})
        new_data = json.dumps({"durum": "Tamamlandi"})
        log = _make_log(
            log_id=4,
            sefer_id=5,
            islem_tipi="UPDATE",
            eski_deger=old_data,
            yeni_deger=new_data,
            degistiren_id=7,
        )

        mock_session = AsyncMock()

        # Build user mock
        mock_user = MagicMock()
        mock_user.id = 7
        mock_user.ad_soyad = "Ahmet Yılmaz"
        mock_user.email = "ahmet@example.com"

        sefer_result = MagicMock()
        sefer_result.scalars.return_value.all.return_value = [log]

        user_result = MagicMock()
        user_result.scalars.return_value.all.return_value = [mock_user]

        mock_session.execute = AsyncMock(side_effect=[sefer_result, user_result])

        timeline = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=5, uow=_make_uow(mock_session)
        )
        assert timeline[0]["kullanici"] == "Ahmet Yılmaz"

    async def test_prediction_refresh_has_prediction_block(self):
        old_data = json.dumps({"tahmini_tuketim": 120.0})
        new_data = json.dumps({"tahmini_tuketim": 135.0})
        log = _make_log(
            log_id=5,
            sefer_id=5,
            islem_tipi="UPDATE",
            eski_deger=old_data,
            yeni_deger=new_data,
            degistiren_id=None,
        )

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [log]
        mock_session.execute = AsyncMock(return_value=result)

        timeline = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=5, uow=_make_uow(mock_session)
        )
        assert timeline[0]["tip"] == "PREDICTION_REFRESH"
        assert timeline[0]["prediction"] is not None
        assert timeline[0]["prediction"]["tahmini_tuketim"] == 135.0

    async def test_technical_details_populated(self):
        old_data = json.dumps({"mesafe_km": 400})
        new_data = json.dumps({"mesafe_km": 450})
        log = _make_log(
            log_id=6,
            sefer_id=5,
            islem_tipi="UPDATE",
            eski_deger=old_data,
            yeni_deger=new_data,
            degistiren_id=None,
        )

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [log]
        mock_session.execute = AsyncMock(return_value=result)

        timeline = await sefer_timeline_repo.get_sefer_timeline(
            sefer_id=5, uow=_make_uow(mock_session)
        )
        td = timeline[0]["technical_details"]
        assert td["islem_tipi"] == "UPDATE"
        assert td["degisen_alan_sayisi"] == 1
