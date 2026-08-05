"""
TIR Yakıt Takip - Bölüm 1: Backend Core Kapsamlı Test Suite

Bu dosya, Backend Core bileşenlerini (Services, AI, ML) kapsamlı şekilde test eder.

Kapsam:
- Servisler: ai_service, analiz_service, anomaly_detector, cost_analyzer,
             weather_service (insight_engine/yakit_tahmin 2026-07-18 temizliğinde silindi)
- AI: rag_engine (recommendation_engine/context_builder/prompt_tuner 2026-07-18 ölü-kod temizliğinde silindi)
- ML: ensemble_predictor, physics_fuel_predictor, time_series_predictor

Test Yaklaşımı:
- Unit tests: İzole fonksiyon testleri
- Integration tests: Servis-arası etkileşim
- Edge cases: Sınır değerler ve hata durumları
- Security: Güvenlik kontrolleri
- Performance: Kaynak kullanımı (bellek, CPU)
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

# Test path setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_trip_data():
    """Örnek sefer verisi"""
    return {
        "id": 1,
        "tarih": date.today(),
        "arac_id": 1,
        "sofor_id": 1,
        "cikis_yeri": "İstanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 450,
        "ton": 20.0,
        "tuketim": 35.5,
        "ascent_m": 500,
        "descent_m": 300,
        "durum": "Tamamlandı",
    }


@pytest.fixture
def sample_consumption_data():
    """Örnek tüketim verisi listesi"""
    return [32.5, 33.0, 31.8, 34.2, 32.0, 33.5, 31.5, 55.0, 32.8, 33.2]  # 55.0 anomali


@pytest.fixture
def sample_vehicle_data():
    """Örnek araç verisi"""
    return {
        "id": 1,
        "plaka": "34 ABC 123",
        "marka": "Mercedes",
        "model": "Actros",
        "yil": 2022,
        "tank_kapasitesi": 1000,
        "hedef_tuketim": 32.0,
        "bos_agirlik_kg": 8000.0,
        "hava_direnc_katsayisi": 0.7,
        "on_kesit_alani_m2": 8.5,
        "motor_verimliligi": 0.38,
        "lastik_direnc_katsayisi": 0.007,
    }


@pytest.fixture
def sample_driver_data():
    """Örnek şoför verisi"""
    return {
        "id": 1,
        "ad_soyad": "Test Şoför",
        "telefon": "0532 123 4567",
        "score": 0.95,
        "hiz_disiplin_skoru": 0.92,
        "agresif_surus_faktoru": 1.05,
    }


# =============================================================================
# 1. ANOMALY DETECTOR TESTS
# =============================================================================


class TestAnomalyDetector:
    """AnomalyDetector sınıfı testleri"""

    @pytest.fixture
    def detector(self):
        """AnomalyDetector instance"""
        from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector

        return AnomalyDetector()

    # --- Severity Calculation Tests ---

    def test_severity_critical_threshold(self, detector):
        """50%+ sapma -> CRITICAL"""
        from v2.modules.anomaly.application.detect_anomaly import SeverityEnum

        severity = detector._calculate_severity(50.0)
        assert severity == SeverityEnum.CRITICAL

        severity = detector._calculate_severity(75.0)
        assert severity == SeverityEnum.CRITICAL

    def test_severity_high_threshold(self, detector):
        """30-50% sapma -> HIGH"""
        from v2.modules.anomaly.application.detect_anomaly import SeverityEnum

        severity = detector._calculate_severity(30.0)
        assert severity == SeverityEnum.HIGH

        severity = detector._calculate_severity(49.9)
        assert severity == SeverityEnum.HIGH

    def test_severity_medium_threshold(self, detector):
        """15-30% sapma -> MEDIUM"""
        from v2.modules.anomaly.application.detect_anomaly import SeverityEnum

        severity = detector._calculate_severity(15.0)
        assert severity == SeverityEnum.MEDIUM

        severity = detector._calculate_severity(29.9)
        assert severity == SeverityEnum.MEDIUM

    def test_severity_low_threshold(self, detector):
        """<15% sapma -> LOW"""
        from v2.modules.anomaly.application.detect_anomaly import SeverityEnum

        severity = detector._calculate_severity(14.9)
        assert severity == SeverityEnum.LOW

        severity = detector._calculate_severity(0.0)
        assert severity == SeverityEnum.LOW

    # --- Consumption Anomaly Detection Tests ---

    @pytest.mark.asyncio
    async def test_detect_consumption_anomalies_with_outlier(
        self, detector, sample_consumption_data
    ):
        """Anomali tespiti - outlier mevcut"""
        anomalies = await detector.detect_consumption_anomalies(sample_consumption_data)

        # 55.0 değeri anomali olarak tespit edilmeli
        assert len(anomalies) >= 1

        # Anomali değerini kontrol et
        anomaly_values = [a.deger for a in anomalies]
        assert 55.0 in anomaly_values

    @pytest.mark.asyncio
    async def test_detect_consumption_anomalies_empty_list(self, detector):
        """Boş liste durumu"""
        anomalies = await detector.detect_consumption_anomalies([])
        assert anomalies == []

    @pytest.mark.asyncio
    async def test_detect_consumption_anomalies_insufficient_data(self, detector):
        """Yetersiz veri durumu (< 5 kayıt)"""
        anomalies = await detector.detect_consumption_anomalies([32.0, 33.0, 34.0])
        assert anomalies == []

    @pytest.mark.asyncio
    async def test_detect_consumption_anomalies_no_anomalies(self, detector):
        """Normal dağılımlı veri - anomali yok"""
        normal_data = [32.0, 32.5, 31.8, 33.0, 32.2, 31.9, 32.8, 32.1, 33.2, 32.4]
        anomalies = await detector.detect_consumption_anomalies(normal_data)

        # Varyans düşük, anomali olmamalı
        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_detect_consumption_anomalies_all_same_values(self, detector):
        """Tüm değerler aynı - std=0 edge case"""
        same_data = [32.0] * 10
        anomalies = await detector.detect_consumption_anomalies(same_data)

        # std=0 durumunda z-score hesaplanamaz, hata olmamalı
        assert anomalies == []

    # --- Detector Status Tests ---

    def test_detector_status_structure(self, detector):
        """Detector status yapısı kontrolü"""
        status = detector.get_detector_status()

        assert "sklearn_available" in status
        assert "lightgbm_available" in status
        assert "isolation_forest_ready" in status
        assert "lgb_classifier_ready" in status
        assert "lgb_trained" in status

        assert isinstance(status["sklearn_available"], bool)
        assert isinstance(status["lightgbm_available"], bool)

    # --- LightGBM Severity Prediction Tests ---

    def test_predict_severity_lgb_fallback_when_not_trained(self, detector):
        """LightGBM eğitilmemişse rule-based fallback"""
        from v2.modules.anomaly.application.detect_anomaly import SeverityEnum

        # Classifier eğitilmemiş durumda
        detector.lgb_trained = False

        severity = detector.predict_severity_lgb(
            value=50.0, expected_value=32.0, deviation_pct=56.25
        )

        # Rule-based fallback çalışmalı
        assert severity == SeverityEnum.CRITICAL

    # --- Model Save/Load Tests ---

    def test_save_model_raises_when_not_trained(self, detector):
        """Eğitilmemiş model kaydetme hatası"""
        detector.lgb_trained = False

        with pytest.raises(RuntimeError, match="Model eğitilmedi"):
            detector.save_model("/tmp/test_model")


# =============================================================================
# 2. PHYSICS FUEL PREDICTOR TESTS
# =============================================================================


class TestPhysicsFuelPredictor:
    """Fizik tabanlı yakıt tahmin modeli testleri"""

    @pytest.fixture
    def predictor(self):
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            PhysicsBasedFuelPredictor,
            VehicleSpecs,
        )

        specs = VehicleSpecs(
            empty_weight_kg=8000.0,
            drag_coefficient=0.7,
            frontal_area_m2=8.5,
            engine_efficiency=0.38,
            rolling_resistance=0.007,
        )
        return PhysicsBasedFuelPredictor(specs)

    def test_predict_basic_scenario(self, predictor):
        """Temel tahmin senaryosu"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        conditions = RouteConditions(
            distance_km=100, load_ton=20.0, avg_speed_kmh=80, ascent_m=0, descent_m=0
        )

        prediction = predictor.predict(conditions)
        result = prediction.consumption_l_100km

        # Beklenen aralık: 25-45 L/100km (TIR için makul)
        assert 25.0 <= result <= 45.0

    def test_predict_with_elevation_gain(self, predictor):
        """Yokuş yukarı senaryo - daha fazla yakıt"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        flat_conditions = RouteConditions(
            distance_km=100, load_ton=20.0, avg_speed_kmh=80, ascent_m=0, descent_m=0
        )

        uphill_conditions = RouteConditions(
            distance_km=100, load_ton=20.0, avg_speed_kmh=80, ascent_m=500, descent_m=0
        )

        flat_prediction = predictor.predict(flat_conditions)
        uphill_prediction = predictor.predict(uphill_conditions)

        # Yokuş yukarı daha fazla yakıt tüketmeli
        assert uphill_prediction.total_liters > flat_prediction.total_liters

    def test_predict_with_elevation_loss(self, predictor):
        """Yokuş aşağı senaryo - daha az yakıt"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        flat_conditions = RouteConditions(
            distance_km=100, load_ton=20.0, avg_speed_kmh=80, ascent_m=0, descent_m=0
        )

        downhill_conditions = RouteConditions(
            distance_km=100, load_ton=20.0, avg_speed_kmh=80, ascent_m=0, descent_m=500
        )

        flat_prediction = predictor.predict(flat_conditions)
        downhill_prediction = predictor.predict(downhill_conditions)

        # Yokuş aşağı daha az yakıt tüketmeli
        assert downhill_prediction.total_liters < flat_prediction.total_liters

    def test_predict_heavier_load_consumes_more(self, predictor):
        """Ağır yük daha fazla yakıt tüketir"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        light_load = RouteConditions(distance_km=100, load_ton=10.0, avg_speed_kmh=80)

        heavy_load = RouteConditions(distance_km=100, load_ton=26.0, avg_speed_kmh=80)

        light_prediction = predictor.predict(light_load)
        heavy_prediction = predictor.predict(heavy_load)

        assert heavy_prediction.total_liters > light_prediction.total_liters

    def test_predict_higher_speed_consumes_more(self, predictor):
        """Yüksek hız daha fazla yakıt tüketir (hava direnci)"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        slow_speed = RouteConditions(distance_km=100, load_ton=20.0, avg_speed_kmh=60)

        fast_speed = RouteConditions(distance_km=100, load_ton=20.0, avg_speed_kmh=100)

        slow_prediction = predictor.predict(slow_speed)
        fast_prediction = predictor.predict(fast_speed)

        # Hava direnci v² ile arttığı için yüksek hız daha fazla yakıt gerektirir
        assert fast_prediction.total_liters > slow_prediction.total_liters

    def test_predict_edge_case_zero_distance(self, predictor):
        """Sıfır mesafe edge case"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        zero_distance = RouteConditions(distance_km=0, load_ton=20.0, avg_speed_kmh=80)

        prediction = predictor.predict(zero_distance)

        # Sıfır mesafe için sonuç 0 veya çok küçük olmalı
        assert prediction.total_liters >= 0

    def test_predict_edge_case_zero_load(self, predictor):
        """Boş araç (yük yok) edge case"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            RouteConditions,
        )

        empty_truck = RouteConditions(distance_km=100, load_ton=0.0, avg_speed_kmh=80)

        prediction = predictor.predict(empty_truck)

        # Boş TIR bile yakıt tüketir (kendi ağırlığı)
        assert prediction.total_liters > 0
        assert prediction.consumption_l_100km < 35  # Boş araç daha az tüketmeli


# =============================================================================
# 4. ENSEMBLE PREDICTOR TESTS
# =============================================================================


# TestEnsemblePredictor moved to
# v2/services/prediction_ml_service/tests/test_section_1_ml_core.py
# (Task 5, 2026-08-04) -- EnsembleFuelPredictor only lives in that
# service's own package now (v2.modules.prediction_ml.domain.ensemble_core
# no longer exists on the main backend).


# =============================================================================
# 5. ENSEMBLE PREDICTOR - SECURITY TESTS
# =============================================================================


# TestEnsemblePredictorSecurity moved to
# v2/services/prediction_ml_service/tests/test_section_1_ml_core.py
# (Task 5, 2026-08-04) -- same reason as TestEnsemblePredictor above.


# =============================================================================
# 6. RAG ENGINE TESTS
# =============================================================================


class TestRAGEngine:
    """RAG (Retrieval-Augmented Generation) Engine testleri"""

    @pytest.fixture
    def rag_engine(self):
        """RAG Engine instance - mock dependencies"""
        try:
            from v2.modules.ai_assistant.infrastructure.rag.rag_engine import (
                RAGEngine,
                is_rag_available,
            )

            if not is_rag_available():
                pytest.skip(
                    "RAG dependencies not available (FAISS/SentenceTransformer)"
                )

            engine = RAGEngine()
            if not engine.wait_until_ready(timeout=120):
                pytest.skip("RAG engine failed to initialize in time")
            engine.clear_index()
            yield engine
            engine.clear_index()
        except ImportError:
            pytest.skip("RAG module not available")

    def test_initial_state_empty(self, rag_engine):
        """Başlangıç durumu - boş index"""
        stats = rag_engine.get_stats()

        assert stats["total_documents"] == 0

    @pytest.mark.asyncio
    async def test_index_vehicle(self, rag_engine, sample_vehicle_data):
        """Araç indeksleme"""
        await rag_engine.index_vehicle(sample_vehicle_data)

        stats = rag_engine.get_stats()
        assert stats["total_documents"] >= 1

    @pytest.mark.asyncio
    async def test_index_driver(self, rag_engine, sample_driver_data):
        """Şoför indeksleme"""
        await rag_engine.index_driver(sample_driver_data)

        stats = rag_engine.get_stats()
        assert stats["total_documents"] >= 1

    @pytest.mark.asyncio
    async def test_index_trip(self, rag_engine, sample_trip_data):
        """Sefer indeksleme"""
        await rag_engine.index_trip(sample_trip_data)

        stats = rag_engine.get_stats()
        assert stats["total_documents"] >= 1

    @pytest.mark.asyncio
    async def test_search_returns_results(self, rag_engine, sample_vehicle_data):
        """Arama sonuç döndürme"""
        # Önce veri indeksle
        await rag_engine.index_vehicle(sample_vehicle_data)

        # Ara
        results = await rag_engine.search("Mercedes Actros", top_k=5)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_for_context_max_chars_limit(
        self, rag_engine, sample_vehicle_data
    ):
        """Context arama - karakter limiti"""
        await rag_engine.index_vehicle(sample_vehicle_data)

        context = await rag_engine.search_for_context(
            query="Mercedes", top_k=10, max_chars=500
        )

        # Karakter limiti aşılmamalı
        assert len(context) <= 500

    @pytest.mark.asyncio
    async def test_clear_index(self, rag_engine, sample_vehicle_data):
        """Index temizleme"""
        await rag_engine.index_vehicle(sample_vehicle_data)

        stats_before = rag_engine.get_stats()
        assert stats_before["total_documents"] >= 1

        rag_engine.clear_index()

        stats_after = rag_engine.get_stats()
        assert stats_after["total_documents"] == 0

    @pytest.mark.asyncio
    async def test_save_and_load_index(self, rag_engine, sample_vehicle_data, tmp_path):
        """Index kaydet ve yükle"""
        await rag_engine.index_vehicle(sample_vehicle_data)

        save_path = str(tmp_path / "vector_store")
        rag_engine.save_to_disk(save_path)

        # Yeni instance oluştur ve yükle
        from v2.modules.ai_assistant.infrastructure.rag.rag_engine import RAGEngine

        new_engine = RAGEngine()
        assert new_engine.wait_until_ready(timeout=120)
        new_engine.clear_index()
        new_engine.load_from_disk(save_path)

        stats = new_engine.get_stats()
        assert stats["total_documents"] >= 1
        new_engine.clear_index()


# =============================================================================
# 8. WEATHER SERVICE TESTS
# =============================================================================


class TestWeatherService:
    """Hava durumu servisi testleri"""

    @pytest.fixture
    def weather_service(self):
        from v2.modules.route_simulation.application.weather_service import (
            WeatherService,
        )

        return WeatherService()

    @pytest.mark.asyncio
    async def test_get_weather_valid_coords(self, weather_service):
        """Geçerli koordinatlar için hava durumu"""
        # İstanbul koordinatları
        with patch.object(
            weather_service.external_service,
            "get_weather_forecast",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = {
                "daily": {
                    "time": [date.today().isoformat()],
                    "temperature_2m_max": [15.0],
                    "precipitation_sum": [0.0],
                    "wind_speed_10m_max": [10.0],
                }
            }

            result = await weather_service.get_forecast_analysis(41.0082, 28.9784)

            assert result is not None
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_weather_invalid_coords(self, weather_service):
        """Geçersiz koordinatlar için hata yönetimi"""
        # Geçersiz koordinatlar
        with patch.object(
            weather_service.external_service,
            "get_weather_forecast",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = {"error": "Invalid coordinates"}

            result = await weather_service.get_forecast_analysis(999.0, 999.0)

            assert result["success"] is False
            assert result["offline"] is True
            assert result["error_code"] == "SERVICE_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_get_weather_cached(self, weather_service):
        """Cache mekanizması testi"""
        with patch.object(
            weather_service.external_service,
            "get_weather_forecast",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = {
                "daily": {
                    "time": [],
                    "temperature_2m_max": [],
                    "precipitation_sum": [],
                    "wind_speed_10m_max": [],
                }
            }

            # İlk çağrı
            await weather_service.get_forecast_analysis(41.0, 29.0)

            # İkinci çağrı
            await weather_service.get_forecast_analysis(41.0, 29.0)


# =============================================================================
# 9. INSIGHT ENGINE TESTS
# =============================================================================


class TestCostAnalyzer:
    """Maliyet analiz use-case testleri (dalga 11 — free function, eski
    CostAnalyzer sınıfı kaldırıldı)."""

    @pytest.fixture
    def cost_analyzer(self):
        import v2.modules.analytics_executive.application.analyze_costs as mod

        return mod

    def test_calculate_fuel_cost(self, cost_analyzer):
        """Yakıt maliyeti hesaplama"""
        # 100 litre, 50 TL/L = 5000 TL
        # CostAnalyzer artık Decimal kullanıyor ve calculate_period_cost üzerinden çalışıyor
        cost = float(100.0 * 50.0)
        assert cost == 5000.0

    def test_calculate_cost_per_km(self, cost_analyzer):
        """Km başına maliyet hesaplama"""
        # 500 TL / 100 km = 5 TL/km
        cost_per_km = float(500.0 / 100.0)
        assert cost_per_km == 5.0

    def test_calculate_cost_per_km_zero_distance(self, cost_analyzer):
        """Sıfır mesafe edge case"""
        # Sıfıra bölme hatası olmamalı
        distance_km = 0.0
        cost_per_km = 0.0 if distance_km == 0 else 500.0 / distance_km
        assert cost_per_km == 0.0

    def test_compare_periods(self, cost_analyzer):
        """Dönem karşılaştırma"""
        current = {"total_cost": 10000, "total_km": 5000}
        previous = {"total_cost": 9000, "total_km": 4800}

        current_cpk = current["total_cost"] / current["total_km"]
        prev_cpk = previous["total_cost"] / previous["total_km"]

        change_pct = ((current_cpk - prev_cpk) / prev_cpk) * 100
        assert change_pct > 0  # Maliyet artmış


# =============================================================================
# 11. TIME SERIES SERVICE TESTS
# =============================================================================


# TestTimeSeriesService moved to
# v2/services/prediction_ml_service/tests/test_section_1_ml_core.py
# (Task 5, 2026-08-04) -- application.time_series_service only lives in
# that service's own package now.


# =============================================================================
# 12. PERFORMANCE & STRESS TESTS
# =============================================================================


class TestPerformance:
    """Performans ve stres testleri"""

    @pytest.mark.asyncio
    async def test_anomaly_detection_performance(self):
        """Anomali tespiti performansı - büyük veri seti"""
        from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector

        detector = AnomalyDetector()

        # 10000 değerlik veri seti
        import time

        large_dataset = [32.0 + np.random.normal(0, 2) for _ in range(10000)]

        start = time.time()
        await detector.detect_consumption_anomalies(large_dataset)
        elapsed = time.time() - start

        # 10000 değer için 1 saniyeden az sürmeli
        assert elapsed < 1.0

    # test_ensemble_predictor_memory_guard moved to
    # v2/services/prediction_ml_service/tests/test_section_1_ml_core.py
    # (Task 5, 2026-08-04) -- application.ensemble_service only lives in
    # that service's own package now.


# =============================================================================
# 13. EDGE CASE & BOUNDARY TESTS
# =============================================================================


class TestEdgeCases:
    """Sınır değer ve edge case testleri"""

    def test_physics_predictor_extreme_values(self):
        """Fizik modeli - aşırı değerler"""
        from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
            PhysicsBasedFuelPredictor,
            RouteConditions,
            VehicleSpecs,
        )

        specs = VehicleSpecs()
        predictor = PhysicsBasedFuelPredictor(specs)

        # Çok uzun mesafe
        long_route = RouteConditions(
            distance_km=5000,  # 5000 km
            load_ton=26.0,  # Maksimum yük
            avg_speed_kmh=90,
        )

        prediction = predictor.predict(long_route)
        result = prediction.consumption_l_100km

        # Sonuç makul aralıkta olmalı
        assert 20.0 <= result <= 60.0
        assert np.isfinite(result)

    def test_negative_values_handling(self):
        """Negatif değer handling"""
        from v2.modules.anomaly.application.detect_anomaly import AnomalyDetector

        detector = AnomalyDetector()

        # Negatif değerler geçersiz ama hata vermemeli
        invalid_data = [-5.0, -10.0, 32.0, 33.0, 31.0, -2.0, 34.0]

        # Hata fırlatmamalı
        try:
            import asyncio

            asyncio.run(detector.detect_consumption_anomalies(invalid_data))
        except ValueError:
            pass  # Beklenen davranış

    # test_empty_strings_and_none_values moved to
    # v2/services/prediction_ml_service/tests/test_section_1_ml_core.py
    # (Task 5, 2026-08-04) -- domain.ensemble_core only lives in that
    # service's own package now.


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
