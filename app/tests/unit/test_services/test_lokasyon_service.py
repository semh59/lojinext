from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.services.lokasyon_service import LokasyonService
from app.database.repositories.lokasyon_repo import LokasyonRepository
from app.schemas.lokasyon import LokasyonCreate, LokasyonUpdate

pytestmark = pytest.mark.integration
# 0-mock epiği: repo artık gerçek LokasyonRepository + gerçek DB (db_session).
# event_bus MagicMock kalır (iç pub/sub yan kanalı, bu testin odağı değil —
# önceki oturumlarda kurulan konvansiyonla tutarlı).


@pytest.fixture
def repo(db_session):
    return LokasyonRepository(session=db_session)


@pytest.fixture
def service(repo):
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    return LokasyonService(repo=repo, event_bus=mock_bus)


@pytest.mark.asyncio
class TestLokasyonService:
    async def test_get_all_paged(self, service, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B", mesafe_km=100.0)
        await db_session.commit()

        result = await service.get_all_paged(skip=0, limit=10)

        assert result["total"] == 1
        assert len(result["items"]) == 1

    async def test_add_lokasyon_simple(self, service, db_session):
        data = LokasyonCreate(
            cikis_yeri="İstanbul",
            varis_yeri="Ankara",
            mesafe_km=450,
            tahmini_sure_saat=5.0,
            zorluk="Normal",
        )

        result = await service.add_lokasyon(data)

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

    @patch.object(LokasyonService, "analyze_route")
    async def test_add_lokasyon_with_coords_triggers_analysis(
        self, mock_analyze, service
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

        result = await service.add_lokasyon(data)

        assert result is not None
        mock_analyze.assert_called_once_with(result)

    async def test_update_lokasyon(self, service, db_session):
        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(db_session, cikis_yeri="A", varis_yeri="B")
        await db_session.commit()

        data = LokasyonUpdate(mesafe_km=500, notlar="Updated Info")
        result = await service.update_lokasyon(lokasyon.id, data)

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

    async def test_delete_lokasyon_soft(self, service, db_session):
        """Active location -> soft delete (aktif=False, row stays)."""
        from sqlalchemy import text

        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="A", varis_yeri="B", aktif=True
        )
        await db_session.commit()

        result = await service.delete_lokasyon(lokasyon.id)

        assert result is True
        row = (
            await db_session.execute(
                text("SELECT aktif FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row.aktif is False

    async def test_delete_lokasyon_hard(self, service, db_session):
        """Inactive location -> hard delete (row removed)."""
        from sqlalchemy import text

        from app.tests._helpers.seed import seed_lokasyon

        lokasyon = await seed_lokasyon(
            db_session, cikis_yeri="A", varis_yeri="B", aktif=False
        )
        await db_session.commit()

        result = await service.delete_lokasyon(lokasyon.id)

        assert result is True
        row = (
            await db_session.execute(
                text("SELECT id FROM lokasyonlar WHERE id = :id"),
                {"id": lokasyon.id},
            )
        ).fetchone()
        assert row is None

    @patch.object(LokasyonService, "_geocode_with_openroute", new_callable=AsyncMock)
    @patch.object(LokasyonService, "_geocode_with_nominatim", new_callable=AsyncMock)
    async def test_geocode_query_prefers_openroute_results(
        self, mock_nominatim, mock_openroute, service
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

        result = await service.geocode_query("Hadimkoy", limit=5)

        assert result[0]["source"] == "ors"
        mock_openroute.assert_awaited_once_with("Hadimkoy", limit=5)
        mock_nominatim.assert_not_awaited()

    @patch.object(LokasyonService, "_geocode_with_openroute", new_callable=AsyncMock)
    @patch.object(LokasyonService, "_geocode_with_nominatim", new_callable=AsyncMock)
    async def test_geocode_query_falls_back_to_nominatim(
        self, mock_nominatim, mock_openroute, service
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

        result = await service.geocode_query("Ostim", limit=3)

        assert result[0]["source"] == "nominatim"
        mock_openroute.assert_awaited_once_with("Ostim", limit=3)
        mock_nominatim.assert_awaited_once_with("Ostim", limit=3)
