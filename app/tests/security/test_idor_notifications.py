"""
T3-A: IDOR — başka kullanıcının bildirimini okundu işaretleme.

Bug Açıklaması:
  notification.read endpoint ownership kontrolü eksik.
  Kullanıcı başka kullanıcının notification'ını okundu işaretleyebiliyor.

Beklenen: 403 Forbidden (ownership check failed).
"""

import pytest
from sqlalchemy import insert, select


@pytest.mark.integration
async def test_cannot_mark_other_users_notification_as_read(
    async_client, auth_headers, db_session
):
    """
    T3-A: Normal kullanıcı başka kullanıcının notification'ını
    okundu işaretleyememelider.

    Senaryo:
    - Admin kullanıcıya ait notification oluştur
    - Normal kullanıcı tokenıyla PATCH /api/v1/notifications/{id}/read
    - 403 veya 404 beklenir (200 dönüyorsa IDOR → BUG)
    """

    from app.database.models import BildirimGecmisi, Kullanici

    # Admin kullanıcıyı bul (genelde user_id=1)
    admin_result = await db_session.execute(select(Kullanici).where(Kullanici.id == 1))
    admin_user = admin_result.scalars().first()

    if not admin_user:
        # Admin yok ise test skip
        pytest.skip("Admin user not found")

    # Admin kullanıcısına ait notification oluştur (gerçek model: BildirimGecmisi)
    notif_result = await db_session.execute(
        insert(BildirimGecmisi).values(
            kullanici_id=admin_user.id,
            baslik="Admin Notification",
            icerik="This is admin only",
            kanal="system",
        )
    )
    notif_id = notif_result.inserted_primary_key[0]
    await db_session.commit()

    # Normal kullanıcı tokenıyla (auth_headers) notification'ı okundu işaretlemeyi dene
    response = await async_client.patch(
        f"/api/v1/notifications/{notif_id}/read",
        json={"okundu": True},
        headers=auth_headers,
    )

    # FAIL if 200 (unauthorized access!)
    assert response.status_code in (403, 404), (
        f"T3-A: IDOR vulnerability detected! "
        f"Status {response.status_code} — another user's notification can be modified! "
        f"Expected 403 (Forbidden) or 404 (Not Found), got {response.status_code}."
    )
