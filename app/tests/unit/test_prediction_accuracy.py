"""
ML tahmin doğruluk regresyon testleri.

Bu testler belirli bilinen girdiler için beklenen çıktı aralıklarını doğrular.
Bir ağırlık değişikliği veya feature engineering regresyonu bu testleri kırar.
"""

import pytest

from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
    RouteConditions,
)

# ---------------------------------------------------------------------------
# Fizik Tahmincisi — Bilinen Girdi → Beklenen Aralık
# ---------------------------------------------------------------------------


class TestPhysicsFuelPredictorAccuracy:
    @pytest.fixture
    def predictor(self):
        return PhysicsBasedFuelPredictor()

    def test_highway_flat_low_load(self, predictor):
        """Otoyol, düz, hafif yük → fizik sabitler aralığında (15–35 L/100km).
        Model toplam kütle (çekici+dorse+yük) bazlı hesaplar; 12t yük ≈ 26.5t toplam.
        """
        route = RouteConditions(
            distance_km=500.0,
            load_ton=12.0,
            otoyol_ratio=0.9,
            devlet_yolu_ratio=0.1,
            sehir_ici_ratio=0.0,
        )
        result = predictor.predict(route)
        assert result is not None
        assert 15.0 <= result.consumption_l_100km <= 35.0, (
            f"Otoyol/düz/hafif: {result.consumption_l_100km:.1f} L/100km beklenen [15–35]"
        )

    def test_mountain_heavy_load(self, predictor):
        """Dağlık, ağır yük → düz hafif yükten belirgin fazla (en az 30 L/100km)."""
        route = RouteConditions(
            distance_km=200.0,
            load_ton=25.0,
            ascent_m=1200.0,
            grade_steep_pct=0.40,
            grade_moderate_pct=0.40,
            grade_gentle_pct=0.20,
        )
        result = predictor.predict(route)
        assert result is not None
        assert result.consumption_l_100km >= 30.0, (
            f"Dağlık/ağır yük: {result.consumption_l_100km:.1f} L/100km, en az 30 beklenir"
        )

    def test_downhill_returns_lower_consumption_than_uphill(self, predictor):
        """İniş dominant rota tırmanış rotasından daha az tüketmeli."""
        uphill_route = RouteConditions(
            distance_km=100.0,
            load_ton=18.0,
            ascent_m=800.0,
            grade_steep_pct=0.30,
            grade_moderate_pct=0.40,
        )
        downhill_route = RouteConditions(
            distance_km=100.0,
            load_ton=18.0,
            descent_m=800.0,
            grade_steep_pct=0.0,
            grade_moderate_pct=0.10,
        )
        uphill_result = predictor.predict(uphill_route)
        downhill_result = predictor.predict(downhill_route)
        assert (
            downhill_result.consumption_l_100km < uphill_result.consumption_l_100km
        ), "İniş dominant rota tırmanıştan daha az yakıt tüketmeli"

    def test_heavier_load_consumes_more(self, predictor):
        """Daha ağır araç daha fazla tüketmeli."""
        light_route = RouteConditions(distance_km=300.0, load_ton=8.0)
        heavy_route = RouteConditions(distance_km=300.0, load_ton=24.0)
        light_result = predictor.predict(light_route)
        heavy_result = predictor.predict(heavy_route)
        assert heavy_result.consumption_l_100km > light_result.consumption_l_100km, (
            "Ağır yük hafif yükten daha fazla yakıt tüketmeli"
        )

    def test_prediction_always_positive(self, predictor):
        """Tüm senaryolarda tahmin pozitif olmalı."""
        routes = [
            RouteConditions(distance_km=50.0, load_ton=5.0),
            RouteConditions(distance_km=1000.0, load_ton=25.0, ascent_m=2000.0),
            RouteConditions(distance_km=200.0, load_ton=15.0, descent_m=800.0),
        ]
        for route in routes:
            result = predictor.predict(route)
            assert result.consumption_l_100km > 0, (
                "Yakıt tüketimi sıfır veya negatif olamaz"
            )
            assert result.total_liters > 0, "Toplam litre sıfır veya negatif olamaz"


# TestARIMATimeSeriesPredictorAccuracy moved to
# v2/services/prediction_ml_service/tests/test_arima_prediction_accuracy.py
# (Task 5, 2026-08-04) -- ARIMATimeSeriesPredictor only lives in that
# service's own package now.
