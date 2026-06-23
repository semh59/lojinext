"""
Real-object integration tests for NotificationService.mark_as_read ownership guard.

SEC-001 regression guard: mark_as_read must reject cross-user read attempts
(IDOR). Previously the service accepted user_id as a keyword arg but never
used it — any authenticated user could mark any notification as read.
"""

import pytest
from sqlalchemy import insert, text

from app.database.models import BildirimGecmisi, Kullanici

pytestmark = pytest.mark.integration


async def _create_rol(db_session) -> int:
    """Insert a minimal Rol row and return its id."""
    result = await db_session.execute(
        text(
            "INSERT INTO roller (ad, yetkiler) VALUES (:ad, '{}') "
            "ON CONFLICT (ad) DO UPDATE SET ad=EXCLUDED.ad RETURNING id"
        ),
        {"ad": "test_rol_notif"},
    )
    await db_session.commit()
    return result.scalar()


async def _create_user(db_session, email: str, rol_id: int) -> int:
    result = await db_session.execute(
        insert(Kullanici).values(
            email=email,
            ad_soyad="Test Kullanici",
            sifre_hash="$2b$12$fakehashfakehashfakeh.",
            rol_id=rol_id,
            aktif=True,
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


async def _create_notification(db_session, kullanici_id: int) -> int:
    result = await db_session.execute(
        insert(BildirimGecmisi).values(
            kullanici_id=kullanici_id,
            baslik="Test Bildirimi",
            icerik="Test icerik",
            kanal="in_app",
            durum="sent",
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


async def test_mark_as_read_rejects_wrong_user(db_session):
    """
    SEC-001: mark_as_read(notification_id, user_id=wrong_user) must return
    False and leave the notification unread.
    """
    from app.core.services.notification_service import NotificationService

    rol_id = await _create_rol(db_session)
    user_a_id = await _create_user(db_session, "owner_a@test.local", rol_id)
    user_b_id = await _create_user(db_session, "attacker_b@test.local", rol_id)

    notif_id = await _create_notification(db_session, user_a_id)

    svc = NotificationService()
    result = await svc.mark_as_read(notif_id, user_id=user_b_id)

    assert result is False, (
        "SEC-001: mark_as_read returned True for wrong user — IDOR still present"
    )


async def test_mark_as_read_accepts_owner(db_session):
    """
    SEC-001: mark_as_read(notification_id, user_id=owner) must return True
    and update the notification status.
    """
    from app.core.services.notification_service import NotificationService

    rol_id = await _create_rol(db_session)
    user_id = await _create_user(db_session, "real_owner@test.local", rol_id)

    notif_id = await _create_notification(db_session, user_id)

    svc = NotificationService()
    result = await svc.mark_as_read(notif_id, user_id=user_id)

    assert result is True, (
        "SEC-001: mark_as_read returned False for legitimate owner — ownership check too strict"
    )


async def test_mark_as_read_nonexistent_notification(db_session):
    """
    mark_as_read on a non-existent notification_id must return False,
    not raise an exception.
    """
    from app.core.services.notification_service import NotificationService

    rol_id = await _create_rol(db_session)
    user_id = await _create_user(db_session, "ghost_user@test.local", rol_id)

    svc = NotificationService()
    result = await svc.mark_as_read(999_999_999, user_id=user_id)

    assert result is False


async def test_mark_as_read_cross_user_does_not_alter_row(db_session):
    """
    After a rejected cross-user call, the notification durum must still be 'sent'.
    """
    from sqlalchemy import select

    from app.core.services.notification_service import NotificationService

    rol_id = await _create_rol(db_session)
    user_a_id = await _create_user(db_session, "owner_dup@test.local", rol_id)
    user_b_id = await _create_user(db_session, "badactor_dup@test.local", rol_id)

    notif_id = await _create_notification(db_session, user_a_id)

    svc = NotificationService()
    await svc.mark_as_read(notif_id, user_id=user_b_id)

    row = (
        await db_session.execute(
            select(BildirimGecmisi).where(BildirimGecmisi.id == notif_id)
        )
    ).scalar_one()

    assert row.durum == "sent", (
        f"Notification durum was changed by wrong-user call: {row.durum}"
    )
    assert row.okundu_tarihi is None, "okundu_tarihi set by attacker's call"
