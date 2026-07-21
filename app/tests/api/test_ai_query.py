"""POST /ai/query testleri."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_general_category_returns_answer(async_client, normal_auth_headers):
    with patch("v2.modules.ai_assistant.api.ai_routes.get_ai_service") as mock_ai:
        mock_ai.return_value.generate_response = AsyncMock(return_value="Merhaba!")
        resp = await async_client.post(
            "/api/v1/ai/query",
            json={"message": "selam", "category": "general"},
            headers=normal_auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Merhaba!"
    assert body["chart"] is None


async def test_fuel_trend_returns_chart_and_action(
    async_client, admin_auth_headers, db_session
):
    from datetime import date

    from app.database.models import YakitAlimi
    from v2.modules.fleet.public import AracORM as Arac

    arac = Arac(
        plaka="34AI001",
        marka="M",
        model="A",
        yil=2022,
        tank_kapasitesi=600,
        hedef_tuketim=30.0,
        aktif=True,
        bos_agirlik_kg=8000,
    )
    db_session.add(arac)
    await db_session.commit()
    await db_session.refresh(arac)
    db_session.add_all(
        [
            YakitAlimi(
                arac_id=arac.id,
                tarih=date(2026, 1, 15),
                litre=100,
                toplam_tutar=4000,
                fiyat_tl=40,
                km_sayac=1000,
            ),
            YakitAlimi(
                arac_id=arac.id,
                tarih=date(2026, 2, 15),
                litre=120,
                toplam_tutar=5000,
                fiyat_tl=41.6,
                km_sayac=2000,
            ),
        ]
    )
    await db_session.commit()

    with patch("v2.modules.ai_assistant.api.ai_routes.get_ai_service") as mock_ai:
        mock_ai.return_value.generate_response = AsyncMock(return_value="Trend yukarı.")
        resp = await async_client.post(
            "/api/v1/ai/query",
            json={"message": "yakıt trendi", "category": "fuel_trend"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chart"] is not None
    assert body["chart"]["type"] == "line"
    assert len(body["chart"]["data"]) >= 2
    assert any(a["url"] == "/fuel" for a in body["actions"])


async def test_query_requires_auth(async_client):
    resp = await async_client.post(
        "/api/v1/ai/query", json={"message": "x", "category": "general"}
    )
    assert resp.status_code == 401


async def test_fuel_trend_llm_failure_still_returns_chart(
    async_client, admin_auth_headers
):
    with patch("v2.modules.ai_assistant.api.ai_routes.get_ai_service") as mock_ai:
        mock_ai.return_value.generate_response = AsyncMock(
            side_effect=RuntimeError("groq down")
        )
        resp = await async_client.post(
            "/api/v1/ai/query",
            json={"message": "yakıt", "category": "fuel_trend"},
            headers=admin_auth_headers,
        )
    assert resp.status_code == 200
    assert "actions" in resp.json()
