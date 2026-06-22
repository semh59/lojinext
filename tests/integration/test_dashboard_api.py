import pytest
from starlette.websockets import WebSocketDisconnect


@pytest.mark.asyncio
async def test_get_dashboard_stats_unauthorized(async_client):
    """Auth olmadan erişim 401 dönmeli"""
    response = await async_client.get("/api/v1/reports/dashboard")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_stats_success(async_client, async_superuser_token_headers):
    """Admin ile erişim başarılı olmalı"""
    response = await async_client.get(
        "/api/v1/reports/dashboard", headers=async_superuser_token_headers
    )
    assert response.status_code == 200

    data = response.json()
    assert "toplam_sefer" in data
    assert "filo_ortalama" in data
    # Standard response has 'trends' or similar
    assert "data" in data or "trends" in data


@pytest.mark.asyncio
async def test_get_dashboard_stats_structure(
    async_client, async_superuser_token_headers
):
    """Response yapısı doğru olmalı"""
    response = await async_client.get(
        "/api/v1/reports/dashboard", headers=async_superuser_token_headers
    )
    data = response.json()

    # Map to DashboardStatsResponse fields
    if "data" in data:
        data = data["data"]

    expected_keys = {
        "toplam_sefer",
        "toplam_km",
        "toplam_yakit",
        "filo_ortalama",
    }
    assert expected_keys.issubset(data.keys())


@pytest.mark.asyncio
async def test_consumption_trend_unauthorized(async_client):
    """Auth olmadan erişim 401 dönmeli"""
    response = await async_client.get("/api/v1/reports/consumption-trend")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_consumption_trend_success(async_client, async_superuser_token_headers):
    """Admin ile erişim başarılı olmalı, liste formatında dönmeli"""
    response = await async_client.get(
        "/api/v1/reports/consumption-trend", headers=async_superuser_token_headers
    )
    assert response.status_code == 200

    data = response.json()
    if "data" in data:
        data = data["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_consumption_trend_item_structure(
    async_client, async_superuser_token_headers
):
    """Her item month ve consumption alanları içermeli"""
    response = await async_client.get(
        "/api/v1/reports/consumption-trend", headers=async_superuser_token_headers
    )
    data = response.json()
    if "data" in data:
        data = data["data"]

    if len(data) > 0:
        item = data[0]
        assert "month" in item
        assert "consumption" in item


@pytest.mark.asyncio
async def test_consumption_trend_max_6_months(
    async_client, async_superuser_token_headers
):
    """En fazla 6 aylık veri dönmeli"""
    response = await async_client.get(
        "/api/v1/reports/consumption-trend", headers=async_superuser_token_headers
    )
    data = response.json()
    if "data" in data:
        data = data["data"]
    assert len(data) <= 6


# WebSocket tests often require TestClient (sync)
# I'll check if 'client' fixture is available.
# If not, I'll use async_client's app with TestClient.
def test_ws_dashboard_unauthorized(client):
    """Token olmadan WebSocket bağlantısı reddedilmeli (1008)"""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/admin/ws/live"):
            pass
    assert exc_info.value.code == 1008


def test_ws_dashboard_invalid_token(client):
    """Geçersiz token ile WebSocket bağlantısı reddedilmeli"""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/admin/ws/live?token=invalid_token"):
            pass
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_ws_dashboard_success_and_ping(client, async_superuser_token_headers):
    """Geçerli token ile bağlanılmalı, ilk veriyi almalı ve ping-pong çalışmalı"""
    token = async_superuser_token_headers["Authorization"].split(" ")[1]

    with client.websocket_connect(f"/api/v1/admin/ws/live?token={token}") as websocket:
        websocket.send_text("ping")
        response = websocket.receive_json()
        assert response["type"] == "pong"
