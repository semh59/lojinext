"""
T3-A: IDOR — başka kullanıcının bildirimini okundu işaretleme.

Bug Açıklaması:
  notification.read endpoint ownership kontrolü eksik.
  Kullanıcı başka kullanıcının notification'ını okundu işaretleyebiliyor.

Beklenen: 403 Forbidden veya 404 Not Found (ownership check failed).

2026-07-01 düzeltmesi (prod-grade denetim P0 #7): Bu test önceki halinde
üç ayrı nedenle hiçbir güvenlik garantisi sağlamıyordu:
  1. `Kullanici.id == 1` var olduğunu varsayıyordu; taze bir test şemasında
     (app/tests/conftest.py her oturum başında şemayı yeniden oluşturur, hiçbir
     yerde id=1'e sabitlenmiş bir kullanıcı seed edilmez) bu satır hiç
     karşılanmıyor ve test `pytest.skip("Admin user not found")` ile
     SESSİZCE atlanıyordu — ampirik olarak doğrulandı (`pytest -v` çıktısı:
     "1 skipped"). Yani bu IDOR regresyon testi muhtemelen hiç çalışmamıştı.
  2. `auth_headers` fixture'ı normal bir kullanıcı değil, **break-glass
     süper-admin** token'ı üretiyordu (`app/tests/conftest.py:606-617`,
     `is_super: True`) — süper-admin'in `current_user.id`'si sentetik (0 veya
     env-superadmin satırı) olduğundan, gerçek bir "normal kullanıcı başka
     bir kullanıcının verisine erişebiliyor mu" senaryosunu hiç test etmiyordu.
  3. İstek URL'i yanlıştı: `/api/v1/notifications/{id}/read` diye bir route
     yok — gerçek mount noktası `/api/v1/admin/notifications/{id}/read`
     (`app/api/v1/api.py:119-122`, `admin_notifications.router`). Test
     çalışsaydı bile muhtemelen "route yok → 404" ile YANLIŞ SEBEPTEN
     PASS olurdu, gerçek ownership-check hiç tetiklenmezdi.

Bu üçü birden düzeltildi: test artık iki GERÇEK, bağımsız kullanıcıyı kendi
içinde oluşturuyor (hiçbir dış seed'e bağımlı değil, asla skip olmaz), sahte
sahibi olmayan normal bir "attacker" kullanıcının token'ıyla istek atıyor, ve
doğru URL'i kullanıyor. Ayrıca pozitif kontrol: istek sonrası bildirimin
GERÇEKTEN okunmamış kaldığı DB'den doğrulanıyor (yalnız status code değil).
"""

from datetime import timedelta

import pytest
from sqlalchemy import insert, select

from v2.modules.auth_rbac.domain.security import create_access_token, get_password_hash
from v2.modules.auth_rbac.public import Kullanici, Rol
from v2.modules.notification.public import BildirimGecmisi


@pytest.mark.integration
async def test_cannot_mark_other_users_notification_as_read(async_client, db_session):
    """
    T3-A: Normal kullanıcı başka kullanıcının notification'ını
    okundu işaretleyememelidir.

    Senaryo:
    - İki bağımsız gerçek kullanıcı oluştur: owner (bildirim sahibi) ve
      attacker (saldırgan — normal, ayrıcalıksız kullanıcı).
    - owner'a ait bir bildirim oluştur.
    - attacker'ın GERÇEK login token'ıyla
      PATCH /api/v1/admin/notifications/{id}/read çağır.
    - 403 veya 404 beklenir (200 dönüyorsa IDOR → BUG).
    - Ek doğrulama: bildirim DB'de gerçekten okunmamış kalmalı.
    """
    role_result = await db_session.execute(select(Rol).where(Rol.ad == "izleyici"))
    role = role_result.scalar_one_or_none()
    if not role:
        role = Rol(ad="izleyici", yetkiler={"sefer:read": True})
        db_session.add(role)
        await db_session.flush()

    owner = Kullanici(
        email="idor-owner@lojinext.test",
        sifre_hash=get_password_hash("ownerpass123"),
        ad_soyad="Notification Owner",
        rol_id=role.id,
        aktif=True,
    )
    attacker = Kullanici(
        email="idor-attacker@lojinext.test",
        sifre_hash=get_password_hash("attackerpass123"),
        ad_soyad="Attacker",
        rol_id=role.id,
        aktif=True,
    )
    db_session.add_all([owner, attacker])
    await db_session.flush()

    notif_result = await db_session.execute(
        insert(BildirimGecmisi).values(
            kullanici_id=owner.id,
            baslik="Owner Notification",
            icerik="This belongs to the owner only",
            kanal="system",
        )
    )
    notif_id = notif_result.inserted_primary_key[0]
    await db_session.commit()

    attacker_token = create_access_token(
        data={"sub": attacker.email},
        expires_delta=timedelta(minutes=30),
    )
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    response = await async_client.patch(
        f"/api/v1/admin/notifications/{notif_id}/read",
        headers=attacker_headers,
    )

    assert response.status_code in (403, 404), (
        f"T3-A: IDOR vulnerability detected! "
        f"attacker (id={attacker.id}) was able to act on owner's "
        f"(id={owner.id}) notification {notif_id}. "
        f"Expected 403 (Forbidden) or 404 (Not Found), got "
        f"{response.status_code}."
    )

    # Positive control: the status code alone doesn't prove nothing changed
    # (e.g. a 404 from an unrelated route bug would also pass the assertion
    # above) — confirm the notification is genuinely still unread in the DB.
    reread = await db_session.execute(
        select(BildirimGecmisi).where(BildirimGecmisi.id == notif_id)
    )
    row = reread.scalar_one()
    assert row.okundu_tarihi is None, (
        "IDOR vulnerability: notification was marked as read despite the "
        "403/404 response."
    )
