"""YakitService unit tests — real DB via db_session fixture."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def _make_yakit_create(**kwargs):
    from app.core.entities.models import YakitAlimiCreate

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
    def test_service_exists(self):
        """YakitService class is importable."""
        from app.core.services.yakit_service import YakitService

        assert YakitService is not None

    async def test_basic_initialization(self):
        """YakitService can be instantiated without a real DB."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        assert svc is not None

    async def test_happy_path_add_yakit(self, db_session):
        """add_yakit returns an integer ID on success (real DB)."""
        from app.core.services.yakit_service import YakitService
        from app.database.models import Arac

        arac = Arac(plaka="34YKT001", marka="Test", model="Dilim19", aktif=True)
        db_session.add(arac)
        await db_session.flush()

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=arac.id)
        result = await svc.add_yakit(data)

        assert isinstance(result, int) and result > 0

    async def test_add_yakit_raises_for_zero_litres(self):
        """YakitAlimiCreate Pydantic schema rejects litre=0 at construction."""
        from app.core.entities.models import YakitAlimiCreate

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
        from app.core.entities.models import YakitAlimiCreate

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
        from app.core.services.yakit_service import YakitService
        from app.database.models import Arac

        arac = Arac(plaka="34YKT002", marka="Test", model="Dilim19", aktif=True)
        db_session.add(arac)
        await db_session.flush()

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(
            arac_id=arac.id, tarih=date.today() + timedelta(days=5)
        )

        with pytest.raises(ValueError, match="İleri tarihli"):
            await svc.add_yakit(data)

    async def test_add_yakit_raises_for_duplicate(self, db_session):
        """add_yakit raises ValueError when duplicate detected (real DB)."""
        from app.core.services.yakit_service import YakitService
        from app.database.models import Arac, YakitAlimi

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

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=arac.id, tarih=entry_date, litre=300.0)

        with pytest.raises(ValueError, match="Duplicate"):
            await svc.add_yakit(data)

    async def test_add_yakit_raises_for_inactive_vehicle(self, db_session):
        """add_yakit raises ValueError when vehicle is inactive (real DB)."""
        from app.core.services.yakit_service import YakitService
        from app.database.models import Arac

        arac = Arac(plaka="34YKT004", marka="Test", model="Dilim19", aktif=False)
        db_session.add(arac)
        await db_session.flush()

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        data = _make_yakit_create(arac_id=arac.id)

        with pytest.raises(ValueError, match="passive or invalid"):
            await svc.add_yakit(data)

    async def test_get_stats_returns_dict(self, db_session):
        """get_stats returns a dict with expected keys (real DB, may be empty)."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.get_stats()

        assert isinstance(result, dict)
        assert "toplam_yakit" in result

    async def test_get_all_paged_returns_dict(self, db_session):
        """get_all_paged returns dict with items and total (real DB, empty)."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.get_all_paged()

        assert "items" in result
        assert "total" in result

    async def test_delete_yakit_not_found_returns_false(self, db_session):
        """delete_yakit returns False when record not found (real DB)."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.delete_yakit(999999)

        assert result is False

    async def test_bulk_add_yakit_empty_list(self):
        """bulk_add_yakit returns 0 for empty input."""
        from app.core.services.yakit_service import YakitService

        svc = YakitService(repo=MagicMock(), event_bus=MagicMock())
        result = await svc.bulk_add_yakit([])
        assert result == 0
