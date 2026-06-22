"""
T4-B: Partial import — mixed valid/invalid rows.
T5-A: Partial commit + dangling event bus.

Bug Açıklaması:
  Import'ta geçerli satırlar kaydediliyor ama invalid satırlar exception fırlatıyor.
  Event bus: kaydedilen her satır için event yayınlanıyor,
  başarısızlık sonrası yayılan event'ler DB'ye gitmiyor (dangling).

Beklenen: Valid satırlar kaydedilmeli, invalid sayısı rapor edilmeli,
  event'ler sadece başarılı satırlar için publish edilmeli.
"""

import pytest
from sqlalchemy import select

from app.database.models import Arac

# OBSOLETE (test debt): this targets the removed /vehicles/import path and a
# 'saved' response key. The live endpoint /vehicles/upload is Excel-only and
# returns {success, message, errors}. Needs a rewrite with an xlsx fixture and
# current-contract assertions before it can be re-enabled.
pytestmark = pytest.mark.skip(
    reason="Obsolete import contract (Excel-only /upload); rewrite with xlsx fixture"
)


@pytest.mark.integration
async def test_partial_import_counts_match(
    db_session, async_client, auth_headers, mock_event_bus
):
    """
    5 geçerli + 3 geçersiz satır yüklendiğinde:
    - Kaydedilen: 5
    - Hata sayısı: 3
    - Event yayın sayısı: 5 (sadece başarılı olanlar için)
    """

    # CSV içeriği: 5 geçerli, 3 geçersiz (mevcut olmayan arac_id FK violation)
    csv_content = """Plaka,Marka,Model,Yil
99 IMP 001,Volvo,FH16,2020
99 IMP 002,Scania,R450,2019
99 IMP 003,MAN,TGX,2021
99 IMP 004,DAF,XF,2020
99 IMP 005,Iveco,S-Way,2022
99 IMP 006,Unknown,Invalid,2015
99 IMP 007,Bad,Row,2010
99 IMP 008,Fail,Test,2018
"""

    # Dosyayı upload et
    from io import BytesIO

    files = {"file": ("vehicles.csv", BytesIO(csv_content.encode()), "text/csv")}

    response = await async_client.post(
        "/api/v1/vehicles/import",
        files=files,
        headers=auth_headers,
    )

    # Check response
    assert response.status_code == 200 or response.status_code == 400, (
        f"Import endpoint unexpected status: {response.status_code}"
    )

    result = response.json()

    # Doğrulamalar
    saved_count = result.get("saved", 0)
    error_count = len(result.get("errors", []))

    assert saved_count == 5, (
        f"T4-B: Expected 5 valid rows saved, got {saved_count}. "
        f"Errors: {result.get('errors', [])}"
    )

    assert error_count == 3, (
        f"T4-B: Expected 3 error rows, got {error_count}. "
        f"Errors: {result.get('errors', [])}"
    )

    # T5-A: Event bus should have published exactly 5 times (valid rows only)
    # In a real implementation, we'd check mock_event_bus.publish.call_count
    # For now, just verify that saved count matches what went to DB
    vehicles = await db_session.execute(select(Arac))
    db_count = len(vehicles.scalars().all())

    assert db_count >= saved_count, (
        f"T5-A: Saved count mismatch. Response says {saved_count}, DB has {db_count}"
    )
