"""Fuel (yakit) use-case unit tests — real DB via db_session fixture.

Dalga 4 (B.1 free-function refactor): YakitService class deleted — no
constructor-injected event_bus/repo to mock (the @publishes decorator is
documented dead code, see v2/modules/fuel/events.py). test_service_exists /
test_basic_initialization removed — no class/constructor-injected repo left
to assert on (same pattern as fleet's test_arac_service_reactivate.py).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from v2.modules.fuel.application.add_yakit import add_yakit
from v2.modules.fuel.application.bulk_add_yakit import bulk_add_yakit
from v2.modules.fuel.application.delete_yakit import delete_yakit
from v2.modules.fuel.application.list_yakit import get_all_paged, get_stats

pytestmark = pytest.mark.integration


def _make_yakit_create(**kwargs):
    from v2.modules.fuel.domain.entities import YakitAlimiCreate

    defaults = {
        "arac_id": 1,
        "tarih": date.today() - timedelta(days=1),
        "istasyon": "Test Istasyon",
        "fiyat_tl": 40.0,
        "litre": 300.0,
        "km_sayac": 125000,
        "fis_no": "F001",
        "depo_durumu": "Dolu",
    }
    defaults.update(kwargs)
    return YakitAlimiCreate(**defaults)


class TestYakitService:
    async def test_happy_path_add_yakit(self, db_session):
        """add_yakit returns an integer ID on success (real DB)."""
        from v2.modules.fleet.public import AracORM as Arac

        arac = Arac(plaka="34YKT001", marka="Test", model="Dilim19", aktif=True)
        db_session.add(arac)
        await db_session.flush()

        data = _make_yakit_create(arac_id=arac.id)
        result = await add_yakit(data)

        assert isinstance(result, int) and result > 0

    async def test_add_yakit_raises_for_zero_litres(self):
        """YakitAlimiCreate Pydantic schema rejects litre=0 at construction."""
        from v2.modules.fuel.domain.entities import YakitAlimiCreate

        with pytest.raises(Exception):  # pydantic ValidationError
            YakitAlimiCreate(
                arac_id=1,
                tarih=date.today() - timedelta(days=1),
                istasyon="Test",
                fiyat_tl=40.0,
                litre=0.0,
                km_sayac=125000,
                fis_no="F001",
                depo_durumu="Dolu",
            )

    async def test_add_yakit_raises_for_zero_price(self):
        """YakitAlimiCreate Pydantic schema rejects fiyat_tl=0 at construction."""
        from v2.modules.fuel.domain.entities import YakitAlimiCreate

        with pytest.raises(Exception):  # pydantic ValidationError
            YakitAlimiCreate(
                arac_id=1,
                tarih=date.today() - timedelta(days=1),
                istasyon="Test",
                fiyat_tl=0.0,
                litre=300.0,
                km_sayac=125000,
                fis_no="F001",
                depo_durumu="Dolu",
            )

    async def test_add_yakit_raises_for_future_date(self, db_session):
        """add_yakit raises ValueError for a future date (real DB)."""
        from v2.modules.fleet.public import AracORM as Arac

        arac = Arac(plaka="34YKT002", marka="Test", model="Dilim19", aktif=True)
        db_session.add(arac)
        await db_session.flush()

        data = _make_yakit_create(
            arac_id=arac.id, tarih=date.today() + timedelta(days=5)
        )

        with pytest.raises(ValueError, match="İleri tarihli"):
            await add_yakit(data)

    async def test_add_yakit_raises_for_duplicate(self, db_session):
        """add_yakit raises ValueError when duplicate detected (real DB)."""
        from app.database.models import YakitAlimi
        from v2.modules.fleet.public import AracORM as Arac

        arac = Arac(plaka="34YKT003", marka="Test", model="Dilim19", aktif=True)
        db_session.add(arac)
        await db_session.flush()

        entry_date = date.today() - timedelta(days=2)
        existing = YakitAlimi(
            arac_id=arac.id,
            tarih=entry_date,
            istasyon="Dup Station",
            fiyat_tl=Decimal("40.0"),
            litre=Decimal("300.0"),
            toplam_tutar=Decimal("12000.0"),
            km_sayac=125000,
            depo_durumu="Dolu",
            durum="Bekliyor",
            aktif=True,
        )
        db_session.add(existing)
        await db_session.flush()

        data = _make_yakit_create(arac_id=arac.id, tarih=entry_date, litre=300.0)

        with pytest.raises(ValueError, match="Duplicate"):
            await add_yakit(data)

    async def test_add_yakit_raises_for_inactive_vehicle(self, db_session):
        """add_yakit raises ValueError when vehicle is inactive (real DB)."""
        from v2.modules.fleet.public import AracORM as Arac

        arac = Arac(plaka="34YKT004", marka="Test", model="Dilim19", aktif=False)
        db_session.add(arac)
        await db_session.flush()

        data = _make_yakit_create(arac_id=arac.id)

        with pytest.raises(ValueError, match="passive or invalid"):
            await add_yakit(data)

    async def test_get_stats_returns_dict(self, db_session):
        """get_stats returns a dict with expected keys (real DB, may be empty)."""
        result = await get_stats()

        assert isinstance(result, dict)
        assert "toplam_yakit" in result

    async def test_get_all_paged_returns_dict(self, db_session):
        """get_all_paged returns dict with items and total (real DB, empty)."""
        result = await get_all_paged()

        assert "items" in result
        assert "total" in result

    async def test_delete_yakit_not_found_returns_false(self, db_session):
        """delete_yakit returns False when record not found (real DB)."""
        result = await delete_yakit(999999)

        assert result is False

    async def test_bulk_add_yakit_empty_list(self):
        """bulk_add_yakit returns 0 for empty input."""
        result = await bulk_add_yakit([])
        assert result == 0
