"""
YakitTahminService coverage tests — targeting uncovered branches.
Repos and external calls are fully mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service():
    from app.core.services.yakit_tahmin_service import YakitTahminService

    return YakitTahminService()


def _make_analiz_repo_mock(training_data=None, params=None):
    mock = AsyncMock()
    mock.get_training_seferler = AsyncMock(return_value=training_data or [])
    mock.save_model_params = AsyncMock(return_value=None)
    mock.get_model_params = AsyncMock(return_value=params)
    return mock


def _make_arac_repo_mock(vehicles=None):
    mock = AsyncMock()
    mock.get_all = AsyncMock(return_value=vehicles or [])
    return mock


def _make_valid_params():
    """Return a valid model-params dict (as would come from DB)."""
    return {
        "r_squared": 0.92,
        "sample_count": 50,
        "updated_at": "2025-01-15T10:00:00",
        "coefficients": {
            "weights": [0.3, 0.02, -0.001, 0.5, 0.1],
            "intercept": 32.0,
            "scaling": {
                "mean": [300.0, 13.0, 500.0, 0.5, 240.0],
                "std": [100.0, 2.0, 200.0, 0.5, 80.0],
            },
        },
    }


# ---------------------------------------------------------------------------
# train_model
# ---------------------------------------------------------------------------


class TestTrainModel:
    async def test_returns_failure_when_no_training_data(self):
        svc = _make_service()
        svc._analiz_repo = _make_analiz_repo_mock(training_data=[])

        result = await svc.train_model(arac_id=1)

        assert result["success"] is False
        assert "error" in result

    async def test_returns_failure_when_all_zero_distance(self):
        svc = _make_service()
        bad_data = [{"mesafe_km": 0, "tuketim": 100, "ton": 13, "zorluk": "Normal"}]
        svc._analiz_repo = _make_analiz_repo_mock(training_data=bad_data)

        result = await svc.train_model(arac_id=1)

        assert result["success"] is False

    async def test_trains_successfully_with_valid_data(self):
        svc = _make_service()
        training_data = [
            {
                "mesafe_km": 450,
                "tuketim": 155,
                "ton": 13,
                "ascent_m": 500,
                "zorluk": "Normal",
                "flat_distance_km": 360,
            },
            {
                "mesafe_km": 300,
                "tuketim": 105,
                "ton": 10,
                "ascent_m": 200,
                "zorluk": "Orta",
                "flat_distance_km": 240,
            },
            {
                "mesafe_km": 600,
                "tuketim": 210,
                "ton": 15,
                "ascent_m": 700,
                "zorluk": "Zor",
                "flat_distance_km": 480,
            },
        ]
        mock_analiz = _make_analiz_repo_mock(training_data=training_data)
        svc._analiz_repo = mock_analiz

        result = await svc.train_model(arac_id=1)

        assert result["success"] is True
        assert "r_squared" in result
        mock_analiz.save_model_params.assert_called_once()

    async def test_uses_zorluk_map_correctly(self):
        """zorluk='Zor' should map to 2 in training features."""
        svc = _make_service()
        training_data = [
            {
                "mesafe_km": 300,
                "tuketim": 105,
                "ton": 13,
                "ascent_m": 300,
                "zorluk": "Zor",
                "flat_distance_km": 240,
            },
            {
                "mesafe_km": 300,
                "tuketim": 100,
                "ton": 13,
                "ascent_m": 300,
                "zorluk": "Normal",
                "flat_distance_km": 240,
            },
        ]
        mock_analiz = _make_analiz_repo_mock(training_data=training_data)
        svc._analiz_repo = mock_analiz

        result = await svc.train_model(arac_id=1)
        assert result["success"] is True

    async def test_does_not_save_params_on_failure(self):
        svc = _make_service()
        mock_analiz = _make_analiz_repo_mock(training_data=[])
        svc._analiz_repo = mock_analiz

        await svc.train_model(arac_id=1)

        mock_analiz.save_model_params.assert_not_called()


# ---------------------------------------------------------------------------
# predict — no model
# ---------------------------------------------------------------------------


class TestPredictNoModel:
    async def test_returns_failure_when_no_params(self):
        svc = _make_service()
        svc._analiz_repo = _make_analiz_repo_mock(params=None)

        result = await svc.predict(arac_id=1, mesafe_km=300, ton=13)

        assert result["success"] is False
        assert result.get("requires_training") is True


# ---------------------------------------------------------------------------
# predict — with model
# ---------------------------------------------------------------------------


class TestPredictWithModel:
    async def test_predict_success_no_sofor(self):
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        result = await svc.predict(
            arac_id=1, mesafe_km=300.0, ton=13.0, ascent_m=300.0, flat_distance_km=240.0
        )

        assert result["success"] is True
        assert result["tahmin_litre"] > 0
        assert "guven_araligi" in result
        assert result["sofor_faktor"] == 1.0

    async def test_predict_applies_lower_margin_for_sofor_below_avg(self):
        """sofor_faktor < 1 → margin_percent = 0.05."""
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        mock_stats = MagicMock()
        mock_stats.performans_puani = 80  # score > 50 → sofor_faktor < 1.0
        mock_analiz_svc = AsyncMock()
        mock_analiz_svc.get_driver_stats = AsyncMock(return_value=[mock_stats])

        mock_sofor_module = MagicMock()
        mock_sofor_module.get_sofor_analiz_service = MagicMock(
            return_value=mock_analiz_svc
        )

        with patch.dict(
            "sys.modules", {"app.core.services.sofor_analiz_service": mock_sofor_module}
        ):
            result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["success"] is True
        # sofor_faktor should be clamped to 0.9..1.1
        assert 0.9 <= result["sofor_faktor"] <= 1.1

    async def test_predict_applies_higher_margin_for_high_risk_sofor(self):
        """sofor_faktor > 1 → margin_percent = 0.08."""
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        mock_stats = MagicMock()
        mock_stats.performans_puani = 20  # score < 50 → sofor_faktor > 1.0
        mock_analiz_svc = AsyncMock()
        mock_analiz_svc.get_driver_stats = AsyncMock(return_value=[mock_stats])

        mock_sofor_module = MagicMock()
        mock_sofor_module.get_sofor_analiz_service = MagicMock(
            return_value=mock_analiz_svc
        )

        with patch.dict(
            "sys.modules", {"app.core.services.sofor_analiz_service": mock_sofor_module}
        ):
            result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["success"] is True
        assert result["sofor_faktor"] > 1.0

    async def test_predict_sofor_factor_defaults_to_1_when_no_stats(self):
        """Empty stats list → sofor_faktor = 1.0."""
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        mock_analiz_svc = AsyncMock()
        mock_analiz_svc.get_driver_stats = AsyncMock(return_value=[])

        mock_sofor_module = MagicMock()
        mock_sofor_module.get_sofor_analiz_service = MagicMock(
            return_value=mock_analiz_svc
        )

        with patch.dict(
            "sys.modules", {"app.core.services.sofor_analiz_service": mock_sofor_module}
        ):
            result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["sofor_faktor"] == 1.0

    async def test_predict_sofor_factor_defaults_to_1_on_none_score(self):
        """performans_puani = None → sofor_faktor = 1.0."""
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        mock_stats = MagicMock()
        mock_stats.performans_puani = None
        mock_analiz_svc = AsyncMock()
        mock_analiz_svc.get_driver_stats = AsyncMock(return_value=[mock_stats])

        mock_sofor_module = MagicMock()
        mock_sofor_module.get_sofor_analiz_service = MagicMock(
            return_value=mock_analiz_svc
        )

        with patch.dict(
            "sys.modules", {"app.core.services.sofor_analiz_service": mock_sofor_module}
        ):
            result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["sofor_faktor"] == 1.0

    async def test_predict_sofor_service_exception_caught(self):
        """Exception in driver factor calc falls back to 1.0."""
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        mock_sofor_module = MagicMock()
        mock_sofor_module.get_sofor_analiz_service = MagicMock(
            side_effect=Exception("sofor service down")
        )

        with patch.dict(
            "sys.modules", {"app.core.services.sofor_analiz_service": mock_sofor_module}
        ):
            result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["success"] is True
        assert result["sofor_faktor"] == 1.0

    async def test_predict_uses_scaling_from_top_level_params(self):
        """Params with top-level 'scaling' key (not inside coefficients) are loaded."""
        svc = _make_service()
        params = {
            "r_squared": 0.85,
            "sample_count": 30,
            "updated_at": "2025-01-01T00:00:00",
            "scaling": {
                "mean": [300.0, 13.0, 500.0, 0.5, 240.0],
                "std": [100.0, 2.0, 200.0, 0.5, 80.0],
            },
            "coefficients": {
                "weights": [0.3, 0.02, -0.001, 0.5, 0.1],
                "intercept": 32.0,
            },
        }
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0)

        assert result["success"] is True

    async def test_predict_all_difficulty_levels(self):
        """Ensure zorluk mapping works for all 3 levels."""
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        for zorluk in ["Normal", "Orta", "Zor"]:
            result = await svc.predict(
                arac_id=1, mesafe_km=300.0, ton=13.0, zorluk=zorluk
            )
            assert result["success"] is True, f"Failed for zorluk={zorluk}"

    async def test_tuketim_100km_calculation(self):
        svc = _make_service()
        params = _make_valid_params()
        svc._analiz_repo = _make_analiz_repo_mock(params=params)

        result = await svc.predict(arac_id=1, mesafe_km=300.0, ton=13.0)

        assert result["success"] is True
        expected = (result["tahmin_litre"] / 300.0) * 100
        assert abs(result["tahmin_tuketim_100km"] - expected) < 0.5


# ---------------------------------------------------------------------------
# lazy repo properties
# ---------------------------------------------------------------------------


class TestRepoProperties:
    def test_analiz_repo_lazy_loads(self):
        svc = _make_service()
        mock_repo = MagicMock()
        mock_analiz_module = MagicMock()
        mock_analiz_module.get_analiz_repo = MagicMock(return_value=mock_repo)

        with patch.dict(
            "sys.modules",
            {"app.database.repositories.analiz_repo": mock_analiz_module},
        ):
            # Reset cached value so property re-fetches
            svc._analiz_repo = None
            repo = svc.analiz_repo

        assert repo is mock_repo

    def test_analiz_repo_is_cached(self):
        svc = _make_service()
        mock_repo = MagicMock()
        mock_analiz_module = MagicMock()
        mock_analiz_module.get_analiz_repo = MagicMock(return_value=mock_repo)

        with patch.dict(
            "sys.modules",
            {"app.database.repositories.analiz_repo": mock_analiz_module},
        ):
            svc._analiz_repo = None
            r1 = svc.analiz_repo
            r2 = svc.analiz_repo  # second access uses cache

        assert r1 is r2
        # factory called once because cache was populated
        mock_analiz_module.get_analiz_repo.assert_called_once()

    def test_arac_repo_lazy_loads(self):
        svc = _make_service()
        mock_repo = MagicMock()
        mock_arac_module = MagicMock()
        mock_arac_module.get_arac_repo = MagicMock(return_value=mock_repo)

        with patch.dict(
            "sys.modules",
            {"v2.modules.fleet.infrastructure.vehicle_repository": mock_arac_module},
        ):
            svc._arac_repo = None
            repo = svc.arac_repo

        assert repo is mock_repo


# ---------------------------------------------------------------------------
# retrain_all_models
# ---------------------------------------------------------------------------


class TestRetrainAllModels:
    async def test_retrain_empty_fleet_returns_zero_success(self):
        svc = _make_service()
        svc._arac_repo = _make_arac_repo_mock(vehicles=[])
        svc._analiz_repo = _make_analiz_repo_mock()

        result = await svc.retrain_all_models()

        assert result["success"] == 0
        assert result["failed"] == 0

    async def test_retrain_single_vehicle_success(self):
        svc = _make_service()
        svc._arac_repo = _make_arac_repo_mock(
            vehicles=[{"id": 1, "plaka": "34TEST001"}]
        )
        training_data = [
            {
                "mesafe_km": 450,
                "tuketim": 155,
                "ton": 13,
                "ascent_m": 500,
                "zorluk": "Normal",
                "flat_distance_km": 360,
            },
            {
                "mesafe_km": 300,
                "tuketim": 105,
                "ton": 10,
                "ascent_m": 200,
                "zorluk": "Normal",
                "flat_distance_km": 240,
            },
        ]
        svc._analiz_repo = _make_analiz_repo_mock(training_data=training_data)

        result = await svc.retrain_all_models()

        assert result["success"] == 1
        assert result["failed"] == 0

    async def test_retrain_single_vehicle_failure(self):
        svc = _make_service()
        svc._arac_repo = _make_arac_repo_mock(
            vehicles=[{"id": 1, "plaka": "34FAIL001"}]
        )
        svc._analiz_repo = _make_analiz_repo_mock(training_data=[])

        result = await svc.retrain_all_models()

        assert result["failed"] == 1
        assert result["success"] == 0

    async def test_retrain_details_contains_plaka(self):
        svc = _make_service()
        svc._arac_repo = _make_arac_repo_mock(
            vehicles=[{"id": 1, "plaka": "34DETAIL001"}]
        )
        svc._analiz_repo = _make_analiz_repo_mock(training_data=[])

        result = await svc.retrain_all_models()

        assert any("34DETAIL001" in d for d in result["details"])
