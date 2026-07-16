"""
Coverage tests for v2/modules/analytics_executive/application/generate_insights.py

dalga 11: eski InsightEngine sınıfı kaldırıldı (B.1, constructor state
taşımıyordu) — free function'lara bölündü, testler class-mock'tan
free-function-mock'a çevrildi.

Targets: generate_* free functions, Insight dataclass, InsightType enum,
         _to_alert_payload, _safe_await, get_uow, _UnitOfWorkContext.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.database.models import Anomaly
from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

pytestmark = pytest.mark.integration
# ---------------------------------------------------------------------------
# Real-DB seed helper: generate_*_insights run a real UnitOfWork (get_uow →
# UnitOfWork → conftest-monkeypatched test session) whose analiz_repo aggregates
# real seferler. Seed a trip with a given consumption so the aggregate hits a
# known value.
# ---------------------------------------------------------------------------


async def _seed_trip(db_session, *, tuketim, plaka="34 ABC 123", hedef_tuketim=25.0):
    arac = await seed_arac(db_session, plaka=plaka, hedef_tuketim=hedef_tuketim)
    sofor = await seed_sofor(db_session, ad_soyad=f"Sofor {plaka}")
    await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id, tuketim=tuketim)
    await db_session.commit()
    return arac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_insight(
    tip_value="uyari", hedef_tur="arac", hedef_id=1, mesaj="msg", seviye="high"
):
    from v2.modules.analytics_executive.application.generate_insights import (
        Insight,
        InsightType,
    )

    tip = InsightType(tip_value)
    return Insight(
        tip=tip, hedef_tur=hedef_tur, hedef_id=hedef_id, mesaj=mesaj, seviye=seviye
    )


# ---------------------------------------------------------------------------
# InsightType enum
# ---------------------------------------------------------------------------


def test_insight_type_values():
    from v2.modules.analytics_executive.application.generate_insights import (
        InsightType,
    )

    assert InsightType.UYARI.value == "uyari"
    assert InsightType.ONERI.value == "oneri"
    assert InsightType.BILGI.value == "bilgi"


# ---------------------------------------------------------------------------
# Insight dataclass
# ---------------------------------------------------------------------------


def test_insight_default_seviye():
    from v2.modules.analytics_executive.application.generate_insights import (
        Insight,
        InsightType,
    )

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
    from v2.modules.analytics_executive.application.generate_insights import (
        _to_alert_payload,
    )

    i = _make_insight(
        tip_value="uyari",
        hedef_tur="arac",
        hedef_id=5,
        mesaj="Tüketim yüksek",
        seviye="high",
    )
    payload = _to_alert_payload(i)
    assert payload["severity"] == "high"
    assert payload["kaynak_tur"] == "arac"
    assert payload["kaynak_id"] == 5
    assert "Tüketim yüksek" in payload["message"]
    assert "Uyari" in payload["title"]


def test_to_alert_payload_oneri():
    from v2.modules.analytics_executive.application.generate_insights import (
        _to_alert_payload,
    )

    i = _make_insight(
        tip_value="oneri",
        hedef_tur="sofor",
        hedef_id=10,
        mesaj="Öneri mesajı",
        seviye="medium",
    )
    payload = _to_alert_payload(i)
    assert "Oneri" in payload["title"]
    assert payload["kaynak_tur"] == "sofor"


def test_to_alert_payload_bilgi():
    from v2.modules.analytics_executive.application.generate_insights import (
        _to_alert_payload,
    )

    i = _make_insight(
        tip_value="bilgi",
        hedef_tur="filo",
        hedef_id=None,
        mesaj="Bilgi mesajı",
        seviye="low",
    )
    payload = _to_alert_payload(i)
    assert "Bilgi" in payload["title"]
    assert payload["kaynak_id"] is None


# ---------------------------------------------------------------------------
# _safe_await
# ---------------------------------------------------------------------------


async def test_safe_await_coroutine():
    from v2.modules.analytics_executive.application.generate_insights import (
        _safe_await,
    )

    async def coro():
        return 42

    result = await _safe_await(coro())
    assert result == 42


async def test_safe_await_plain_value():
    from v2.modules.analytics_executive.application.generate_insights import (
        _safe_await,
    )

    result = await _safe_await(99)
    assert result == 99


async def test_safe_await_none():
    from v2.modules.analytics_executive.application.generate_insights import (
        _safe_await,
    )

    result = await _safe_await(None)
    assert result is None


async def test_safe_await_list():
    from v2.modules.analytics_executive.application.generate_insights import (
        _safe_await,
    )

    result = await _safe_await([1, 2, 3])
    assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# generate_fleet_insights
# ---------------------------------------------------------------------------


async def test_generate_fleet_insights_high_avg(db_session):
    """Real filo_ortalama = AVG(seferler.tuketim) > 38 → one high 'filo' insight."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_fleet_insights,
    )

    await _seed_trip(db_session, tuketim=40.0)
    insights = await generate_fleet_insights()
    assert len(insights) == 1
    assert insights[0].seviye == "high"
    assert insights[0].hedef_tur == "filo"


async def test_generate_fleet_insights_normal_avg(db_session):
    """Real avg 34 (≤ 38) → no insight."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_fleet_insights,
    )

    await _seed_trip(db_session, tuketim=34.0)
    insights = await generate_fleet_insights()
    assert insights == []


async def test_generate_fleet_insights_low_avg_empty_db(db_session):
    """No trips → COALESCE to DEFAULT_FILO_ORTALAMA (32) ≤ 38 → no insight."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_fleet_insights,
    )

    insights = await generate_fleet_insights()
    assert insights == []


async def test_generate_fleet_insights_exception():
    """The DB-error guard returns [] (defensive branch; forced via get_uow error)."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_fleet_insights,
    )

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(side_effect=RuntimeError("DB error"))
    with patch(
        "v2.modules.analytics_executive.application.generate_insights.get_uow",
        return_value=mock_uow,
    ):
        insights = await generate_fleet_insights()
    assert insights == []


# ---------------------------------------------------------------------------
# generate_vehicle_insights_bulk
# ---------------------------------------------------------------------------


async def test_generate_vehicle_insights_over_target(db_session):
    """Real ort_tuketim (35) > hedef*1.10 (33) → one high insight naming the plate."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_vehicle_insights_bulk,
    )

    await _seed_trip(db_session, tuketim=35.0, plaka="34 ABC 123", hedef_tuketim=30.0)
    insights = await generate_vehicle_insights_bulk()
    assert len(insights) == 1
    assert "34 ABC 123" in insights[0].mesaj
    assert insights[0].seviye == "high"


async def test_generate_vehicle_insights_within_target(db_session):
    """Real ort 30.5 ≤ hedef*1.10 (33) → no insight."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_vehicle_insights_bulk,
    )

    await _seed_trip(db_session, tuketim=30.5, plaka="06 XYZ 789", hedef_tuketim=30.0)
    insights = await generate_vehicle_insights_bulk()
    assert insights == []


async def test_generate_vehicle_insights_zero_hedef(db_session):
    """hedef_tuketim ≤ 0 → vehicle skipped regardless of consumption."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_vehicle_insights_bulk,
    )

    await _seed_trip(db_session, tuketim=40.0, plaka="35 YY 12", hedef_tuketim=0.0)
    insights = await generate_vehicle_insights_bulk()
    assert insights == []


async def test_generate_vehicle_insights_empty_rows(db_session):
    """No vehicles → no insights."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_vehicle_insights_bulk,
    )

    insights = await generate_vehicle_insights_bulk()
    assert insights == []


async def test_generate_vehicle_insights_exception():
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_vehicle_insights_bulk,
    )

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(side_effect=RuntimeError("DB crash"))
    mock_uow.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "v2.modules.analytics_executive.application.generate_insights.get_uow",
        return_value=mock_uow,
    ):
        insights = await generate_vehicle_insights_bulk()

    assert insights == []


# ---------------------------------------------------------------------------
# generate_driver_insights_bulk
# ---------------------------------------------------------------------------


def _make_mock_uow_ctx_drivers(rows):
    """Inject the (currently UNIMPLEMENTED) driver-stats repo method.

    The real ``analiz_repo`` has no ``get_all_drivers_consumption_stats`` —
    ``generate_driver_insights_bulk`` getattr-guards it and returns [] in reality
    (see test_generate_driver_insights_no_method, which runs against the real DB).
    These low/good/zero-score tests therefore inject the future method to verify
    the score<50 → 'sofor' insight contract for when the repo method lands. This
    is a documented future-capability boundary, not internal-logic mocking.
    """
    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.analiz_repo = MagicMock()
    mock_uow.analiz_repo.get_all_drivers_consumption_stats = AsyncMock(
        return_value=rows
    )
    return mock_uow


async def test_generate_driver_insights_low_score():
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_driver_insights_bulk,
    )

    rows = [{"sofor_id": 5, "ad_soyad": "Mehmet Yılmaz", "performans_skoru": 40.0}]
    mock_uow = _make_mock_uow_ctx_drivers(rows)

    with patch(
        "v2.modules.analytics_executive.application.generate_insights.get_uow",
        return_value=mock_uow,
    ):
        insights = await generate_driver_insights_bulk()

    assert len(insights) == 1
    assert "Mehmet Yılmaz" in insights[0].mesaj
    assert insights[0].hedef_id == 5


async def test_generate_driver_insights_good_score():
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_driver_insights_bulk,
    )

    rows = [{"sofor_id": 6, "ad_soyad": "Ali Can", "performans_skoru": 80.0}]
    mock_uow = _make_mock_uow_ctx_drivers(rows)

    with patch(
        "v2.modules.analytics_executive.application.generate_insights.get_uow",
        return_value=mock_uow,
    ):
        insights = await generate_driver_insights_bulk()

    assert insights == []


async def test_generate_driver_insights_zero_score():
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_driver_insights_bulk,
    )

    rows = [{"sofor_id": 7, "ad_soyad": "Test", "performans_skoru": 0}]
    mock_uow = _make_mock_uow_ctx_drivers(rows)

    with patch(
        "v2.modules.analytics_executive.application.generate_insights.get_uow",
        return_value=mock_uow,
    ):
        insights = await generate_driver_insights_bulk()

    # score=0 is falsy → no insight generated
    assert insights == []


async def test_generate_driver_insights_no_method(db_session):
    """Against the REAL DB the analiz_repo has no get_all_drivers_consumption_stats,
    so the getattr-guard returns [] — the genuine production behaviour today."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_driver_insights_bulk,
    )

    insights = await generate_driver_insights_bulk()
    assert insights == []


async def test_generate_driver_insights_exception():
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_driver_insights_bulk,
    )

    mock_uow = AsyncMock()
    mock_uow.__aenter__ = AsyncMock(side_effect=RuntimeError("crash"))
    mock_uow.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "v2.modules.analytics_executive.application.generate_insights.get_uow",
        return_value=mock_uow,
    ):
        insights = await generate_driver_insights_bulk()

    assert insights == []


# ---------------------------------------------------------------------------
# generate_all_and_save
# ---------------------------------------------------------------------------


# generate_all_and_save runs the three generate_* concurrently via asyncio.gather
# and saves the combined insights to the anomalies alert store. The gather over the
# shared test session works (verified empirically), so these run FULLY REAL — no
# stubbing of the generate_* methods. The key invariant is that the returned count
# equals the rows actually persisted — exactly the data-loss bug this de-mock
# surfaced (a non-zero count with nothing committed).


async def _persisted_insights(db_session):
    return (
        (await db_session.execute(select(Anomaly).where(Anomaly.tip == "insight")))
        .scalars()
        .all()
    )


async def test_generate_all_and_save_no_insights(db_session):
    """Empty DB → no insights, nothing saved, count 0."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_all_and_save,
    )

    count = await generate_all_and_save()
    assert count == 0
    assert (await db_session.execute(select(Anomaly))).scalars().all() == []


async def test_generate_all_and_save_persists_real_insights(db_session):
    """Seeded high consumption → real fleet/vehicle insights are persisted; the
    returned count equals the rows actually committed."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_all_and_save,
    )

    await _seed_trip(db_session, tuketim=40.0, plaka="34 GAT 001", hedef_tuketim=30.0)
    count = await generate_all_and_save()
    rows = await _persisted_insights(db_session)
    assert count >= 1
    assert len(rows) == count  # count == persisted — guards the data-loss bug


async def test_generate_all_and_save_count_matches_persisted(db_session):
    """Vehicle within its own target but high enough for the fleet average →
    fleet insight only; count still equals persisted rows (no over/under count)."""
    from v2.modules.analytics_executive.application.generate_insights import (
        generate_all_and_save,
    )

    await _seed_trip(db_session, tuketim=40.0, plaka="34 GAT 002", hedef_tuketim=40.0)
    count = await generate_all_and_save()
    rows = await _persisted_insights(db_session)
    assert len(rows) == count


# ---------------------------------------------------------------------------
# get_uow
# ---------------------------------------------------------------------------


def test_get_uow_returns_context_manager():
    from v2.modules.analytics_executive.application.generate_insights import (
        _UnitOfWorkContext,
        get_uow,
    )

    ctx = get_uow()
    assert isinstance(ctx, _UnitOfWorkContext)


def test_get_uow_is_different_each_call():
    from v2.modules.analytics_executive.application.generate_insights import get_uow

    c1 = get_uow()
    c2 = get_uow()
    # Each call returns a new instance (not a singleton)
    assert c1 is not c2
