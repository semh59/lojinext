"""Integration tests for admin ML endpoint — /api/v1/admin/ml/"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

BASE = "/api/v1/admin/ml"


# ---------------------------------------------------------------------------
# GET /api/v1/admin/ml/queue — training queue (status-like endpoint)
# ---------------------------------------------------------------------------


async def test_ml_queue_admin_gets_200(async_client, admin_auth_headers):
    """Admin can retrieve the ML training queue and gets 200 with a list."""
    response = await async_client.get(f"{BASE}/queue", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


async def test_ml_queue_normal_user_gets_403(async_client, normal_auth_headers):
    """Normal user (lacking model_goruntule permission) is rejected with 403."""
    response = await async_client.get(f"{BASE}/queue", headers=normal_auth_headers)
    assert response.status_code == 403, response.text


async def test_ml_queue_no_auth_gets_401(async_client):
    """Unauthenticated request is rejected with 401."""
    response = await async_client.get(f"{BASE}/queue")
    assert response.status_code == 401, response.text


async def test_ml_queue_rejects_huge_limit(async_client, admin_auth_headers):
    """2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 20): `limit` üst
    sınırı yoktu — `?limit=999999999` tüm tabloyu OOM riskiyle çekebilirdi."""
    response = await async_client.get(
        f"{BASE}/queue?limit=999999999", headers=admin_auth_headers
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/admin/ml/train/{arac_id} — trigger training
# ---------------------------------------------------------------------------


async def test_ml_train_admin_gets_200_or_202(
    async_client, admin_auth_headers, db_session
):
    """
    Admin can trigger ML training for a vehicle.
    The response is 200 or 202 (accepted); the actual training is async.
    MLService.schedule_training is mocked so no real ML work occurs.
    """
    from datetime import datetime, timezone

    from app.schemas.ml_schemas import MLTaskRead

    fake_task = MLTaskRead(
        id=1,
        arac_id=1,
        durum="beklemede",
        hedef_versiyon=1,
        ilerleme=0.0,
        baslangic_zaman=None,
        bitis_zaman=None,
        hata_detay=None,
        tetikleyen_kullanici_id=None,
        olusturma_tarihi=datetime.now(timezone.utc),
    )

    with patch(
        "app.core.services.ml_service.MLService.schedule_training",
        new=AsyncMock(return_value=fake_task),
    ):
        response = await async_client.post(
            f"{BASE}/train/1", headers=admin_auth_headers
        )

    assert response.status_code in (
        200,
        202,
    ), f"Expected 200 or 202, got {response.status_code}: {response.text}"
    body = response.json()
    assert "arac_id" in body or "id" in body


async def test_ml_train_normal_user_gets_403(async_client, normal_auth_headers):
    """Normal user (lacking model_egit permission) gets 403."""
    response = await async_client.post(f"{BASE}/train/1", headers=normal_auth_headers)
    assert response.status_code == 403, response.text


async def test_ml_train_no_auth_gets_401(async_client):
    """Unauthenticated request is rejected with 401."""
    response = await async_client.post(f"{BASE}/train/1")
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# GET /api/v1/admin/ml/versions/{arac_id} — model versions
# ---------------------------------------------------------------------------


async def test_ml_versions_admin_gets_200(async_client, admin_auth_headers):
    """Admin can list model versions for a vehicle (may be an empty list)."""
    response = await async_client.get(f"{BASE}/versions/1", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


async def test_ml_versions_normal_user_gets_403(async_client, normal_auth_headers):
    """Normal user (lacking model_goruntule permission) is rejected with 403."""
    response = await async_client.get(f"{BASE}/versions/1", headers=normal_auth_headers)
    assert response.status_code == 403, response.text
