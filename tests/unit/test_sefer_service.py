from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.entities.models import SeferCreate
from app.core.exceptions import RouteProcessingError
from app.core.services.sefer_service import SeferService


class TestSeferService:
    @pytest.fixture
    def mock_uow(self):
        uow = AsyncMock()
        uow.__aenter__.return_value = uow
        uow.__aexit__.return_value = None
        uow.commit = AsyncMock()

        uow.sefer_repo = AsyncMock()
        uow.sefer_repo.add.return_value = 1
        uow.sefer_repo.get_by_sefer_no.return_value = None
        uow.sefer_repo.has_active_trip.return_value = False

        active_arac = {"id": 1, "aktif": True, "plaka": "34ABC123"}
        active_sofor = {"id": 1, "aktif": True, "ad_soyad": "Test Driver"}
        active_guzergah = {
            "id": 1,
            "adi": "Route 1",
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
        }

        uow.arac_repo = AsyncMock()
        uow.arac_repo.get_by_id.return_value = active_arac

        uow.sofor_repo = AsyncMock()
        uow.sofor_repo.get_by_id.return_value = active_sofor

        uow.session = AsyncMock()
        uow.session.get.return_value = active_guzergah

        uow.lokasyon_repo = AsyncMock()
        uow.lokasyon_repo.get_by_id.return_value = active_guzergah

        uow.guzergah_repo = AsyncMock()
        uow.guzergah_repo.get_by_id.return_value = active_guzergah

        return uow

    @pytest.fixture
    def mock_event_bus(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_event_bus):
        return SeferService(event_bus=mock_event_bus)

    @pytest.mark.asyncio
    async def test_add_sefer_valid(self, service, mock_uow):
        sefer_data = SeferCreate(
            tarih=date.today(),
            arac_id=1,
            sofor_id=1,
            guzergah_id=1,
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=450.0,
            net_kg=25000,
            durum="Tamam",
            bos_sefer=False,
        )

        with (
            patch(
                "app.core.services.sefer_write_service.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "app.core.services.sefer_write_service.RouteValidator.validate_and_correct",
                side_effect=lambda x: x,
            ),
        ):
            result = await service.add_sefer(sefer_data)

        assert result == 1
        mock_uow.sefer_repo.add.assert_called_once()
        mock_uow.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_sefer_same_locations(self, service, mock_uow):
        sefer_data = SeferCreate(
            tarih=date.today(),
            arac_id=1,
            sofor_id=1,
            guzergah_id=1,
            cikis_yeri="Istanbul",
            varis_yeri="Istanbul",
            mesafe_km=10.0,
            net_kg=1000,
            bos_sefer=False,
        )

        with patch(
            "app.core.services.sefer_write_service.UnitOfWork", return_value=mock_uow
        ):
            with pytest.raises(RouteProcessingError, match="aynı olamaz"):
                await service.add_sefer(sefer_data)

    def test_add_sefer_invalid_distance_pydantic(self):
        with pytest.raises(ValidationError) as excinfo:
            SeferCreate(
                tarih=date.today(),
                arac_id=1,
                sofor_id=1,
                guzergah_id=1,
                cikis_yeri="LocA",
                varis_yeri="LocB",
                mesafe_km=0,
                net_kg=1000,
                bos_sefer=False,
            )
        assert "mesafe_km" in str(excinfo.value)

    def test_add_sefer_invalid_weight_pydantic(self):
        with pytest.raises(ValidationError) as excinfo:
            SeferCreate(
                tarih=date.today(),
                arac_id=1,
                sofor_id=1,
                guzergah_id=1,
                cikis_yeri="LocA",
                varis_yeri="LocB",
                mesafe_km=100,
                net_kg=-50,
                bos_sefer=False,
            )
        assert "net_kg" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_add_sefer_future_date_limit(self, service, mock_uow):
        sefer_data = SeferCreate(
            tarih=date.today() + timedelta(days=366),
            arac_id=1,
            sofor_id=1,
            guzergah_id=1,
            cikis_yeri="LocA",
            varis_yeri="LocB",
            mesafe_km=100,
            net_kg=1000,
            bos_sefer=False,
        )

        with patch(
            "app.core.services.sefer_write_service.UnitOfWork", return_value=mock_uow
        ):
            with pytest.raises(RouteProcessingError, match="ileri bir tarih olamaz"):
                await service.add_sefer(sefer_data)

    @pytest.mark.asyncio
    async def test_add_sefer_duplicate_sefer_no(self, service, mock_uow):
        sefer_data = SeferCreate(
            tarih=date.today(),
            arac_id=1,
            sofor_id=1,
            guzergah_id=1,
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=450.0,
            net_kg=25000,
            sefer_no="DUPE-123",
        )
        mock_uow.sefer_repo.get_by_sefer_no.return_value = {
            "id": 100,
            "sefer_no": "DUPE-123",
        }

        with patch(
            "app.core.services.sefer_write_service.UnitOfWork", return_value=mock_uow
        ):
            with pytest.raises(RouteProcessingError, match="zaten kullanımda"):
                await service.add_sefer(sefer_data)

    @pytest.mark.asyncio
    async def test_create_return_trip_success(self, service, mock_uow):
        mock_uow.sefer_repo.get_by_id.return_value = {
            "id": 1,
            "arac_id": 1,
            "sofor_id": 1,
            "dorse_id": None,
            "guzergah_id": 1,
            "sefer_no": "TEST-001",
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "bos_agirlik_kg": 15000,
            "ascent_m": 500,
            "descent_m": 300,
            "flat_distance_km": 200,
        }
        mock_uow.sefer_repo.get_by_sefer_no.return_value = None

        with (
            patch(
                "app.core.services.sefer_write_service.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "app.core.services.sefer_write_service.RouteValidator.validate_and_correct",
                side_effect=lambda x: x,
            ),
        ):
            result = await service.create_return_trip(sefer_id=1)

        assert result == 1
        add_call_kwargs = mock_uow.sefer_repo.add.call_args.kwargs
        assert add_call_kwargs["cikis_yeri"] == "Ankara"
        assert add_call_kwargs["varis_yeri"] == "Istanbul"
        assert add_call_kwargs["ascent_m"] == 300
        assert add_call_kwargs["descent_m"] == 500
        assert add_call_kwargs["sefer_no"] == "TEST-001-D"
        assert add_call_kwargs["bos_sefer"] is True
        assert add_call_kwargs["net_kg"] == 0

    @pytest.mark.asyncio
    async def test_create_return_trip_duplicate_d(self, service, mock_uow):
        mock_uow.sefer_repo.get_by_id.return_value = {
            "id": 2,
            "sefer_no": "TEST-001-D",
            "cikis_yeri": "Ankara",
            "varis_yeri": "Istanbul",
            "mesafe_km": 450.0,
            "arac_id": 1,
            "sofor_id": 1,
            "guzergah_id": 1,
        }
        mock_uow.sefer_repo.get_by_sefer_no.return_value = None

        with (
            patch(
                "app.core.services.sefer_write_service.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "app.core.services.sefer_write_service.RouteValidator.validate_and_correct",
                side_effect=lambda x: x,
            ),
        ):
            await service.create_return_trip(sefer_id=2)

        add_call_kwargs = mock_uow.sefer_repo.add.call_args.kwargs
        assert add_call_kwargs["sefer_no"] == "TEST-001-D"
