"""
Unit Tests - AnalizService
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.entities import Sefer, SeverityEnum, YakitAlimi, YakitPeriyodu
from app.core.services.analiz_service import AnalizService


class TestAnalizServiceAlgorithms:
    """Algorithm-focused tests for AnalizService (Async)"""

    @pytest.fixture
    def service(self):
        # Mock repos for pure algorithm tests
        return AnalizService(yakit_repo=MagicMock(), sefer_repo=MagicMock())

    @pytest.mark.asyncio
    async def test_create_fuel_periods_empty(self, service):
        """Empty list -> empty result"""
        result = await service.create_fuel_periods([])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_record_returns_empty(self, service):
        """Single record -> no period possible"""
        fuel = YakitAlimi(
            id=1,
            tarih=date(2024, 1, 1),
            arac_id=1,
            istasyon="Shell",
            fiyat_tl=45.0,
            litre=500,
            km_sayac=10000,
        )
        result = await service.create_fuel_periods([fuel])
        assert result == []

    @pytest.mark.asyncio
    async def test_two_records_creates_one_period(self, service):
        """Two records -> one period"""
        fuel1 = YakitAlimi(
            id=1,
            tarih=date(2024, 1, 1),
            arac_id=1,
            istasyon="Shell",
            fiyat_tl=45.0,
            litre=500,
            km_sayac=10000,
            depo_durumu="dolu",
        )
        fuel2 = YakitAlimi(
            id=2,
            tarih=date(2024, 1, 10),
            arac_id=1,
            istasyon="BP",
            fiyat_tl=46.0,
            litre=600,
            km_sayac=12000,
            depo_durumu="dolu",
        )

        result = await service.create_fuel_periods([fuel1, fuel2])

        assert len(result) == 1
        period = result[0]
        assert period.arac_id == 1
        assert period.ara_mesafe == 2000
        assert period.toplam_yakit == 600
        assert period.ort_tuketim == 30.0

    @pytest.mark.asyncio
    async def test_weighted_distribution(self, service):
        """Weighted distribution by Ton-Km"""
        period = YakitPeriyodu(
            id=1,
            arac_id=1,
            alim1_id=1,
            alim2_id=2,
            alim1_tarih=date(2024, 1, 1),
            alim1_km=10000,
            alim1_litre=500,
            alim2_tarih=date(2024, 1, 10),
            alim2_km=12000,
            ara_mesafe=2000,
            toplam_yakit=1000,
            ort_tuketim=50,
        )

        trip1 = Sefer(
            id=1,
            tarih=date(2024, 1, 3),
            arac_id=1,
            sofor_id=1,
            cikis_yeri="Ankara",
            varis_yeri="Bursa",
            mesafe_km=500,
            net_kg=20000,
        )
        trip2 = Sefer(
            id=2,
            tarih=date(2024, 1, 5),
            arac_id=1,
            sofor_id=1,
            cikis_yeri="Bursa",
            varis_yeri="Ankara",
            mesafe_km=500,
            net_kg=0,
        )

        result = await service.distribute_fuel_to_trips(period, [trip1, trip2])

        assert result[0].dagitilan_yakit > result[1].dagitilan_yakit
        assert sum(t.dagitilan_yakit for t in result) == pytest.approx(1000, 0.1)


class TestAnalizServiceAnomalies:
    """Anomaly detection tests for AnalizService (Async)"""

    @pytest.fixture
    def service(self):
        return AnalizService(yakit_repo=MagicMock(), sefer_repo=MagicMock())

    @pytest.mark.asyncio
    async def test_detect_anomalies_insufficient_data(self, service):
        """Less than 5 records -> empty result"""
        result = await service.detect_anomalies([30, 31, 32, 33])
        assert result == []

    @pytest.mark.asyncio
    async def test_detects_high_outlier(self, service):
        """High outlier detection"""
        data = [30, 31, 32, 33, 34, 31, 32, 33, 32, 80]
        result = await service.detect_anomalies(data, z_threshold=2.5)

        assert len(result) > 0
        assert any(a.value == 80 for a in result)
        assert result[0].severity in [SeverityEnum.HIGH, SeverityEnum.CRITICAL]


class TestAnalizServiceStats:
    """Statistics and Regression tests for AnalizService (Async)"""

    @pytest.fixture
    def service(self):
        service = AnalizService(yakit_repo=MagicMock(), sefer_repo=MagicMock())
        return service

    @pytest.mark.asyncio
    async def test_analyze_vehicle_consumption(self, service):
        """analyze_vehicle_consumption returns VehicleStats"""
        consumptions = [30, 31, 32, 33, 34, 31, 32, 33, 32, 31]
        result = await service.analyze_vehicle_consumption(
            arac_id=1, consumptions=consumptions
        )

        assert result.arac_id == 1
        assert result.ort_tuketim > 0
        assert result.anomali_sayisi == 0

    @pytest.mark.asyncio
    async def test_calculate_long_term_stats(self, service):
        """Long term regression stats"""
        # Mock yakit_repo.get_all to return data
        service.yakit_repo.get_all = AsyncMock(
            return_value=[
                {"id": 1, "km_sayac": 10000, "litre": 0, "tarih": "2024-01-01"},
                {"id": 2, "km_sayac": 11000, "litre": 300, "tarih": "2024-01-10"},
                {"id": 3, "km_sayac": 12000, "litre": 320, "tarih": "2024-01-20"},
                {"id": 4, "km_sayac": 13000, "litre": 310, "tarih": "2024-01-30"},
            ]
        )

        result = await service.calculate_long_term_stats(arac_id=1)

        assert result is not None
        assert result["ortalama"] > 0
        assert result["guvenilirlik"] > 50
        assert result["toplam_km"] == 3000
