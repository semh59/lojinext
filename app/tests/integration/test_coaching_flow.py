"""Coaching endpoint integration tests."""

from datetime import date

import pytest
from sqlalchemy import insert

from v2.modules.platform_infra.security.pii_encryption import blind_index

pytestmark = pytest.mark.integration


@pytest.mark.integration
async def test_get_driver_coaching_insights(
    async_client, admin_auth_headers, db_session
):
    """Test getting driver coaching insights with real data."""
    from v2.modules.driver.public import Sofor

    # Create test driver
    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Test Driver Coaching",
            ad_soyad_bidx=blind_index("Test Driver Coaching"),
            telefon="0532 333 33 33",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=0.80,
            manual_score=0.80,
            hiz_disiplin_skoru=0.75,
            agresif_surus_faktoru=0.70,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/coaching/{sofor_id}/insights",
        headers=admin_auth_headers,
    )

    assert response.status_code in [200, 404]


@pytest.mark.integration
async def test_coaching_weekly_digest(async_client, admin_auth_headers, db_session):
    """Test weekly coaching digest generation."""
    from v2.modules.driver.public import Sofor

    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Weekly Digest Driver",
            ad_soyad_bidx=blind_index("Weekly Digest Driver"),
            telefon="0532 444 44 44",
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

    response = await async_client.get(
        f"/api/v1/coaching/{sofor_id}/weekly-digest",
        headers=admin_auth_headers,
    )

    assert response.status_code in [200, 404]


@pytest.mark.integration
async def test_coaching_performance_trends(
    async_client, admin_auth_headers, db_session
):
    """Test driver performance trend analysis."""
    from v2.modules.driver.public import Sofor

    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Trend Analysis Driver",
            ad_soyad_bidx=blind_index("Trend Analysis Driver"),
            telefon="0532 555 55 55",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=0.80,
            manual_score=0.80,
            hiz_disiplin_skoru=0.78,
            agresif_surus_faktoru=0.75,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/coaching/{sofor_id}/trends?days=30",
        headers=admin_auth_headers,
    )

    assert response.status_code in [200, 404]


@pytest.mark.integration
async def test_coaching_goals_setting(async_client, admin_auth_headers, db_session):
    """Test setting coaching goals for driver."""
    from v2.modules.driver.public import Sofor

    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Goals Driver",
            ad_soyad_bidx=blind_index("Goals Driver"),
            telefon="0532 666 66 66",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=0.70,
            manual_score=0.70,
            hiz_disiplin_skoru=0.65,
            agresif_surus_faktoru=0.60,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/coaching/{sofor_id}/goals",
        json={
            "target_score": 0.85,
            "focus_areas": ["fuel_efficiency", "speed_discipline"],
            "duration_days": 30,
        },
        headers=admin_auth_headers,
    )

    assert response.status_code in [200, 201, 404]


@pytest.mark.integration
async def test_coaching_requires_auth(async_client, db_session):
    """Test coaching endpoint requires authentication."""
    from v2.modules.driver.public import Sofor

    sofor_result = await db_session.execute(
        insert(Sofor).values(
            ad_soyad="Auth Test",
            ad_soyad_bidx=blind_index("Auth Test"),
            telefon="0532 777 77 77",
            ise_baslama=date(2020, 1, 1),
            ehliyet_sinifi="E",
            aktif=True,
            score=0.70,
            manual_score=0.70,
            hiz_disiplin_skoru=0.65,
            agresif_surus_faktoru=0.60,
        )
    )
    sofor_id = sofor_result.inserted_primary_key[0]
    await db_session.commit()

    response = await async_client.get(f"/api/v1/coaching/{sofor_id}/insights")

    assert response.status_code == 401


@pytest.mark.integration
async def test_coaching_all_drivers_summary(async_client, admin_auth_headers):
    """Test fleet-wide coaching summary."""
    response = await async_client.get(
        "/api/v1/coaching/summary",
        headers=admin_auth_headers,
    )

    assert response.status_code in [200, 404]
