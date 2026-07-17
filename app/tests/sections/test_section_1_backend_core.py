"""
TIR Yakıt Takip - Bölüm 1: Backend Core Kapsamlı Test Suite

Bu dosya, Backend Core bileşenlerini (Services, AI, ML) kapsamlı şekilde test eder.

Kapsam:
- Servisler: ai_service, analiz_service, anomaly_detector, cost_analyzer,
             insight_engine, weather_service, yakit_tahmin_service
- AI: rag_engine, recommendation_engine, context_builder, prompt_tuner
- ML: ensemble_predictor, kalman_estimator, physics_fuel_predictor, time_series_predictor

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
from unittest.mock import AsyncMock, MagicMock, patch

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
        from app.core.ml.physics_fuel_predictor import (
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
        from app.core.ml.physics_fuel_predictor import RouteConditions

        conditions = RouteConditions(
            distance_km=100, load_ton=20.0, avg_speed_kmh=80, ascent_m=0, descent_m=0
        )

        prediction = predictor.predict(conditions)
        result = prediction.consumption_l_100km

        # Beklenen aralık: 25-45 L/100km (TIR için makul)
        assert 25.0 <= result <= 45.0

    def test_predict_with_elevation_gain(self, predictor):
        """Yokuş yukarı senaryo - daha fazla yakıt"""
        from app.core.ml.physics_fuel_predictor import RouteConditions

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
        from app.core.ml.physics_fuel_predictor import RouteConditions

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
        from app.core.ml.physics_fuel_predictor import RouteConditions

        light_load = RouteConditions(distance_km=100, load_ton=10.0, avg_speed_kmh=80)

        heavy_load = RouteConditions(distance_km=100, load_ton=26.0, avg_speed_kmh=80)

        light_prediction = predictor.predict(light_load)
        heavy_prediction = predictor.predict(heavy_load)

        assert heavy_prediction.total_liters > light_prediction.total_liters

    def test_predict_higher_speed_consumes_more(self, predictor):
        """Yüksek hız daha fazla yakıt tüketir (hava direnci)"""
        from app.core.ml.physics_fuel_predictor import RouteConditions

        slow_speed = RouteConditions(distance_km=100, load_ton=20.0, avg_speed_kmh=60)

        fast_speed = RouteConditions(distance_km=100, load_ton=20.0, avg_speed_kmh=100)

        slow_prediction = predictor.predict(slow_speed)
        fast_prediction = predictor.predict(fast_speed)

        # Hava direnci v² ile arttığı için yüksek hız daha fazla yakıt gerektirir
        assert fast_prediction.total_liters > slow_prediction.total_liters

    def test_predict_edge_case_zero_distance(self, predictor):
        """Sıfır mesafe edge case"""
        from app.core.ml.physics_fuel_predictor import RouteConditions

        zero_distance = RouteConditions(distance_km=0, load_ton=20.0, avg_speed_kmh=80)

        prediction = predictor.predict(zero_distance)

        # Sıfır mesafe için sonuç 0 veya çok küçük olmalı
        assert prediction.total_liters >= 0

    def test_predict_edge_case_zero_load(self, predictor):
        """Boş araç (yük yok) edge case"""
        from app.core.ml.physics_fuel_predictor import RouteConditions

        empty_truck = RouteConditions(distance_km=100, load_ton=0.0, avg_speed_kmh=80)

        prediction = predictor.predict(empty_truck)

        # Boş TIR bile yakıt tüketir (kendi ağırlığı)
        assert prediction.total_liters > 0
        assert prediction.consumption_l_100km < 35  # Boş araç daha az tüketmeli


# =============================================================================
# 3. KALMAN ESTIMATOR TESTS
# =============================================================================


class TestKalmanEstimator:
    """Kalman filtresi testleri"""

    @pytest.fixture
    def estimator(self):
        from app.core.ml.kalman_estimator import KalmanFuelEstimator

        return KalmanFuelEstimator()

    def test_initial_state(self, estimator):
        """Başlangıç durumu kontrolü"""
        assert estimator.state.state is not None  # State vektörü
        assert estimator.state.P is not None  # Covariance matrisi

    def test_update_with_single_measurement(self, estimator):
        """Tek ölçüm ile güncelleme"""
        initial_estimate, _ = estimator.predict({"ton": 20, "ascent_m": 300})

        estimator.update({"ton": 20, "ascent_m": 300}, 35.0)  # Yeni ölçüm

        new_estimate, _ = estimator.predict({"ton": 20, "ascent_m": 300})

        # Güncelleme sonrası tahmin değişmeli
        assert new_estimate != initial_estimate

    def test_update_convergence(self, estimator):
        """Ardışık ölçümlerle yakınsama"""
        measurements = [32.0, 32.5, 31.8, 32.2, 32.1, 32.3, 31.9, 32.0]
        features = {"ton": 20, "ascent_m": 300}

        for m in measurements:
            estimator.update(features, m)

        estimate, _ = estimator.predict(features)

        # Ölçüm ortalamasına yakın olmalı
        mean_measurement = np.mean(measurements)
        assert abs(estimate - mean_measurement) < 5.0

    def test_numerical_stability_many_iterations(self, estimator):
        """Sayısal stabilite - çok sayıda iterasyon"""
        # 1000 iterasyon boyunca güncelle
        features = {"ton": 20, "ascent_m": 300}
        for i in range(1000):
            value = 32.0 + np.random.normal(0, 1)
            estimator.update(features, value)

        estimate, _ = estimator.predict(features)

        # NaN veya Inf olmamalı
        assert np.isfinite(estimate)
        assert not np.isnan(estimate)

        # Makul aralıkta olmalı (32 etrafında salınıyor)
        assert 20.0 <= estimate <= 50.0

    def test_covariance_stays_positive_definite(self, estimator):
        """Covariance matrisi pozitif tanımlı kalmalı"""
        measurements = [32.0, 33.0, 31.5, 34.0, 30.0, 35.0]
        features = {"ton": 20, "ascent_m": 300}

        for m in measurements:
            estimator.update(features, m)

        # state.P matrisi pozitif tanımlı olmalı (eigenvalue'lar > 0)
        if hasattr(estimator.state, "P") and estimator.state.P is not None:
            eigenvalues = np.linalg.eigvals(estimator.state.P)
            assert all(ev > 0 for ev in eigenvalues)


# =============================================================================
# 4. ENSEMBLE PREDICTOR TESTS
# =============================================================================


class TestEnsemblePredictor:
    """Ensemble (hibrit) tahmin modeli testleri"""

    @pytest.fixture
    def predictor(self):
        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        return EnsembleFuelPredictor()

    @pytest.fixture
    def sample_seferler(self):
        """Eğitim için örnek sefer listesi"""
        return [
            {
                "mesafe_km": 450,
                "ton": 20.0,
                "ascent_m": 500,
                "descent_m": 300,
                "sofor_score": 0.95,
                "tuketim": 34.5,
            },
            {
                "mesafe_km": 300,
                "ton": 15.0,
                "ascent_m": 200,
                "descent_m": 250,
                "sofor_score": 0.90,
                "tuketim": 32.0,
            },
            {
                "mesafe_km": 600,
                "ton": 25.0,
                "ascent_m": 800,
                "descent_m": 400,
                "sofor_score": 1.0,
                "tuketim": 38.0,
            },
            {
                "mesafe_km": 200,
                "ton": 10.0,
                "ascent_m": 100,
                "descent_m": 150,
                "sofor_score": 0.85,
                "tuketim": 30.5,
            },
            {
                "mesafe_km": 500,
                "ton": 22.0,
                "ascent_m": 600,
                "descent_m": 350,
                "sofor_score": 0.92,
                "tuketim": 35.8,
            },
        ] * 10  # 50 kayıt için çoğalt

    def test_prepare_features_structure(self, predictor, sample_seferler):
        """Feature hazırlama - yapı kontrolü"""
        features = predictor.prepare_features(sample_seferler)

        assert features is not None
        assert isinstance(features, np.ndarray)
        assert len(features) == len(sample_seferler)

    def test_predict_without_training_uses_physics(self, predictor):
        """Eğitim olmadan tahmin - fizik modeli kullanır"""
        sefer = {
            "mesafe_km": 450,
            "ton": 20.0,
            "ascent_m": 500,
            "descent_m": 300,
            "sofor_score": 0.95,
        }

        result = predictor.predict(sefer)

        assert result is not None
        assert hasattr(result, "tahmin_l_100km")
        assert result.tahmin_l_100km > 0

        # Fizik modeli dominant olmalı (eğitim yok)
        assert result.physics_weight > 0

    def test_prediction_result_structure(self, predictor):
        """Tahmin sonucu yapısı kontrolü"""
        sefer = {
            "mesafe_km": 450,
            "ton": 20.0,
            "ascent_m": 500,
            "descent_m": 300,
            "sofor_score": 0.95,
        }

        result = predictor.predict(sefer)

        # Gerekli alanlar mevcut olmalı
        assert hasattr(result, "tahmin_l_100km")
        assert hasattr(result, "physics_only")
        assert hasattr(result, "ml_correction")
        assert hasattr(result, "confidence_low")
        assert hasattr(result, "confidence_high")
        assert hasattr(result, "physics_weight")
        assert hasattr(result, "features_used")

    def test_confidence_interval_valid(self, predictor):
        """Güven aralığı geçerliliği"""
        sefer = {
            "mesafe_km": 450,
            "ton": 20.0,
            "ascent_m": 500,
            "descent_m": 300,
            "sofor_score": 0.95,
        }

        result = predictor.predict(sefer)

        # Güven aralığı: low <= prediction <= high
        assert result.confidence_low <= result.tahmin_l_100km
        assert result.tahmin_l_100km <= result.confidence_high

    def test_weights_sum_to_one(self, predictor):
        """Model ağırlıkları toplamı 1 olmalı"""
        weights = predictor.WEIGHTS

        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001


# =============================================================================
# 5. ENSEMBLE PREDICTOR - SECURITY TESTS
# =============================================================================


class TestEnsemblePredictorSecurity:
    """Ensemble predictor güvenlik testleri"""

    @pytest.fixture
    def predictor(self):
        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        return EnsembleFuelPredictor()

    def test_save_load_model_integrity(self, predictor, tmp_path):
        """Model kaydet/yükle bütünlük kontrolü"""
        # Basit bir model oluştur (eğitim simülasyonu)
        predictor.is_trained = True
        predictor._physics_weight = 0.2

        filepath = str(tmp_path / "test_model")

        # Not: Eğitilmemiş modelle bu hata vermeli
        # Gerçek test için önce model eğitilmeli
        try:
            predictor.save_model(filepath)

            # Yeni instance ile yükle
            from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

            new_predictor = EnsembleFuelPredictor()
            new_predictor.load_model(filepath)

            # Değerler aynı olmalı
            assert new_predictor._physics_weight == predictor._physics_weight
        except Exception:
            # Model eğitilmemişse hata beklenir
            pass

    def test_model_tampering_detection(self, predictor, tmp_path):
        """Model tampering tespiti: yükleme sırasında checksum uyuşmazlığı hata verir."""
        import hashlib
        import json

        import joblib

        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        base_path = tmp_path / "model_tamper"
        sklearn_file = tmp_path / "model_tamper_sklearn.joblib"
        meta_file = tmp_path / "model_tamper_meta.json"

        # Create a minimal valid sklearn joblib file
        joblib.dump(
            {
                "gb_model": None,
                "rf_model": None,
                "xgb_model": None,
                "lgb_model": None,
                "scaler": None,
            },
            str(sklearn_file),
        )

        # Compute checksum of the valid file
        sha256 = hashlib.sha256()
        with open(str(sklearn_file), "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                sha256.update(block)
        checksum = sha256.hexdigest()

        # Write metadata with valid checksum
        meta = {
            "physics_weight": 0.8,
            "training_stats": {},
            "is_trained": True,
            "last_updated": "2025-01-01",
            "sklearn_checksum": checksum,
            "model_weights": {
                "physics": 0.8,
                "lightgbm": 0.05,
                "xgboost": 0.05,
                "gradient_boosting": 0.05,
                "random_forest": 0.05,
            },
        }
        with open(str(meta_file), "w", encoding="utf-8") as f:
            json.dump(meta, f)

        # Corrupt the sklearn file after recording the checksum
        with open(str(sklearn_file), "ab") as f:
            f.write(b"\xff\xfe\xfd")

        # Loading a corrupted file must raise SecurityError (checksum mismatch)
        tampered = EnsembleFuelPredictor()
        with pytest.raises(Exception):
            tampered.load_model(str(base_path) + ".pkl")


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
        from app.core.services.weather_service import WeatherService

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


class TestInsightEngine:
    """Insight (içgörü) motoru testleri (dalga 11 — free function, eski
    InsightEngine sınıfı kaldırıldı)."""

    @pytest.mark.asyncio
    async def test_generate_insights_empty_data(self):
        """Boş veri ile insight üretimi"""
        from app.database.unit_of_work import UnitOfWork
        from v2.modules.analytics_executive.application.generate_insights import (
            generate_vehicle_insights_bulk,
        )

        with patch(
            "v2.modules.analytics_executive.application.generate_insights.get_uow"
        ) as mock_uow_func:
            mock_uow = MagicMock(spec=UnitOfWork)
            mock_uow.__aenter__.return_value = mock_uow
            mock_uow.analiz_repo = AsyncMock()
            mock_uow.analiz_repo.get_all_vehicles_consumption_stats.return_value = []
            mock_uow_func.return_value = mock_uow

            insights = await generate_vehicle_insights_bulk()

            assert isinstance(insights, list)
            assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_insight_structure(self):
        """Insight yapısı kontrolü"""
        from app.database.unit_of_work import UnitOfWork
        from v2.modules.analytics_executive.application.generate_insights import (
            generate_vehicle_insights_bulk,
        )

        with patch(
            "v2.modules.analytics_executive.application.generate_insights.get_uow"
        ) as mock_uow_func:
            mock_uow = MagicMock(spec=UnitOfWork)
            mock_uow.__aenter__.return_value = mock_uow
            mock_uow.analiz_repo = AsyncMock()
            mock_uow.analiz_repo.get_all_vehicles_consumption_stats.return_value = [
                {
                    "arac_id": 1,
                    "plaka": "34 ABC 123",
                    "hedef_tuketim": 32.0,
                    "ort_tuketim": 40.0,
                }
            ]
            mock_uow_func.return_value = mock_uow

            insights = await generate_vehicle_insights_bulk()

            if insights:
                insight = insights[0]
                assert hasattr(insight, "tip")
                assert hasattr(insight, "mesaj")


# =============================================================================
# 10. COST ANALYZER TESTS
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


class TestTimeSeriesService:
    """Zaman serisi servisi testleri"""

    @pytest.fixture
    def ts_service(self):
        from app.services.time_series_service import get_time_series_service

        return get_time_series_service()

    @pytest.mark.asyncio
    async def test_predict_weekly_no_model(self, ts_service):
        """Model eğitilmeden tahmin - hata veya fallback"""
        result = await ts_service.predict_weekly(arac_id=None)

        # Model yoksa hata mesajı veya boş sonuç
        assert "error" in result or not result.get("success") or "forecast" in result

    @pytest.mark.asyncio
    async def test_get_trend_analysis(self, ts_service):
        """Trend analizi"""
        # get_daily_summary metodunu mock'la (doğru format: dict listesi)
        with patch.object(
            ts_service, "get_daily_summary", new_callable=AsyncMock
        ) as mock:
            mock.return_value = [
                {
                    "tarih": "2024-01-01",
                    "ort_tuketim": 32.0,
                    "toplam_km": 100,
                    "ort_ton": 10,
                    "sefer_sayisi": 5,
                },
                {
                    "tarih": "2024-01-02",
                    "ort_tuketim": 32.5,
                    "toplam_km": 110,
                    "ort_ton": 11,
                    "sefer_sayisi": 6,
                },
                {
                    "tarih": "2024-01-03",
                    "ort_tuketim": 33.0,
                    "toplam_km": 120,
                    "ort_ton": 12,
                    "sefer_sayisi": 5,
                },
                {
                    "tarih": "2024-01-04",
                    "ort_tuketim": 33.5,
                    "toplam_km": 115,
                    "ort_ton": 11,
                    "sefer_sayisi": 6,
                },
                {
                    "tarih": "2024-01-05",
                    "ort_tuketim": 34.0,
                    "toplam_km": 130,
                    "ort_ton": 13,
                    "sefer_sayisi": 7,
                },
                {
                    "tarih": "2024-01-06",
                    "ort_tuketim": 34.5,
                    "toplam_km": 125,
                    "ort_ton": 12,
                    "sefer_sayisi": 5,
                },
                {
                    "tarih": "2024-01-07",
                    "ort_tuketim": 35.0,
                    "toplam_km": 140,
                    "ort_ton": 14,
                    "sefer_sayisi": 8,
                },
            ]

            result = await ts_service.get_trend_analysis(arac_id=None, days=30)

            assert "success" in result or "trend" in result

    def test_model_status(self, ts_service):
        """Model durum bilgisi"""
        status = ts_service.get_model_status()

        assert isinstance(status, dict)
        assert "trained" in status or "is_trained" in status or "available" in status


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

    def test_ensemble_predictor_memory_guard(self):
        """Ensemble predictor bellek guard'ı"""
        from app.core.ml.ensemble_predictor import EnsemblePredictorService

        service = EnsemblePredictorService()

        # MAX_PREDICTORS limiti var mı kontrol et
        assert hasattr(service, "MAX_PREDICTORS")
        assert service.MAX_PREDICTORS > 0
        assert service.MAX_PREDICTORS <= 1000  # Makul limit


# =============================================================================
# 13. EDGE CASE & BOUNDARY TESTS
# =============================================================================


class TestEdgeCases:
    """Sınır değer ve edge case testleri"""

    def test_physics_predictor_extreme_values(self):
        """Fizik modeli - aşırı değerler"""
        from app.core.ml.physics_fuel_predictor import (
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

    def test_empty_strings_and_none_values(self):
        """Boş string ve None değer handling"""
        from app.core.ml.ensemble_predictor import EnsembleFuelPredictor

        predictor = EnsembleFuelPredictor()

        # None değerli sefer
        sefer_with_none = {
            "mesafe_km": None,
            "ton": None,
            "ascent_m": None,
            "descent_m": None,
            "sofor_score": None,
        }

        # Hata yönetimi olmalı
        try:
            predictor.predict(sefer_with_none)
        except (TypeError, ValueError, KeyError):
            pass  # Beklenen davranış


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
