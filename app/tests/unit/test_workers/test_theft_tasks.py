"""theft_tasks.py birim testleri — real DB for the pattern-scan query.

_run_pattern_scan runs a raw multi-join theft-pattern SQL (fuel_investigations →
anomalies → seferler → sofor/arac, GROUP BY … HAVING COUNT >= min_count). The
happy paths run against the real test DB with a seeded investigation chain; the
returned pattern count is the real query result, not a mocked row list.

Two branches stay mocked, honestly: the DB-error paths (forcing a real DB error
mid-test is not reproducible cleanly) and the null-avg-score guard (the SQL
filters `suspicion_score IS NOT NULL`, so a real AVG can never be null — the
`float(... or 0)` guard is defensive and only reachable with an injected row).
"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import insert

from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor
from v2.modules.anomaly.infrastructure.theft_tasks import (
    _run_pattern_scan,
    daily_pattern_scan,
)
from v2.modules.anomaly.public import Anomaly, FuelInvestigation
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

pytestmark = pytest.mark.integration


async def _seed_theft_pattern(db_session, *, n=3, score=0.87):
    """Seed n fuel_investigations for one sofor's sefer → one grouped pattern."""
    arac = await seed_arac(db_session, plaka="34 THF 001")
    sofor = await seed_sofor(db_session, ad_soyad="Theft Sofor")
    sefer = await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
    for _ in range(n):
        aid = (
            await db_session.execute(
                insert(Anomaly).values(
                    tarih=date.today(),
                    tip="tuketim",
                    kaynak_tip="sefer",
                    kaynak_id=sefer.id,
                    deger=30.0,
                    beklenen_deger=20.0,
                    sapma_yuzde=50.0,
                    severity="high",
                    aciklama="theft",
                )
            )
        ).inserted_primary_key[0]
        await db_session.execute(
            insert(FuelInvestigation).values(
                anomaly_id=aid,
                status="open",
                suspicion_score=score,
                evidence_files=[],
                created_at=datetime.now(timezone.utc),
            )
        )
    await db_session.commit()
    return sofor, arac


def _uow_error_mock():
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session.execute = AsyncMock(side_effect=Exception("DB error"))
    return mock_uow


def _make_uow_mock(rows):
    """Injected-row UoW double — only for the defensive null-avg guard."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    mock_uow.__aexit__.return_value = None
    mock_uow.session = mock_session
    return mock_uow


# --- real DB ---------------------------------------------------------------


async def test_run_pattern_scan_no_patterns(db_session):
    """Empty DB → no patterns."""
    result = await _run_pattern_scan(days=30, min_count=3, limit=100)
    assert result["patterns_found"] == 0
    assert result["window_days"] == 30
    assert result["min_count"] == 3


async def test_run_pattern_scan_with_patterns(db_session, caplog):
    """A seeded 3-investigation chain for one sofor → one real pattern + log."""
    import logging

    await _seed_theft_pattern(db_session, n=3)
    with caplog.at_level(
        logging.WARNING, logger="v2.modules.anomaly.infrastructure.theft_tasks"
    ):
        result = await _run_pattern_scan(days=30, min_count=3)

    assert result["patterns_found"] == 1
    assert "THEFT_PATTERN" in caplog.text


async def test_run_pattern_scan_below_min_count(db_session):
    """2 investigations with min_count=3 → no pattern (real HAVING filter)."""
    await _seed_theft_pattern(db_session, n=2)
    result = await _run_pattern_scan(days=30, min_count=3)
    assert result["patterns_found"] == 0


async def test_run_pattern_scan_custom_params(db_session):
    result = await _run_pattern_scan(days=7, min_count=5, limit=50)
    assert result["window_days"] == 7
    assert result["min_count"] == 5


async def test_run_pattern_scan_returns_meta_keys(db_session):
    result = await _run_pattern_scan()
    assert {"patterns_found", "window_days", "min_count"} <= result.keys()


# --- defensive / pure (documented boundaries) ------------------------------


async def test_run_pattern_scan_db_error():
    """DB error propagates (task layer catches it) — forced via a UoW double."""
    err_uow = _uow_error_mock()
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=err_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        with pytest.raises(Exception, match="DB error"):
            await _run_pattern_scan()


def test_daily_pattern_scan_is_celery_task():
    assert daily_pattern_scan.name == "theft.daily_pattern_scan"


def test_daily_pattern_scan_handles_db_error():
    """DB error → task returns an error key instead of raising (forced double)."""
    err_uow = _uow_error_mock()
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=err_uow)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        result = daily_pattern_scan.apply().get()
    assert "error" in result
    assert result["patterns_found"] == 0


async def test_run_pattern_scan_avg_score_null():
    """Defensive guard: float(avg or 0) when avg is null. The real SQL filters
    suspicion_score IS NOT NULL so a real AVG is never null — exercised with an
    injected row."""
    rows = [
        {
            "sofor_id": 1,
            "arac_id": 5,
            "occurrence_count": 4,
            "avg_suspicion_score": None,
            "last_seen": None,
            "sofor_adi": None,
            "plaka": None,
        }
    ]
    uow_inst = _make_uow_mock(rows)
    with (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    ):
        result = await _run_pattern_scan()
    assert result["patterns_found"] == 1
