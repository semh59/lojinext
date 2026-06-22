"""Predictions endpoint integration tests - real code execution."""

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.integration
async def test_predict_fuel_consumption_full_flow(
    async_client, admin_auth_headers, db_session
):
    """Test full fuel prediction flow with real service execution."""
    # Create test data
    from datetime import date

    from sqlalchemy import insert

    from app.database.models import Arac, Sefer, Sofor

    # Create vehicle
    arac_result = await db_session.execute(
        insert(Arac).values(
            plaka="99 TEST 001",
            marka="Test",
            model="Model",
            yil=2020,
            aktif=True,
            bos_agirlik_kg=5000.0,
        )
    )
    arac_id = arac_result.inserted_primary_key[0]

    # Create driver
    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Test Driver",
            telefon="0532 000 00 01",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=1.0,
            manual_score=1.0,
            hiz_disiplin_skoru=1.0,
            agresif_surus_faktoru=1.0,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]

    # Create trip for prediction context
    sefer_result = await db_session.execute(
        insert(Sefer).values(
            arac_id=arac_id,
            sofor_id=sofor_id,
            tarih=date.today(),
            cikis_yeri="Istanbul",
            varis_yeri="Ankara",
            mesafe_km=450.0,
            durum="Planned",
            tuketim=None,
            bos_agirlik_kg=5000,
            dolu_agirlik_kg=15000,
            net_kg=10000,
            flat_distance_km=450.0,
        )
    )
    sefer_id = sefer_result.inserted_primary_key[0]
    await db_session.commit()

    # Test prediction request — real endpoint is POST /predictions/predict with a
    # PredictionRequest body (arac_id/mesafe_km/ton), not /predictions/fuel.
    _ = sefer_id  # trip created above for context; predict uses arac/mesafe/ton
    response = await async_client.post(
        "/api/v1/predictions/predict",
        json={
            "arac_id": arac_id,
            "mesafe_km": 450.0,
            "ton": 10.0,
            "sofor_id": sofor_id,
        },
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "predicted_consumption" in data or "error" not in str(response.text)


@pytest.mark.integration
async def test_coaching_insights_real_flow(
    async_client, admin_auth_headers, db_session
):
    """Test coaching insights with real driver data."""
    from datetime import date

    from sqlalchemy import insert

    from app.database.models import Sofor

    # Create driver for coaching analysis
    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Coaching Test Driver",
            telefon="0532 111 11 11",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=0.75,
            manual_score=0.75,
            hiz_disiplin_skoru=0.70,
            agresif_surus_faktoru=0.65,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    # Get coaching insights
    response = await async_client.get(
        f"/api/v1/coaching/driver/{sofor_id}/insights",
        headers=admin_auth_headers,
    )

    # Should return insights or 404 if endpoint exists
    assert response.status_code in [200, 404]


@pytest.mark.integration
async def test_explain_prediction_with_real_models(async_client, admin_auth_headers):
    """Test prediction explanation with real ML models."""
    response = await async_client.post(
        "/api/v1/predictions/explain",
        json={"sefer_id": 1, "feature_count": 10},
        headers=admin_auth_headers,
    )

    # Should work or gracefully handle missing data
    assert response.status_code in [200, 404, 422]


@pytest.mark.skip(
    reason="No /predictions/batch endpoint exists; GET /{task_id} catches the path "
    "and 405s POST. Re-enable if a batch endpoint is added."
)
@pytest.mark.integration
async def test_batch_predictions(async_client, admin_auth_headers):
    """Test batch prediction processing."""
    response = await async_client.post(
        "/api/v1/predictions/batch",
        json={
            "sefer_ids": [1, 2, 3],
            "include_confidence": True,
        },
        headers=admin_auth_headers,
    )

    # Should handle batch requests
    assert response.status_code in [200, 400, 422]


@pytest.mark.integration
async def test_coaching_recommendations(async_client, admin_auth_headers, db_session):
    """Test coaching recommendations generation."""
    from datetime import date

    from sqlalchemy import insert

    from app.database.models import Sofor

    # Create low-score driver
    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Poor Driver",
            telefon="0532 222 22 22",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=0.5,
            manual_score=0.5,
            hiz_disiplin_skoru=0.4,
            agresif_surus_faktoru=0.3,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/coaching/driver/{sofor_id}/recommendations",
        json={"focus_areas": ["speed_discipline", "fuel_efficiency"]},
        headers=admin_auth_headers,
    )

    assert response.status_code in [200, 404]
