"""
T3-C: IntegrityError → response body DB schema içermemeli.

Bug Açıklaması:
  FK/Constraint violation sonrası error response'da tablo adları/constraint adları
  görülüyor. DB schema leakage vulnerability.

Beklenen: 422 + sanitized error message (schema detayları gizli).
"""

import pytest


@pytest.mark.integration
async def test_create_trip_fk_error_hides_schema(async_client, auth_headers):
    """
    T3-C: Sefer create'te FK violation → response'da DB schema bilgisi yok.

    Senaryo:
    - Mevcut olmayan arac_id ile sefer oluştur
    - IntegrityError beklenen (FK violation)
    - Response'da "araclar" tablo adı, "FOREIGN KEY" keywords YOK
    """

    response = await async_client.post(
        "/api/v1/trips/",
        json={
            "arac_id": 999999,  # Non-existent vehicle
            "sofor_id": 1,
            "tarih": "2026-05-31",
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 400.0,
            "durum": "Tamamlandi",
            "net_kg": 10000,
            "bos_agirlik_kg": 5000,
            "dolu_agirlik_kg": 15000,
            "flat_distance_km": 400.0,
        },
        headers=auth_headers,
    )

    # Should get error response (422 or similar, not 500)
    assert response.status_code in (400, 422, 409), (
        f"T3-C: FK violation should return 4xx (got {response.status_code}). "
        f"Expected: 422 Unprocessable Entity"
    )

    # Check response body for schema leakage
    body_text = str(response.json()).lower()

    assert "araclar" not in body_text, (
        f"T3-C: Response leaked table name 'araclar'. Response: {response.json()}"
    )
    assert "foreign key" not in body_text, (
        f"T3-C: Response leaked 'FOREIGN KEY' constraint details. "
        f"Response: {response.json()}"
    )
    assert "constraint" not in body_text or "violation" not in body_text, (
        f"T3-C: Response exposed constraint violation details. "
        f"Must sanitize error messages. "
        f"Response: {response.json()}"
    )
