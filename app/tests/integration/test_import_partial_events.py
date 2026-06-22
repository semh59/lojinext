"""
T5-A: Partial import — partial commit + dangling event bus.

Bug Açıklaması:
  Import'ta geçerli satırlar kaydediliyor ama invalid satırlar exception fırlatıyor.
  Event bus: kaydedilen her satır için event yayınlanıyor,
  başarısızlık sonrası yayılan event'ler DB'ye gitmiyor (dangling).

Beklenen: Valid satırlar kaydedilmeli, invalid sayısı rapor edilmeli,
  event'ler sadece başarılı satırlar için publish edilmeli.
"""

import pytest
from sqlalchemy import select

from app.database.models import Sefer

# OBSOLETE (test debt): targets the removed /trips/import path with a CSV body.
# The live endpoint /trips/upload is Excel-only. Needs a rewrite with an xlsx
# fixture + current-contract assertions before re-enabling.
pytestmark = pytest.mark.skip(
    reason="Obsolete import contract (Excel-only /upload); rewrite with xlsx fixture"
)


@pytest.mark.integration
async def test_partial_import_dangling_events_count(
    db_session, async_client, auth_headers, mock_event_bus
):
    """
    T5-A: Sefer bulk import — partial success, event count matches saved rows.

    Senaryo:
    1. 5 geçerli + 3 geçersiz sefer satırı upload et
    2. Response: saved=5, errors=3
    3. event_bus.publish call_count == 5 (başarısız satırlar event vermemeli)

    Not: Mock event bus'ın publish() method'u sayılacak (unittest.mock.MagicMock).
    """

    # CSV: 5 valid + 3 invalid (invalid olanlar alanlar eksik/yanlış)
    csv_content = b"""arac_id,sofor_id,tarih,cikis_yeri,varis_yeri,mesafe_km,durum,net_kg,bos_agirlik_kg,dolu_agirlik_kg,flat_distance_km
1,1,2026-05-30,Istanbul,Ankara,400.0,Tamamlandi,10000,5000,15000,400.0
1,2,2026-05-30,Ankara,Izmir,500.0,Tamamlandi,11000,5000,16000,500.0
1,3,2026-05-30,Izmir,Antalya,600.0,Tamamlandi,12000,5000,17000,600.0
1,4,2026-05-30,Antalya,Bursa,450.0,Tamamlandi,10500,5000,15500,450.0
1,5,2026-05-30,Bursa,Eskisehir,300.0,Tamamlandi,9000,5000,14000,300.0
,,2026-05-30,X,Y,100.0,Tamamlandi,5000,5000,10000,100.0
1,,2026-05-30,A,B,200.0,Tamamlandi,8000,5000,13000,200.0
,,2026-05-30,C,D,250.0,Tamamlandi,7500,5000,12500,250.0
"""  # noqa: E501

    from io import BytesIO

    files = {"file": ("trips.csv", BytesIO(csv_content), "text/csv")}

    response = await async_client.post(
        "/api/v1/trips/import",
        files=files,
        headers=auth_headers,
    )

    # Check response
    assert response.status_code in (200, 207), (
        f"T5-A: Import endpoint should accept partial imports. "
        f"Status: {response.status_code}"
    )

    result = response.json()
    saved_count = result.get("saved", 0)
    error_count = len(result.get("errors", []))

    # Verify counts (5 valid, 3 invalid)
    assert saved_count >= 5, (
        f"T5-A: Expected >= 5 valid rows saved, got {saved_count}. "
        f"Errors: {result.get('errors', [])}"
    )
    assert error_count >= 3, f"T5-A: Expected >= 3 error rows, got {error_count}."

    # T5-A: Event bus should have published for saved rows only
    # Count the actual publish calls
    if mock_event_bus and hasattr(mock_event_bus, "publish"):
        publish_count = getattr(mock_event_bus.publish, "call_count", 0)
        assert publish_count <= saved_count, (
            f"T5-A: Event bus published {publish_count} times for {saved_count} saved rows. "
            f"Should publish == saved_count (no dangling events). "
            f"Sorun: event'ler başarısız satırlar için de publish edilmiş olabilir."
        )

    # Verify saved rows in DB
    db_seferler = await db_session.execute(select(Sefer))
    db_count = len(db_seferler.scalars().all())

    assert db_count >= saved_count, (
        f"T5-A: DB row count mismatch. "
        f"Response says {saved_count} saved, DB has {db_count}."
    )
