from unittest.mock import MagicMock, patch

import pytest

from app.core.services.anomaly_detection_service import (
    AnomalyDetectionService,
    get_anomaly_detection_service,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)
    cache.set = MagicMock()
    return cache


@pytest.fixture
def service(mock_cache):
    with patch(
        "app.core.services.anomaly_detection_service.get_cache_manager",
        return_value=mock_cache,
    ):
        return AnomalyDetectionService()


class TestAnomalyDetectionService:
    async def test_detect_anomalies_happy_path(self, service):
        consumptions = [10.0, 10.5, 11.0, 9.5, 20.0, 25.0, 10.2, 10.8]
        result = await service.detect_anomalies(consumptions, z_threshold=2.5)
        assert isinstance(result, list)

    async def test_detect_anomalies_no_outliers(self, service):
        consumptions = [10.0, 11.0, 12.0, 10.5, 11.5]
        result = await service.detect_anomalies(consumptions)
        assert isinstance(result, list)

    async def test_detect_anomalies_empty_list(self, service):
        result = await service.detect_anomalies([])
        assert result == []

    async def test_detect_anomalies_insufficient_data(self, service):
        consumptions = [10.0, 20.0]
        result = await service.detect_anomalies(consumptions)
        assert result == []

    async def test_detect_anomalies_with_nan_values(self, service):
        consumptions = [10.0, float("nan"), 12.0, 11.0, 9.0]
        result = await service.detect_anomalies(consumptions)
        assert isinstance(result, list)

    async def test_detect_anomalies_custom_threshold(self, service):
        consumptions = [10.0, 11.0, 12.0, 11.5, 10.5, 100.0]
        result = await service.detect_anomalies(consumptions, z_threshold=3.0)
        assert isinstance(result, list)

    async def test_detect_anomalies_use_iqr(self, service):
        consumptions = [5.0, 10.0, 10.5, 11.0, 11.5, 50.0]
        result = await service.detect_anomalies(consumptions, use_iqr=True)
        assert isinstance(result, list)

    async def test_detect_anomalies_less_than_5_items(self, service):
        result = await service.detect_anomalies([10.0, 11.0, 12.0])
        assert result == []

    async def test_detect_anomalies_with_inf_values(self, service):
        consumptions = [10.0, 11.0, float("inf"), 12.0, 10.5, 11.2]
        result = await service.detect_anomalies(consumptions)
        assert isinstance(result, list)

    async def test_detect_anomalies_z_threshold_variation(self, service):
        consumptions = [10.0, 10.5, 11.0, 9.5, 20.0, 10.2, 10.8, 10.3]
        result_strict = await service.detect_anomalies(consumptions, z_threshold=1.5)
        result_lenient = await service.detect_anomalies(consumptions, z_threshold=4.0)
        assert len(result_strict) >= len(result_lenient)

    async def test_detect_anomalies_iqr_disabled(self, service):
        consumptions = [10.0, 10.5, 11.0, 9.5, 20.0, 10.2, 10.8, 10.3]
        result_iqr = await service.detect_anomalies(
            consumptions, use_iqr=True, z_threshold=2.5
        )
        result_no_iqr = await service.detect_anomalies(
            consumptions, use_iqr=False, z_threshold=2.5
        )
        assert isinstance(result_iqr, list) and isinstance(result_no_iqr, list)

    async def test_analyze_vehicle_consumption(self, service):
        consumptions = [10.0, 11.0, 12.0, 11.5, 10.5]
        result = await service.analyze_vehicle_consumption(
            arac_id=1, consumptions=consumptions
        )
        assert result is not None
        assert result.arac_id == 1

    async def test_analyze_vehicle_consumption_happy_path(self, service, mock_cache):
        mock_cache.get.return_value = None
        consumptions = [10.0, 10.5, 11.0, 9.5, 10.2, 10.8]
        result = await service.analyze_vehicle_consumption(
            arac_id=1, consumptions=consumptions
        )
        assert result.arac_id == 1
        assert result.toplam_sefer == 6
        mock_cache.set.assert_called_once()

    async def test_analyze_vehicle_consumption_cache_hit(self, service, mock_cache):
        cached_result = MagicMock()
        cached_result.arac_id = 1
        mock_cache.get.return_value = cached_result
        consumptions = [10.0, 10.5, 11.0, 9.5, 10.2, 10.8]
        result = await service.analyze_vehicle_consumption(
            arac_id=1, consumptions=consumptions
        )
        assert result == cached_result
        mock_cache.set.assert_not_called()

    def test_calculate_eei_normal_values(self, service):
        eei = service.calculate_eei(actual_consumption=10.0, predicted_consumption=30.0)
        assert eei == 300.0

    def test_calculate_eei_zero_actual_consumption(self, service):
        eei = service.calculate_eei(actual_consumption=0.0, predicted_consumption=30.0)
        assert eei == 0.0

    def test_calculate_eei_zero_predicted_consumption(self, service):
        eei = service.calculate_eei(actual_consumption=10.0, predicted_consumption=0.0)
        assert eei == 100.0

    def test_singleton_pattern(self):
        service1 = get_anomaly_detection_service()
        service2 = get_anomaly_detection_service()
        assert service1 is service2
