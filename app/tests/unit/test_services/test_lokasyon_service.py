from unittest.mock import AsyncMock, patch

import pytest

from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.application.geocode_location import geocode_location
from v2.modules.location.application.list_locations import list_locations
from v2.modules.location.application.update_location import update_location
from v2.modules.location.infrastructure.repository import LokasyonRepository
from v2.modules.location.schemas import LokasyonCreate, LokasyonUpdate

pytestmark = pytest.mark.integration
# 0-mock epiği: repo gerçek LokasyonRepository + gerçek DB (db_session).
# LokasyonService sınıfı yok — her use-case standalone fonksiyon (bkz.
# v2/modules/location/public.py docstring'i).


@pytest.fixture
def repo(db_session):
    return LokasyonRepository(session=db_session)


@pytest.mark.asyncio
class TestLocationUseCases:
    async def test_list_locations(self, repo, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B", mesafe_km=100.0)
        await db_session.commit()

        result = await list_locations(repo, skip=0, limit=10)

        assert result["total"] == 1
        assert len(result["items"]) == 1

    async def test_create_location_simple(self, repo, db_session):
        data = LokasyonCreate(
            cikis_yeri="İstanbul",
            varis_yeri="Ankara",
            mesafe_km=450,
            tahmini_sure_saat=5.0,
            zorluk="Normal",
        )

        result = await create_location(repo, data)

        assert result is not None
        from sqlalchemy import text

        row = (
            await db_session.execute(
                text("SELECT cikis_yeri, varis_yeri FROM lokasyonlar WHERE id = :id"),
                {"id": result},
            )
        ).fetchone()
        assert row.cikis_yeri == "İstanbul"
        assert row.varis_yeri == "Ankara"

    @patch(
        "v2.modules.location.application.create_location.analyze_location_route",
        new_callable=AsyncMock,
    )
    async def test_create_location_with_coords_triggers_analysis(
        self, mock_analyze, repo
    ):
        data = LokasyonCreate(
            cikis_yeri="İstanbul",
            varis_yeri="Kocaeli",
            mesafe_km=100,
            cikis_lat=41.0,
            cikis_lon=29.0,
            varis_lat=40.8,
            varis_lon=29.4,
        )

        result = await create_location(repo, data)

        assert result is not None
        mock_analyze.assert_called_once_with(repo, result)

    async def test_update_location(self, repo, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B")
        await db_session.commit()

        data = LokasyonUpdate(mesafe_km=500, notlar="Updated Info")
        result = await update_location(repo, lokasyon.id, data)

        assert result is True
        from sqlalchemy import text

        row = (
            await db_session.execute(
                text("SELECT mesafe_km, notlar FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row.mesafe_km == 500
        assert row.notlar == "Updated Info"

    async def test_delete_location_soft(self, repo, db_session):
        """Active location -> soft delete (aktif=False, row stays)."""
        from sqlalchemy import text

        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="A", varis_yeri="B", aktif=True
        )
        await db_session.commit()

        result = await delete_location(repo, lokasyon.id)

        assert result is True
        row = (
            await db_session.execute(
                text("SELECT aktif FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row.aktif is False

    async def test_delete_location_hard(self, repo, db_session):
        """Inactive location -> hard delete (row removed)."""
        from sqlalchemy import text

        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="A", varis_yeri="B", aktif=False
        )
        await db_session.commit()

        result = await delete_location(repo, lokasyon.id)

        assert result is True
        row = (
            await db_session.execute(
                text("SELECT id FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row is None

    @patch(
        "v2.modules.location.application.geocode_location.geocode_via_nominatim",
        new_callable=AsyncMock,
    )
    @patch(
        "v2.modules.location.application.geocode_location.geocode_via_openroute",
        new_callable=AsyncMock,
    )
    async def test_geocode_location_prefers_openroute_results(
        self, mock_openroute, mock_nominatim
    ):
        mock_openroute.return_value = [
            {
                "lat": 41.07,
                "lon": 28.54,
                "label": "Hadimkoy Lojistik",
                "source": "ors",
            }
        ]
        mock_nominatim.return_value = [
            {
                "lat": 41.08,
                "lon": 28.55,
                "label": "Fallback Result",
                "source": "nominatim",
            }
        ]

        result = await geocode_location("Hadimkoy", limit=5)

        assert result[0]["source"] == "ors"
        mock_openroute.assert_awaited_once_with("Hadimkoy", limit=5)
        mock_nominatim.assert_not_awaited()

    @patch(
        "v2.modules.location.application.geocode_location.geocode_via_nominatim",
        new_callable=AsyncMock,
    )
    @patch(
        "v2.modules.location.application.geocode_location.geocode_via_openroute",
        new_callable=AsyncMock,
    )
    async def test_geocode_location_falls_back_to_nominatim(
        self, mock_openroute, mock_nominatim
    ):
        mock_openroute.return_value = []
        mock_nominatim.return_value = [
            {
                "lat": 39.96,
                "lon": 32.74,
                "label": "Ostim Fabrika",
                "source": "nominatim",
            }
        ]

        result = await geocode_location("Ostim", limit=3)

        assert result[0]["source"] == "nominatim"
        mock_openroute.assert_awaited_once_with("Ostim", limit=3)
        mock_nominatim.assert_awaited_once_with("Ostim", limit=3)
