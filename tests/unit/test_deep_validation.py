import os
import sys

import pytest

sys.path.append(os.getcwd())

from app.core.services.route_validator import RouteValidator
from v2.modules.prediction_ml.domain.physics_fuel_predictor import (
    PhysicsBasedFuelPredictor,
    RouteConditions,
)


class TestDeepValidation:
    @pytest.fixture
    def predictor(self):
        return PhysicsBasedFuelPredictor()

    def test_guarded_prediction_limit(self, predictor):
        """
        Giriş verisi (yükseklik) hatalı/uç olsa bile tahmin gerçekçi üst limitlerde kalmalı.
        """
        # 60km mesafede 3000m tırmanış (Normalde imkansız bir eğim: %5)
        bad_route = RouteConditions(
            distance_km=60.0, load_ton=25.0, ascent_m=3000.0, avg_speed_kmh=70
        )

        result = predictor.predict(bad_route)

        # Guarded limit 85.0 L/100km olmalı
        assert result.consumption_l_100km <= 85.0
        assert result.consumption_l_100km > 0
        print(f"Guarded Prediction Result: {result.consumption_l_100km} L/100km")

    def test_route_validator_extreme_ascent(self):
        """
        Aşırı yüksek tırmanış verileri otoyol standartlarına (%1.2) çekilmeli.
        """
        # 60km için 1288m tırmanış (%2.1)
        data = {"mesafe_km": 60.0, "ascent_m": 1288.0, "descent_m": 1288.0}

        corrected = RouteValidator.validate_and_correct(data)

        _, cap = RouteValidator._get_grade_thresholds(60.0)
        expected_ascent = round(60.0 * 1000 * cap, 1)
        assert corrected["ascent_m"] == expected_ascent
        assert corrected.get("is_corrected") is True
        print(f"Validator Corrected {data['ascent_m']} to {corrected['ascent_m']}")

    def test_route_validator_normal_ascent(self):
        """
        Normal sınırlar içerisindeki (%0.5) veriler değiştirilmemeli.
        """
        data = {"mesafe_km": 100.0, "ascent_m": 500.0, "descent_m": 500.0}

        corrected = RouteValidator.validate_and_correct(data)

        assert corrected["ascent_m"] == 500.0
        assert corrected.get("is_corrected") is False

    def test_prediction_empty_vs_loaded(self, predictor):
        """
        Boş ve dolu araç arasındaki tüketim farkı mantıklı olmalı.
        """
        route_params = {"distance_km": 100.0, "ascent_m": 200.0, "avg_speed_kmh": 80}

        empty_route = RouteConditions(**route_params, load_ton=0.0, is_empty_trip=True)
        loaded_route = RouteConditions(
            **route_params, load_ton=25.0, is_empty_trip=False
        )

        empty_res = predictor.predict(empty_route)
        loaded_res = predictor.predict(loaded_route)

        # Dolu araç boş araçtan daha fazla yakmalı
        assert loaded_res.total_liters > empty_res.total_liters
        # Tipik TIR farkı (20-22L vs 30-35L)
        diff_percent = (
            (loaded_res.total_liters - empty_res.total_liters)
            / empty_res.total_liters
            * 100
        )
        assert 30 <= diff_percent <= 100
        print(
            f"Empty: {empty_res.consumption_l_100km}, Loaded: {loaded_res.consumption_l_100km}, Diff: %{diff_percent:.1f}"
        )


if __name__ == "__main__":
    # Testleri manuel çalıştırmak için (eğer pytest yoksa)
    import sys

    pytest.main([__file__])
