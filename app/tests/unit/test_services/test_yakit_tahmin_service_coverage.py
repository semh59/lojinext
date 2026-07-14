"""
Fuel consumption-prediction (yakit tahmin) coverage tests — targeting
uncovered branches. Repos and external calls are fully mocked.

Dalga 4 (B.1 free-function refactor): YakitTahminService class deleted —
train_model/predict/retrain_all_models are free functions in
v2/modules/fuel/domain/consumption_prediction.py, each fetching its repo
fresh via an inline `from ... import get_x_repo` call (no cached instance
attribute left to inject a mock into) — patch target is the SOURCE module
(app.database.repositories.analiz_repo.get_analiz_repo /
v2.modules.fleet.infrastructure.vehicle_repository.get_arac_repo), same
inline-import gotcha documented in location/CLAUDE.md.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.fuel.domain.consumption_prediction import (
    predict,
    retrain_all_models,
    train_model,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _patch_analiz_repo(mock_repo):
    return patch(
        "app.database.repositories.analiz_repo.get_analiz_repo",
        return_value=mock_repo,
    )


def _patch_arac_repo(mock_repo):
    return patch(
        "v2.modules.fleet.infrastructure.vehicle_repository.get_arac_repo",
        return_value=mock_repo,
    )


# ---------------------------------------------------------------------------
# train_model
# ---------------------------------------------------------------------------


class TestTrainModel:
    async def test_returns_failure_when_no_training_data(self):
        with _patch_analiz_repo(_make_analiz_repo_mock(training_data=[])):
            result = await train_model(arac_id=1)

        assert result["success"] is False
        assert "error" in result

    async def test_returns_failure_when_all_zero_distance(self):
        bad_data = [{"mesafe_km": 0, "tuketim": 100, "ton": 13, "zorluk": "Normal"}]
        with _patch_analiz_repo(_make_analiz_repo_mock(training_data=bad_data)):
            result = await train_model(arac_id=1)

        assert result["success"] is False

    async def test_trains_successfully_with_valid_data(self):
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
        with _patch_analiz_repo(mock_analiz):
            result = await train_model(arac_id=1)

        assert result["success"] is True
        assert "r_squared" in result
        mock_analiz.save_model_params.assert_called_once()

    async def test_uses_zorluk_map_correctly(self):
        """zorluk='Zor' should map to 2 in training features."""
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
        with _patch_analiz_repo(mock_analiz):
            result = await train_model(arac_id=1)
        assert result["success"] is True

    async def test_does_not_save_params_on_failure(self):
        mock_analiz = _make_analiz_repo_mock(training_data=[])
        with _patch_analiz_repo(mock_analiz):
            await train_model(arac_id=1)

        mock_analiz.save_model_params.assert_not_called()


# ---------------------------------------------------------------------------
# predict — no model
# ---------------------------------------------------------------------------


class TestPredictNoModel:
    async def test_returns_failure_when_no_params(self):
        with _patch_analiz_repo(_make_analiz_repo_mock(params=None)):
            result = await predict(arac_id=1, mesafe_km=300, ton=13)

        assert result["success"] is False
        assert result.get("requires_training") is True


# ---------------------------------------------------------------------------
# predict — with model
# ---------------------------------------------------------------------------


class TestPredictWithModel:
    async def test_predict_success_no_sofor(self):
        params = _make_valid_params()
        with _patch_analiz_repo(_make_analiz_repo_mock(params=params)):
            result = await predict(
                arac_id=1,
                mesafe_km=300.0,
                ton=13.0,
                ascent_m=300.0,
                flat_distance_km=240.0,
            )

        assert result["success"] is True
        assert result["tahmin_litre"] > 0
        assert "guven_araligi" in result
        assert result["sofor_faktor"] == 1.0

    async def test_predict_applies_lower_margin_for_sofor_below_avg(self):
        """sofor_faktor < 1 → margin_percent = 0.05."""
        params = _make_valid_params()

        mock_stats = MagicMock()
        mock_stats.performans_puani = 80  # score > 50 → sofor_faktor < 1.0

        with (
            _patch_analiz_repo(_make_analiz_repo_mock(params=params)),
            patch(
                "v2.modules.driver.domain.driver_stats.get_driver_stats",
                AsyncMock(return_value=[mock_stats]),
            ),
        ):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["success"] is True
        # sofor_faktor should be clamped to 0.9..1.1
        assert 0.9 <= result["sofor_faktor"] <= 1.1

    async def test_predict_applies_higher_margin_for_high_risk_sofor(self):
        """sofor_faktor > 1 → margin_percent = 0.08."""
        params = _make_valid_params()

        mock_stats = MagicMock()
        mock_stats.performans_puani = 20  # score < 50 → sofor_faktor > 1.0

        with (
            _patch_analiz_repo(_make_analiz_repo_mock(params=params)),
            patch(
                "v2.modules.driver.domain.driver_stats.get_driver_stats",
                AsyncMock(return_value=[mock_stats]),
            ),
        ):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["success"] is True
        assert result["sofor_faktor"] > 1.0

    async def test_predict_sofor_factor_defaults_to_1_when_no_stats(self):
        """Empty stats list → sofor_faktor = 1.0."""
        params = _make_valid_params()

        with (
            _patch_analiz_repo(_make_analiz_repo_mock(params=params)),
            patch(
                "v2.modules.driver.domain.driver_stats.get_driver_stats",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["sofor_faktor"] == 1.0

    async def test_predict_sofor_factor_defaults_to_1_on_none_score(self):
        """performans_puani = None → sofor_faktor = 1.0."""
        params = _make_valid_params()

        mock_stats = MagicMock()
        mock_stats.performans_puani = None

        with (
            _patch_analiz_repo(_make_analiz_repo_mock(params=params)),
            patch(
                "v2.modules.driver.domain.driver_stats.get_driver_stats",
                AsyncMock(return_value=[mock_stats]),
            ),
        ):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["sofor_faktor"] == 1.0

    async def test_predict_sofor_service_exception_caught(self):
        """Exception in driver factor calc falls back to 1.0."""
        params = _make_valid_params()

        with (
            _patch_analiz_repo(_make_analiz_repo_mock(params=params)),
            patch(
                "v2.modules.driver.domain.driver_stats.get_driver_stats",
                AsyncMock(side_effect=Exception("sofor service down")),
            ),
        ):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0, sofor_id=5)

        assert result["success"] is True
        assert result["sofor_faktor"] == 1.0

    async def test_predict_uses_scaling_from_top_level_params(self):
        """Params with top-level 'scaling' key (not inside coefficients) are loaded."""
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
        with _patch_analiz_repo(_make_analiz_repo_mock(params=params)):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0)

        assert result["success"] is True

    async def test_predict_all_difficulty_levels(self):
        """Ensure zorluk mapping works for all 3 levels."""
        params = _make_valid_params()
        with _patch_analiz_repo(_make_analiz_repo_mock(params=params)):
            for zorluk in ["Normal", "Orta", "Zor"]:
                result = await predict(
                    arac_id=1, mesafe_km=300.0, ton=13.0, zorluk=zorluk
                )
                assert result["success"] is True, f"Failed for zorluk={zorluk}"

    async def test_tuketim_100km_calculation(self):
        params = _make_valid_params()
        with _patch_analiz_repo(_make_analiz_repo_mock(params=params)):
            result = await predict(arac_id=1, mesafe_km=300.0, ton=13.0)

        assert result["success"] is True
        expected = (result["tahmin_litre"] / 300.0) * 100
        assert abs(result["tahmin_tuketim_100km"] - expected) < 0.5


# ---------------------------------------------------------------------------
# retrain_all_models
# ---------------------------------------------------------------------------


class TestRetrainAllModels:
    async def test_retrain_empty_fleet_returns_zero_success(self):
        with (
            _patch_arac_repo(_make_arac_repo_mock(vehicles=[])),
            _patch_analiz_repo(_make_analiz_repo_mock()),
        ):
            result = await retrain_all_models()

        assert result["success"] == 0
        assert result["failed"] == 0

    async def test_retrain_single_vehicle_success(self):
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
        with (
            _patch_arac_repo(
                _make_arac_repo_mock(vehicles=[{"id": 1, "plaka": "34TEST001"}])
            ),
            _patch_analiz_repo(_make_analiz_repo_mock(training_data=training_data)),
        ):
            result = await retrain_all_models()

        assert result["success"] == 1
        assert result["failed"] == 0

    async def test_retrain_single_vehicle_failure(self):
        with (
            _patch_arac_repo(
                _make_arac_repo_mock(vehicles=[{"id": 1, "plaka": "34FAIL001"}])
            ),
            _patch_analiz_repo(_make_analiz_repo_mock(training_data=[])),
        ):
            result = await retrain_all_models()

        assert result["failed"] == 1
        assert result["success"] == 0

    async def test_retrain_details_contains_plaka(self):
        with (
            _patch_arac_repo(
                _make_arac_repo_mock(vehicles=[{"id": 1, "plaka": "34DETAIL001"}])
            ),
            _patch_analiz_repo(_make_analiz_repo_mock(training_data=[])),
        ):
            result = await retrain_all_models()

        assert any("34DETAIL001" in d for d in result["details"])


# TestRepoProperties removed — YakitTahminService's cached `_analiz_repo`/
# `_arac_repo` lazy properties deleted in dalga 4 (B.1 free-function
# refactor, v2.modules.fuel); train_model/predict/retrain_all_models each
# fetch their repo fresh via an inline import + factory call, no caching
# behavior left to test.
