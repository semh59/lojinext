"""
Layer 6 — ML/AI Pipeline
Verifies ML and AI subsystems behave correctly at the API and service boundary.
All tests require Docker stack (real DB + Redis + Celery not required for these).
"""

import math

import pytest

pytestmark = pytest.mark.integration


def _is_finite_positive(v) -> bool:
    try:
        return math.isfinite(float(v)) and float(v) > 0
    except (TypeError, ValueError):
        return False


# ── Ensemble predictor cold-start invariant ──────────────────────────────────


@pytest.mark.asyncio
async def test_prediction_physics_model_works_without_training_data(
    async_client, admin_auth_headers
):
    """
    POST /predictions/predict with a valid request must not 500.
    When no trained model exists, the physics fallback must produce
    tahmini_tuketim > 0 with model_used in known values.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 450.0,
            "ton": 22.0,
            "ascent_m": 200.0,
            "descent_m": 200.0,
            "flat_distance_km": 400.0,
            "zorluk": "Normal",
            "model_type": "ensemble",
        },
        headers=admin_auth_headers,
    )

    assert r.status_code != 500, f"Prediction endpoint 500'd: {r.text}"
    assert r.status_code in (
        200,
        404,
        422,
    ), f"Unexpected status {r.status_code}: {r.text}"

    if r.status_code == 200:
        body = r.json()
        assert body["status"] == "success", f"status != success: {body}"
        assert _is_finite_positive(body["tahmini_tuketim"]), (
            f"tahmini_tuketim not finite positive: {body['tahmini_tuketim']}"
        )
        known_models = {"linear", "xgboost", "ensemble", "physics", "physics_fallback"}
        assert body["model_used"] in known_models, (
            f"model_used '{body['model_used']}' not in known set {known_models}"
        )


@pytest.mark.asyncio
async def test_prediction_confidence_bounds_are_ordered(
    async_client, admin_auth_headers
):
    """
    When confidence_low and confidence_high are present in the prediction response,
    confidence_low < tahmini_tuketim < confidence_high must hold.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 300.0,
            "ton": 18.0,
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "flat_distance_km": 300.0,
            "zorluk": "Normal",
            "model_type": "ensemble",
        },
        headers=admin_auth_headers,
    )

    if r.status_code != 200:
        pytest.skip("Prediction returned non-200; skipping confidence bound check")

    body = r.json()
    low = body.get("confidence_low")
    high = body.get("confidence_high")
    value = float(body["tahmini_tuketim"])

    if low is not None and high is not None:
        assert float(low) < value, (
            f"confidence_low ({low}) must be < tahmini_tuketim ({value})"
        )
        assert float(high) > value, (
            f"confidence_high ({high}) must be > tahmini_tuketim ({value})"
        )
        assert float(low) > 0, "confidence_low must be positive"


# ── AI chat endpoint ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_chat_returns_response_field(async_client, admin_auth_headers):
    """
    POST /ai/chat must return {"response": str, "timestamp": str}.
    Must not 500 regardless of Groq availability.
    """
    r = await async_client.post(
        "/api/v1/ai/chat",
        json={"message": "Yakıt anomalisi nedir?", "history": []},
        headers=admin_auth_headers,
    )

    assert r.status_code != 500, f"AI chat 500'd: {r.text}"
    assert r.status_code in (
        200,
        503,
    ), f"Unexpected AI chat status {r.status_code}: {r.text}"

    if r.status_code == 200:
        body = r.json()
        assert "response" in body, f"'response' field missing: {list(body.keys())}"
        assert isinstance(body["response"], str), (
            f"'response' must be a string, got {type(body['response'])}"
        )
        assert len(body["response"]) > 0, "AI response must not be empty"
        assert "timestamp" in body, "'timestamp' field missing"


@pytest.mark.asyncio
async def test_ai_chat_with_invalid_groq_key_does_not_500(
    async_client, admin_auth_headers, monkeypatch
):
    """
    When Groq API is unavailable (invalid key), AI chat must return a
    graceful error response — never an unhandled 500.
    """
    monkeypatch.setenv("GROQ_API_KEY", "invalid_key_for_test")

    r = await async_client.post(
        "/api/v1/ai/chat",
        json={"message": "Test query with invalid LLM key"},
        headers=admin_auth_headers,
    )

    assert r.status_code != 500, (
        "AI chat must handle LLM failures gracefully — never 500 without envelope. "
        f"Got 500: {r.text[:300]}"
    )


@pytest.mark.asyncio
async def test_ai_chat_rejects_oversized_message(async_client, admin_auth_headers):
    """2026-07-02 prod-grade denetimi P1 (Tier A madde 1): `ChatRequest.message`
    hiçbir uzunluk sınırına sahip değildi — MB boyutunda bir mesaj doğrudan
    LLM context'ine gidebiliyordu (maliyet/DoS). Artık 422 ile reddedilmeli."""
    oversized_message = "a" * 100_000
    r = await async_client.post(
        "/api/v1/ai/chat",
        json={"message": oversized_message, "history": []},
        headers=admin_auth_headers,
    )
    assert r.status_code == 422, (
        f"Aşırı büyük mesaj (100000 karakter) 422 ile reddedilmeliydi, "
        f"{r.status_code} döndü: {r.text[:300]}"
    )


# ── Anomaly fleet insights ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anomaly_fleet_insights_response_shape(async_client, admin_auth_headers):
    """
    GET /anomalies/fleet/insights must return status=success and data dict.
    Must not 500.
    """
    r = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=30",
        headers=admin_auth_headers,
    )
    assert r.status_code == 200, f"Fleet insights failed: {r.text}"
    body = r.json()
    assert body.get("status") == "success", f"Expected status='success': {body}"
    assert "data" in body, f"'data' key missing from fleet insights: {body}"


@pytest.mark.asyncio
async def test_anomaly_fleet_insights_leakage_and_maintenance_keys(
    async_client, admin_auth_headers
):
    """
    Fleet insights data must have 'leakage' and 'maintenance' sub-keys.
    Both must be non-None (list or dict).
    """
    r = await async_client.get(
        "/api/v1/anomalies/fleet/insights?days=30",
        headers=admin_auth_headers,
    )
    assert r.status_code == 200
    data = r.json().get("data", {})
    assert "leakage" in data, f"'leakage' key missing: {data}"
    assert "maintenance" in data, f"'maintenance' key missing: {data}"
    assert data["leakage"] is not None, "'leakage' must not be None"
    assert data["maintenance"] is not None, "'maintenance' must not be None"


# ── ML training queue (admin) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ml_training_queue_returns_list(async_client, admin_auth_headers):
    """
    GET /admin/ml/queue must return a list (possibly empty).
    Verifies the ML admin endpoint is reachable with correct permissions.
    """
    r = await async_client.get(
        "/api/v1/admin/ml/queue",
        headers=admin_auth_headers,
    )
    assert r.status_code == 200, f"ML training queue failed: {r.status_code} {r.text}"
    body = r.json()
    assert isinstance(body, list), f"ML queue must return a list: {type(body)}"


# ── Prediction with extreme values doesn't 500 ────────────────────────────────


@pytest.mark.asyncio
async def test_prediction_extreme_values_no_500(async_client, admin_auth_headers):
    """
    Prediction with edge-case inputs (very high ascent, max ton) must not 500.
    Physics model must handle any valid numeric input.
    """
    r = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": 1,
            "mesafe_km": 9999.0,
            "ton": 26.0,
            "ascent_m": 49999.0,
            "descent_m": 49999.0,
            "flat_distance_km": 1.0,
            "zorluk": "Zor",
            "model_type": "physics",
        },
        headers=admin_auth_headers,
    )
    assert r.status_code != 500, (
        f"Prediction with extreme inputs must not 500. Got: {r.text}"
    )
    if r.status_code == 200:
        assert _is_finite_positive(r.json()["tahmini_tuketim"]), (
            "tahmini_tuketim must be finite even for extreme inputs"
        )
