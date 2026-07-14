"""POST /fuel/ocr-preview testleri."""

from contextlib import asynccontextmanager
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

# Geçerli JPEG magic byte (>=12 bayt) — ARCH-020 sniff'i geçer
_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"x" * 20


def _ocr_client_mock(payload):
    @asynccontextmanager
    async def _factory(*a, **k):
        client = MagicMock()
        resp = MagicMock()
        resp.json = MagicMock(return_value=payload)
        resp.raise_for_status = MagicMock()
        client.post = AsyncMock(return_value=resp)
        yield client

    return _factory


async def test_ocr_preview_returns_parsed_fields(
    async_client, admin_auth_headers, monkeypatch
):
    payload = {
        "ham_metin": "PETROL OFISI 45.50 LT 1.234,56 TL 123456 KM",
        "yapilandirilmis": {
            "litre": 45.5,
            "tutar": 1234.56,
            "km": 123456,
            "tarih": "01/06/2026",
            "istasyon": "PETROL OFISI",
        },
    }
    monkeypatch.setattr(
        "v2.modules.fuel.api.fuel_routes.get_monitored_client",
        _ocr_client_mock(payload),
    )
    resp = await async_client.post(
        "/api/v1/fuel/ocr-preview",
        files={"file": ("fis.jpg", BytesIO(_JPEG), "image/jpeg")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["yapilandirilmis"]["litre"] == 45.5
    assert body["yapilandirilmis"]["istasyon"] == "PETROL OFISI"


async def test_ocr_preview_rejects_non_image(async_client, admin_auth_headers):
    resp = await async_client.post(
        "/api/v1/fuel/ocr-preview",
        files={"file": ("x.txt", BytesIO(b"not an image at all"), "image/jpeg")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 415


async def test_ocr_preview_requires_auth(async_client):
    resp = await async_client.post(
        "/api/v1/fuel/ocr-preview",
        files={"file": ("fis.jpg", BytesIO(_JPEG), "image/jpeg")},
    )
    assert resp.status_code == 401
