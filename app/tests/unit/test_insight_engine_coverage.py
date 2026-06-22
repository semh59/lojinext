"""
Coverage tests for app/core/services/insight_engine.py
Targets: InsightEngine methods, Insight dataclass, InsightType enum,
         _to_alert_payload, _safe_await, get_uow, _UnitOfWorkContext.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine():
    from app.core.services.insight_engine import InsightEngine

    return InsightEngine()


def _make_insight(
    tip_value="uyari", hedef_tur="arac", hedef_id=1, mesaj="msg", seviye="high"
):
    from app.core.services.insight_engine import Insight, InsightType

    tip = InsightType(tip_value)
    return Insight(
        tip=tip, hedef_tur=hedef_tur, hedef_id=hedef_id, mesaj=mesaj, seviye=seviye
    )


# ---------------------------------------------------------------------------
# InsightType enum
# ---------------------------------------------------------------------------


def test_insight_type_values():
    from app.core.services.insight_engine import InsightType

    assert InsightType.UYARI.value == "uyari"
    assert InsightType.ONERI.value == "oneri"
    assert InsightType.BILGI.value == "bilgi"


# ---------------------------------------------------------------------------
# Insight dataclass
# ---------------------------------------------------------------------------


def test_insight_default_seviye():
    from app.core.services.insight_engine import Insight, InsightType

    i = Insight(tip=InsightType.BILGI, hedef_tur="filo", hedef_id=None, mesaj="Info")
    assert i.seviye == "medium"


def test_insight_custom_seviye():
    i = _make_insight(seviye="high")
    assert i.seviye == "high"


def test_insight_none_hedef_id():
    i = _make_insight(hedef_id=None)
    assert i.hedef_id is None


# ---------------------------------------------------------------------------
# _to_alert_payload
# ---------------------------------------------------------------------------


def test_to_alert_payload_uyari():
    from app.core.services.insight_engine import InsightEngine

    i = _make_insight(
        tip_value="uyari",
        hedef_tur="arac",
        hedef_id=5,
        mesaj="Tüketim yüksek",
        seviye="high",
    )
    payload = InsightEngine._to_alert_payload(i)
    assert payload["severity"] == "high"
    assert payload["kaynak_tur"] == "arac"
    assert payload["kaynak_id"] == 5
    assert "Tüketim yüksek" in payload["message"]
    assert "Uyari" in payload["title"]


def test_to_alert_payload_oneri():
    from app.core.services.insight_engine import InsightEngine

    i = _make_insight(
        tip_value="oneri",
        hedef_tur="sofor",
        hedef_id=10,
        mesaj="Öneri mesajı",
        seviye="medium",
    )
    payload = InsightEngine._to_alert_payload(i)
    assert "Oneri" in payload["title"]
    assert payload["kaynak_tur"] == "sofor"


def test_to_alert_payload_bilgi():
    from app.core.services.insight_engine import InsightEngine

    i = _make_insight(
        tip_value="bilgi",
        hedef_tur="filo",
        hedef_id=None,
        mesaj="Bilgi mesajı",
        seviye="low",
    )
    payload = InsightEngine._to_alert_payload(i)
    assert "Bilgi" in payload["title"]
    assert payload["kaynak_id"] is None


# ---------------------------------------------------------------------------
# _safe_await
# ---------------------------------------------------------------------------


async def test_safe_await_coroutine():
    from app.core.services.insight_engine import _safe_await

    async def coro():
        return 42

    result = await _safe_await(coro())
    assert result == 42


async def test_safe_await_plain_value():
    from app.core.services.insight_engine import _safe_await

    result = await _safe_await(99)
    assert result == 99


async def test_safe_await_none():
    from app.core.services.insight_engine import _safe_await

    result = await _safe_await(None)
    assert result is None


async def test_safe_await_list():
    from app.core.services.insight_engine import _safe_await

    result = await _safe_await([1, 2, 3])
    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# generate_fleet_insights
# ---------------------------------------------------------------------------


def _uow_with_dashboard(stats):
    """AUDIT-094: generate_fleet_insights artık get_uow() kullanır (session'sız
    get_analiz_repo değil). Dashboard stats sağlayan mock uow context döndürür."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.analiz_repo = MagicMock()
    mock_uow.analiz_repo.get_dashboard_stats = AsyncMock(return_value=stats)
    return mock_uow


async def test_generate_fleet_insights_high_avg():
    engine = _make_engine()
    mock_uow = _uow_with_dashboard({"filo_ortalama": 40.0})

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_fleet_insights()

    assert len(insights) == 1
    assert insights[0].seviye == "high"
    assert insights[0].hedef_tur == "filo"


async def test_generate_fleet_insights_normal_avg():
    engine = _make_engine()
    mock_uow = _uow_with_dashboard({"filo_ortalama": 34.0})

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_fleet_insights()

    assert insights == []


async def test_generate_fleet_insights_zero_avg():
    engine = _make_engine()
    mock_uow = _uow_with_dashboard({"filo_ortalama": 0})

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_fleet_insights()

    assert insights == []


async def test_generate_fleet_insights_exception():
    engine = _make_engine()
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(side_effect=RuntimeError("DB error"))
    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_fleet_insights()
    assert insights == []


# ---------------------------------------------------------------------------
# generate_vehicle_insights_bulk
# ---------------------------------------------------------------------------


def _make_mock_uow_ctx(rows):
    """Returns a mock UoW context manager that provides analiz_repo."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.analiz_repo = MagicMock()
    mock_uow.analiz_repo.get_all_vehicles_consumption_stats = AsyncMock(
        return_value=rows
    )
    return mock_uow


async def test_generate_vehicle_insights_over_target():
    engine = _make_engine()
    rows = [
        {"arac_id": 1, "plaka": "34ABC", "hedef_tuketim": 30.0, "ort_tuketim": 35.0},
    ]
    mock_uow = _make_mock_uow_ctx(rows)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_vehicle_insights_bulk()

    assert len(insights) == 1
    assert "34ABC" in insights[0].mesaj
    assert insights[0].seviye == "high"


async def test_generate_vehicle_insights_within_target():
    engine = _make_engine()
    rows = [
        {"arac_id": 2, "plaka": "06XYZ", "hedef_tuketim": 30.0, "ort_tuketim": 30.5},
    ]
    mock_uow = _make_mock_uow_ctx(rows)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_vehicle_insights_bulk()

    assert insights == []


async def test_generate_vehicle_insights_zero_hedef():
    engine = _make_engine()
    rows = [{"arac_id": 3, "plaka": "35YY", "hedef_tuketim": 0, "ort_tuketim": 40.0}]
    mock_uow = _make_mock_uow_ctx(rows)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_vehicle_insights_bulk()

    assert insights == []


async def test_generate_vehicle_insights_empty_rows():
    engine = _make_engine()
    mock_uow = _make_mock_uow_ctx([])

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_vehicle_insights_bulk()

    assert insights == []


async def test_generate_vehicle_insights_exception():
    engine = _make_engine()
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(side_effect=RuntimeError("DB crash"))
    mock_uow.__aexit__ = AsyncMock(return_value=None)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_vehicle_insights_bulk()

    assert insights == []


# ---------------------------------------------------------------------------
# generate_driver_insights_bulk
# ---------------------------------------------------------------------------


def _make_mock_uow_ctx_drivers(rows):
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.analiz_repo = MagicMock()
    mock_uow.analiz_repo.get_all_drivers_consumption_stats = AsyncMock(
        return_value=rows
    )
    return mock_uow


async def test_generate_driver_insights_low_score():
    engine = _make_engine()
    rows = [{"sofor_id": 5, "ad_soyad": "Mehmet Yılmaz", "performans_skoru": 40.0}]
    mock_uow = _make_mock_uow_ctx_drivers(rows)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_driver_insights_bulk()

    assert len(insights) == 1
    assert "Mehmet Yılmaz" in insights[0].mesaj
    assert insights[0].hedef_id == 5


async def test_generate_driver_insights_good_score():
    engine = _make_engine()
    rows = [{"sofor_id": 6, "ad_soyad": "Ali Can", "performans_skoru": 80.0}]
    mock_uow = _make_mock_uow_ctx_drivers(rows)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_driver_insights_bulk()

    assert insights == []


async def test_generate_driver_insights_zero_score():
    engine = _make_engine()
    rows = [{"sofor_id": 7, "ad_soyad": "Test", "performans_skoru": 0}]
    mock_uow = _make_mock_uow_ctx_drivers(rows)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_driver_insights_bulk()

    # score=0 is falsy → no insight generated
    assert insights == []


async def test_generate_driver_insights_no_method():
    """When analiz_repo lacks get_all_drivers_consumption_stats, returns []."""
    engine = _make_engine()
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    # analiz_repo without that method
    mock_uow.analiz_repo = MagicMock(spec=[])  # empty spec → no attributes

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_driver_insights_bulk()

    assert insights == []


async def test_generate_driver_insights_exception():
    engine = _make_engine()
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(side_effect=RuntimeError("crash"))
    mock_uow.__aexit__ = AsyncMock(return_value=None)

    with patch("app.core.services.insight_engine.get_uow", return_value=mock_uow):
        insights = await engine.generate_driver_insights_bulk()

    assert insights == []


# ---------------------------------------------------------------------------
# generate_all_and_save
# ---------------------------------------------------------------------------


async def test_generate_all_and_save_no_insights():
    engine = _make_engine()
    with (
        patch.object(engine, "generate_fleet_insights", new=AsyncMock(return_value=[])),
        patch.object(
            engine, "generate_vehicle_insights_bulk", new=AsyncMock(return_value=[])
        ),
        patch.object(
            engine, "generate_driver_insights_bulk", new=AsyncMock(return_value=[])
        ),
    ):
        count = await engine.generate_all_and_save()
    assert count == 0


def _uow_with_repo(mock_repo):
    """AUDIT-094: generate_all_and_save kaydetme yolu get_uow().analiz_repo kullanır."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.analiz_repo = mock_repo
    mock_uow.commit = AsyncMock()
    return mock_uow


async def test_generate_all_and_save_with_insights():
    engine = _make_engine()
    fleet = [_make_insight("uyari", "filo", None, "Fleet msg", "high")]
    vehicle = [_make_insight("uyari", "arac", 1, "Vehicle msg", "high")]
    driver = [_make_insight("uyari", "sofor", 5, "Driver msg", "medium")]

    mock_repo = MagicMock()
    mock_repo.bulk_create_alerts = AsyncMock(return_value=3)

    with (
        patch.object(
            engine, "generate_fleet_insights", new=AsyncMock(return_value=fleet)
        ),
        patch.object(
            engine,
            "generate_vehicle_insights_bulk",
            new=AsyncMock(return_value=vehicle),
        ),
        patch.object(
            engine, "generate_driver_insights_bulk", new=AsyncMock(return_value=driver)
        ),
        patch(
            "app.core.services.insight_engine.get_uow",
            return_value=_uow_with_repo(mock_repo),
        ),
    ):
        count = await engine.generate_all_and_save()
    assert count == 3


async def test_generate_all_and_save_partial_insights():
    engine = _make_engine()
    fleet = [_make_insight("bilgi", "filo", None, "Info", "low")]

    mock_repo = MagicMock()
    mock_repo.bulk_create_alerts = AsyncMock(return_value=1)

    with (
        patch.object(
            engine, "generate_fleet_insights", new=AsyncMock(return_value=fleet)
        ),
        patch.object(
            engine, "generate_vehicle_insights_bulk", new=AsyncMock(return_value=[])
        ),
        patch.object(
            engine, "generate_driver_insights_bulk", new=AsyncMock(return_value=[])
        ),
        patch(
            "app.core.services.insight_engine.get_uow",
            return_value=_uow_with_repo(mock_repo),
        ),
    ):
        count = await engine.generate_all_and_save()
    assert count == 1


# ---------------------------------------------------------------------------
# get_uow
# ---------------------------------------------------------------------------


def test_get_uow_returns_context_manager():
    from app.core.services.insight_engine import _UnitOfWorkContext, get_uow

    ctx = get_uow()
    assert isinstance(ctx, _UnitOfWorkContext)


def test_get_uow_is_different_each_call():
    from app.core.services.insight_engine import get_uow

    c1 = get_uow()
    c2 = get_uow()
    # Each call returns a new instance (not a singleton)
    assert c1 is not c2
