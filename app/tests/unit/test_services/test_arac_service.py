"""
Unit Tests - fleet vehicle use-cases (free functions, v2.modules.fleet)
"""

import pytest

pytestmark = pytest.mark.integration


class TestVehicleUseCases:
    """Test suite for vehicle listing/lookup use-cases."""

    async def test_get_all_vehicles_returns_list(self, db_session):
        from v2.modules.fleet.application.list_vehicles import get_all_vehicles

        vehicles = await get_all_vehicles()
        assert isinstance(vehicles, list)

    async def test_get_all_vehicles_only_active(self, db_session):
        from v2.modules.fleet.application.list_vehicles import get_all_vehicles

        vehicles = await get_all_vehicles()
        for v in vehicles:
            assert v.aktif

    async def test_get_vehicle_by_id(self, db_session):
        from v2.modules.fleet.application.list_vehicles import (
            get_all_vehicles,
            get_vehicle_by_id,
        )

        vehicles = await get_all_vehicles()
        if vehicles:
            first_id = (
                vehicles[0]["id"] if isinstance(vehicles[0], dict) else vehicles[0].id
            )

            vehicle = await get_vehicle_by_id(first_id)
            assert vehicle is not None
            v_id = vehicle["id"] if isinstance(vehicle, dict) else vehicle.id
            assert v_id == first_id

    async def test_get_vehicle_by_invalid_id(self, db_session):
        from v2.modules.fleet.application.list_vehicles import get_vehicle_by_id

        vehicle = await get_vehicle_by_id(99999)
        assert vehicle is None


class TestVehicleValidation:
    """Test input validation in vehicle schemas."""

    def test_add_vehicle_plaka_required(self):
        """Adding a vehicle without plaka should fail validation."""
        from pydantic import ValidationError

        from v2.modules.fleet.schemas import AracCreate

        with pytest.raises((ValueError, TypeError, ValidationError)):
            AracCreate(plaka="", marka="Test", model="Test", yil=2020)

    @pytest.mark.parametrize(
        "plaka,expected_normalized",
        [
            ("34 ABC 123", "34 ABC 123"),
            ("06 XYZ 789", "06 XYZ 789"),
            ("35 AAA 001", "35 AAA 001"),
        ],
    )
    def test_valid_plaka_formats(self, plaka, expected_normalized):
        """2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 23): eskiden
        `validate_plaka_str` gerçekten hata fırlatırsa test `pytest.skip`
        ile geçiyordu — gevşek/bozuk bir validasyon kalıcı olarak fark
        edilmeden kalırdı. Artık gerçek bir assertion, skip yok."""
        from v2.modules.fleet.schemas import AracCreate

        model = AracCreate(plaka=plaka, marka="Test", model="Test", yil=2020)
        assert model.plaka == expected_normalized

    def test_invalid_plaka_format_raises(self):
        """Regresyon guard'ı: gerçekten geçersiz bir plaka formatı
        `ValidationError` fırlatmalı (validasyon sessizce devre dışı
        kalmamalı)."""
        from pydantic import ValidationError

        from v2.modules.fleet.schemas import AracCreate

        with pytest.raises(ValidationError):
            AracCreate(plaka="INVALID!!!", marka="Test", model="Test", yil=2020)


class TestVehicleStats:
    """Test statistics use-case."""

    async def test_get_vehicle_stats(self, db_session):
        from app.core.entities.models import VehicleStats
        from v2.modules.fleet.application.list_vehicles import (
            get_all_vehicles,
            get_vehicle_stats,
        )

        vehicles = await get_all_vehicles()
        if vehicles:
            v_id = (
                vehicles[0]["id"] if isinstance(vehicles[0], dict) else vehicles[0].id
            )
            stats = await get_vehicle_stats(v_id)
            if stats:
                assert isinstance(stats, VehicleStats)
