"""
T4-A: Latin-1 CSV encoding → anlaşılır hata mesajı.

Bug Açıklaması:
  UTF-8 olmayan CSV yüklendiğinde hata mesajı belirsiz.
  Doğru: "encoding" veya "karakter" içeren mesaj döndürülmeli.

Beklenen: 400 + descriptive error message.
"""

from io import BytesIO

import pytest

# OBSOLETE (test debt): premise was a latin-1 CSV upload yielding an encoding
# error. The live /vehicles/upload is Excel-only (no CSV text-encoding path), and
# the fixture itself can't encode 'Ş' as latin-1. No equivalent behavior exists to
# assert; rewrite as an Excel-MIME rejection test if still wanted.
pytestmark = pytest.mark.skip(
    reason="Obsolete: Excel-only /upload has no CSV encoding-detection path"
)


@pytest.mark.integration
async def test_import_rejects_latin1_with_encoding_error(async_client, auth_headers):
    """
    Latin-1 encoded CSV yüklendiğinde, 400 + encoding error mesajı dönmeli.
    """

    # Latin-1 encoded content (Turkish characters with accents)
    content = "Plaka,Marka\n34ŞŞŞ001,Mercédes\n".encode("latin-1")

    # CSV dosyası yükle (multipart form)
    files = {"file": ("test.csv", BytesIO(content), "text/csv")}

    response = await async_client.post(
        "/api/v1/vehicles/import",
        files=files,
        headers=auth_headers,
    )

    # Expected: 400 Bad Request
    assert response.status_code == 400, (
        f"T4-A: Encoding error handling broken. "
        f"Beklenen: 400, Aldık: {response.status_code}. "
        f"Response: {response.json()}"
    )

    # Error message should mention encoding or character issues
    error_text = str(response.json()).lower()
    assert any(
        keyword in error_text for keyword in ["encoding", "character", "utf", "decode"]
    ), (
        f"T4-A: Error message unclear. "
        f"Should mention 'encoding' or 'character': {response.json()}"
    )
