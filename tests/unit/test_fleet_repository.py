from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.database.repositories.arac_repo import AracRepository
from app.database.repositories.sefer_repo import SeferRepository

pytestmark = pytest.mark.asyncio


async def test_get_cost_leakage_stats_logic(db_session):
    """Real-DB: empty DB returns all-zero stats — validates the query structure without mocks."""
    repo = SeferRepository(session=db_session)

    stats = await repo.get_cost_leakage_stats(days=30)

    # Empty DB → COALESCE returns 0 for all aggregates
    assert stats["route_deviation_km"] == 0.0
    assert stats["fuel_gap_liters"] == 0.0
    assert stats["route_deviation_cost"] == 0.0
    assert stats["fuel_gap_cost"] == 0.0
    assert stats["total_leakage_cost"] == 0.0


async def test_get_maintenance_candidates_logic():
    repo = AracRepository()
    repo.execute_query = AsyncMock()
    recent = datetime.now(timezone.utc)
    repo.execute_query.return_value = [
        # 1 kriter → medium (warning)
        {
            "id": 1,
            "plaka": "34 OLD 01",
            "yil": 2010,
            "ort_tuketim": 30.0,
            "toplam_km": 100_000,
            "son_bakim": recent,
        },
        # 1 kriter → medium (warning)
        {
            "id": 2,
            "plaka": "34 GAS 02",
            "yil": 2020,
            "ort_tuketim": 40.0,
            "toplam_km": 100_000,
            "son_bakim": recent,
        },
        # 2 kriter → high (urgent)
        {
            "id": 3,
            "plaka": "34 BAD 03",
            "yil": 2010,
            "ort_tuketim": 40.0,
            "toplam_km": 100_000,
            "son_bakim": recent,
        },
    ]

    result = await repo.get_maintenance_candidates()

    assert result["urgent_count"] == 1
    assert result["warning_count"] == 2
    assert len(result["vehicles"]) == 3

    v3 = next(v for v in result["vehicles"] if v["id"] == 3)
    assert v3["severity"] == "high"
    assert "," in v3["reason"]
