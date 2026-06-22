"""Predictions endpoint tests."""

import pytest


@pytest.mark.asyncio
async def test_predict_fuel_consumption_success(
    async_client, admin_auth_headers, monkeypatch
):
    """Test fuel consumption prediction → 200.

    The endpoint is POST /predictions/predict (not /predictions/fuel).
    PredictionService is instantiated inline; patch its predict_consumption method.
    """
    from app.services import prediction_service as pred_svc_mod

    async def _fake_predict(self, **kwargs):
        return {
            "status": "success",
            "tahmini_tuketim": 45.2,
            "model_used": "ensemble",
            "arac_id": 1,
            "mesafe_km": 450,
        }

    monkeypatch.setattr(
        pred_svc_mod.PredictionService, "predict_consumption", _fake_predict
    )

    response = await async_client.post(
        "/api/v1/predictions/predict",
        json={"arac_id": 1, "mesafe_km": 450.0, "ton": 5.0},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "tahmini_tuketim" in data


@pytest.mark.asyncio
async def test_predict_fuel_invalid_input(async_client, admin_auth_headers):
    """Test fuel prediction with invalid input → 422 (missing required fields)."""
    response = await async_client.post(
        "/api/v1/predictions/predict",
        json={"sefer_id": "invalid"},
        headers=admin_auth_headers,
    )
    # Missing required arac_id + mesafe_km → 422
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_explain_prediction_success(
    async_client, admin_auth_headers, monkeypatch
):
    """Test prediction explanation → 200.

    The endpoint is POST /predictions/explain and takes a PredictionRequest body.
    """
    from app.services import prediction_service as pred_svc_mod

    async def _fake_explain(self, **kwargs):
        return {
            "features": [
                {"name": "distance_km", "importance": 0.35},
                {"name": "vehicle_age", "importance": 0.25},
                {"name": "weather", "importance": 0.20},
            ]
        }

    monkeypatch.setattr(
        pred_svc_mod.PredictionService, "explain_consumption", _fake_explain
    )

    response = await async_client.post(
        "/api/v1/predictions/explain",
        json={"arac_id": 1, "mesafe_km": 450.0},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "features" in data


@pytest.mark.asyncio
async def test_predict_requires_auth(async_client):
    """Test prediction endpoint requires authentication → 401."""
    response = await async_client.post(
        "/api/v1/predictions/predict",
        json={"arac_id": 1, "mesafe_km": 450.0},
    )
    assert response.status_code == 401
