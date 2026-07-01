"""
Unit Tests - AracService
"""

import pytest


class TestAracService:
    """Test suite for AracService."""

    def test_service_singleton(self, arac_service):
        """Service should return singleton instance."""
        from app.core.services.arac_service import get_arac_service

        service2 = get_arac_service()
        assert arac_service is service2

    async def test_get_all_vehicles_returns_list(self, arac_service):
        """get_all_vehicles should return a list."""
        vehicles = await arac_service.get_all_vehicles()
        assert isinstance(vehicles, list)

    async def test_get_all_vehicles_only_active(self, arac_service):
        """Default should return only active vehicles."""
        vehicles = await arac_service.get_all_vehicles()
        for v in vehicles:
            assert v.aktif

    async def test_get_vehicle_by_id(self, arac_service):
        """Should retrieve vehicle by ID."""
        vehicles = await arac_service.get_all_vehicles()
        if vehicles:
            try:
                first_id = vehicles[0].id
            except (AttributeError, KeyError):
                # Handle both object and dict access for flexibility in tests
                first_id = (
                    vehicles[0]["id"]
                    if isinstance(vehicles[0], dict)
                    else vehicles[0].id
                )

            vehicle = await arac_service.get_by_id(first_id)
            assert vehicle is not None
            # Handle both object and dict access for flexibility in tests
            v_id = vehicle["id"] if isinstance(vehicle, dict) else vehicle.id
            assert v_id == first_id

    async def test_get_vehicle_by_invalid_id(self, arac_service):
        """Should return None for invalid ID."""
        vehicle = await arac_service.get_by_id(99999)
        assert vehicle is None


class TestAracServiceValidation:
    """Test input validation in AracService."""

    async def test_add_vehicle_plaka_required(self, arac_service):
        """Adding a vehicle without plaka should fail."""
        from app.core.entities.models import AracCreate

        with pytest.raises((ValueError, TypeError)):
            # Pydantic validation error or service logic
            try:
                model = AracCreate(plaka="", marka="Test", model="Test", yil=2020)
                await arac_service.create_arac(model)
            except Exception as e:
                raise ValueError(f"Plaka required: {e}")

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
        edilmeden kalırdı. `validate_plaka_str` (app/core/entities/models.py)
        gerçek regex-tabanlı bir validasyon uyguluyor; bu 3 format zaten
        geçerli — artık gerçek bir assertion, skip yok."""
        from app.core.entities.models import AracCreate

        model = AracCreate(plaka=plaka, marka="Test", model="Test", yil=2020)
        assert model.plaka == expected_normalized

    def test_invalid_plaka_format_raises(self):
        """Regresyon guard'ı: gerçekten geçersiz bir plaka formatı
        `ValidationError` fırlatmalı (validasyon sessizce devre dışı
        kalmamalı)."""
        from pydantic import ValidationError

        from app.core.entities.models import AracCreate

        with pytest.raises(ValidationError):
            AracCreate(plaka="INVALID!!!", marka="Test", model="Test", yil=2020)


class TestAracServiceStats:
    """Test statistics methods in AracService."""

    async def test_get_vehicle_stats(self, arac_service):
        """Should return vehicle statistics."""
        from app.core.entities.models import VehicleStats

        vehicles = await arac_service.get_all_vehicles()
        if vehicles:
            v_id = (
                vehicles[0]["id"] if isinstance(vehicles[0], dict) else vehicles[0].id
            )
            stats = await arac_service.get_vehicle_stats(v_id)
            if stats:
                assert isinstance(stats, VehicleStats)
