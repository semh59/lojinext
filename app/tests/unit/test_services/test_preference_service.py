"""preference_service use-case tests — real DB, no mocked UoW.

Previously these mocked the UnitOfWork/session and asserted on inner calls
(`session.add.assert_called()`, `setting_repo.update.assert_called()`), which
verifies *that a method was called* rather than *the persisted result*. Here
the free functions run against the real test DB (db_session monkeypatches
AsyncSessionLocal, so the internal `UnitOfWork()` fallback uses the test
session) and we assert the real KullaniciAyari rows (created / updated /
deleted / default-flagged).
"""

import pytest
from sqlalchemy import insert, select

from app.infrastructure.security.pii_encryption import blind_index
from v2.modules.auth_rbac.application import preference_service
from v2.modules.auth_rbac.public import Kullanici, KullaniciAyari, Rol

pytestmark = pytest.mark.integration


async def _seed_user(db_session) -> int:
    rid = (
        await db_session.execute(insert(Rol).values(ad="pref_role", yetkiler={}))
    ).inserted_primary_key[0]
    uid = (
        await db_session.execute(
            insert(Kullanici).values(
                email="pref@lojinext.test",
                email_bidx=blind_index("pref@lojinext.test"),
                ad_soyad="Pref User",
                sifre_hash="x",
                rol_id=rid,
                aktif=True,
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return uid


async def _seed_setting(
    db_session, user_id, modul, ayar_tipi, deger, *, is_default=False
) -> int:
    sid = (
        await db_session.execute(
            insert(KullaniciAyari).values(
                kullanici_id=user_id,
                modul=modul,
                ayar_tipi=ayar_tipi,
                deger=deger,
                is_default=is_default,
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return sid


async def _get_setting(db_session, sid):
    return (
        await db_session.execute(select(KullaniciAyari).where(KullaniciAyari.id == sid))
    ).scalar_one_or_none()


class TestPreferenceService:
    async def test_get_preferences_happy_path(self, db_session):
        uid = await _seed_user(db_session)
        await _seed_setting(db_session, uid, "dashboard", "filter", {"theme": "dark"})

        result = await preference_service.get_preferences(
            user_id=uid, modul="dashboard"
        )

        assert len(result) == 1
        assert result[0].deger == {"theme": "dark"}

    async def test_get_preferences_not_found(self, db_session):
        uid = await _seed_user(db_session)
        result = await preference_service.get_preferences(user_id=uid, modul="trips")
        assert result == []

    async def test_save_preference_happy_path(self, db_session):
        uid = await _seed_user(db_session)

        result = await preference_service.save_preference(
            user_id=uid, modul="dashboard", ayar_tipi="filter", deger={"theme": "dark"}
        )

        assert result is not None
        # Real row persisted with the given value — the business outcome.
        row = await _get_setting(db_session, result.id)
        assert row is not None
        assert row.kullanici_id == uid
        assert row.deger == {"theme": "dark"}

    async def test_save_preference_with_existing(self, db_session):
        uid = await _seed_user(db_session)
        sid = await _seed_setting(
            db_session, uid, "dashboard", "sutun", {"cols": ["old"]}
        )

        result = await preference_service.save_preference(
            user_id=uid, modul="dashboard", ayar_tipi="sutun", deger={"cols": ["new"]}
        )

        assert result is not None
        # The existing row was updated in place (no duplicate insert).
        row = await _get_setting(db_session, sid)
        assert row.deger == {"cols": ["new"]}
        all_rows = (
            (
                await db_session.execute(
                    select(KullaniciAyari).where(KullaniciAyari.kullanici_id == uid)
                )
            )
            .scalars()
            .all()
        )
        assert len(all_rows) == 1

    async def test_delete_preference(self, db_session):
        uid = await _seed_user(db_session)
        sid = await _seed_setting(db_session, uid, "dashboard", "filter", {"a": 1})

        result = await preference_service.delete_preference(user_id=uid, pref_id=sid)

        assert result is True
        assert await _get_setting(db_session, sid) is None

    async def test_delete_preference_not_found(self, db_session):
        uid = await _seed_user(db_session)
        result = await preference_service.delete_preference(user_id=uid, pref_id=999999)
        assert result is False

    async def test_set_default(self, db_session):
        uid = await _seed_user(db_session)
        sid = await _seed_setting(
            db_session, uid, "dashboard", "filter", {"a": 1}, is_default=False
        )

        result = await preference_service.set_default(user_id=uid, pref_id=sid)

        assert result is True
        row = await _get_setting(db_session, sid)
        assert row.is_default is True

    async def test_save_preference_rejects_zero_user_id(self):
        with pytest.raises(ValueError, match="Geçersiz kullanıcı"):
            await preference_service.save_preference(
                user_id=0, modul="dashboard", ayar_tipi="filter", deger={}
            )

    async def test_save_preference_rejects_negative_user_id(self):
        with pytest.raises(ValueError, match="Geçersiz kullanıcı"):
            await preference_service.save_preference(
                user_id=-1, modul="dashboard", ayar_tipi="filter", deger={}
            )

    def test_service_instantiation(self):
        assert hasattr(preference_service, "get_preferences")
        assert hasattr(preference_service, "save_preference")
