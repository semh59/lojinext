"""
Coverage tests for app/schemas/user.py

Targets missed branches in:
- RolRead / RolCreate (validate_role_name, validate_permissions)
- KullaniciBase
- KullaniciCreate (validate_password)
- KullaniciUpdate (validate_password with None)
- KullaniciRead (heal_name, heal_email, heal_required_datetime, heal_optional_datetime, heal_ip)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


def _kullanici_read_payload(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    base = dict(
        email="test@example.com",
        ad_soyad="Test Kullanici",
        rol_id=1,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# RolRead
# ---------------------------------------------------------------------------


class TestRolRead:
    def test_valid(self):
        from v2.modules.auth_rbac.schemas import RolRead

        obj = RolRead(
            id=1,
            ad="admin",
            yetkiler={"read": True},
            olusturma=datetime.now(timezone.utc),
        )
        assert obj.ad == "admin"
        assert obj.yetkiler == {"read": True}


# ---------------------------------------------------------------------------
# RolCreate — validate_role_name
# ---------------------------------------------------------------------------


class TestRolCreate:
    def test_valid_role(self):
        from v2.modules.auth_rbac.schemas import RolCreate

        obj = RolCreate(ad="operator", yetkiler={"sefer:gör": True})
        assert obj.ad == "operator"

    def test_whitespace_stripped(self):
        from v2.modules.auth_rbac.schemas import RolCreate

        obj = RolCreate(ad="  manager  ", yetkiler={"x": True})
        assert obj.ad == "manager"

    def test_empty_name_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import RolCreate

        with pytest.raises(ValidationError, match="bos olamaz"):
            RolCreate(ad="   ", yetkiler={"x": True})

    def test_empty_yetkiler_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import RolCreate

        with pytest.raises(ValidationError, match="bos olamaz"):
            RolCreate(ad="admin", yetkiler={})

    def test_empty_key_in_yetkiler_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import RolCreate

        with pytest.raises(ValidationError, match="bos olamaz"):
            RolCreate(ad="admin", yetkiler={"  ": True})

    def test_valid_permissions_normalized(self):
        from v2.modules.auth_rbac.schemas import RolCreate

        obj = RolCreate(ad="driver", yetkiler={"  sefer:gör  ": True})
        assert "sefer:gör" in obj.yetkiler


# ---------------------------------------------------------------------------
# KullaniciBase
# ---------------------------------------------------------------------------


class TestKullaniciBase:
    def test_valid_base(self):
        from v2.modules.auth_rbac.schemas import KullaniciBase

        obj = KullaniciBase(email="user@company.tr", ad_soyad="Mehmet Demir")
        assert obj.email == "user@company.tr"
        assert obj.aktif is True
        assert obj.sofor_id is None


# ---------------------------------------------------------------------------
# KullaniciCreate — validate_password
# ---------------------------------------------------------------------------


class TestKullaniciCreate:
    def test_valid_user(self):
        from v2.modules.auth_rbac.schemas import KullaniciCreate

        obj = KullaniciCreate(
            email="driver@loji.tr",
            ad_soyad="Ali Veli",
            rol_id=2,
            sifre="SecurePass1",
        )
        assert obj.sifre == "SecurePass1"

    def test_weak_password_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import KullaniciCreate

        with pytest.raises(ValidationError):
            KullaniciCreate(
                email="x@y.com",
                ad_soyad="Test User",
                rol_id=1,
                sifre="weak",
            )

    def test_no_uppercase_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import KullaniciCreate

        with pytest.raises(ValidationError, match="büyük harf"):
            KullaniciCreate(
                email="x@y.com",
                ad_soyad="Test User",
                rol_id=1,
                sifre="password1",
            )

    def test_no_digit_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import KullaniciCreate

        with pytest.raises(ValidationError, match="rakam"):
            KullaniciCreate(
                email="x@y.com",
                ad_soyad="Test User",
                rol_id=1,
                sifre="PasswordOnly",
            )


# ---------------------------------------------------------------------------
# KullaniciUpdate — validate_password with None
# ---------------------------------------------------------------------------


class TestKullaniciUpdate:
    def test_none_password_stays_none(self):
        from v2.modules.auth_rbac.schemas import KullaniciUpdate

        obj = KullaniciUpdate(sifre=None)
        assert obj.sifre is None

    def test_valid_password_updated(self):
        from v2.modules.auth_rbac.schemas import KullaniciUpdate

        obj = KullaniciUpdate(sifre="NewPass1")
        assert obj.sifre == "NewPass1"

    def test_weak_password_update_raises(self):
        from pydantic import ValidationError

        from v2.modules.auth_rbac.schemas import KullaniciUpdate

        with pytest.raises(ValidationError):
            KullaniciUpdate(sifre="bad")

    def test_empty_update_valid(self):
        from v2.modules.auth_rbac.schemas import KullaniciUpdate

        obj = KullaniciUpdate()
        assert obj.email is None
        assert obj.rol_id is None


# ---------------------------------------------------------------------------
# KullaniciRead — heal_name
# ---------------------------------------------------------------------------


class TestKullaniciReadHealName:
    def test_none_name_becomes_bilinmiyor(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(ad_soyad=None))
        assert obj.ad_soyad == "BİLİNMİYEN KULLANICI"

    def test_empty_name_becomes_bilinmiyor(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(ad_soyad="   "))
        assert obj.ad_soyad == "BİLİNMİYEN KULLANICI"

    def test_short_name_becomes_bilinmiyor(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(ad_soyad="A"))
        assert obj.ad_soyad == "BİLİNMİYEN KULLANICI"

    def test_valid_name_kept(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(ad_soyad="Ahmet Yıldız")
        )
        assert obj.ad_soyad == "Ahmet Yıldız"


# ---------------------------------------------------------------------------
# KullaniciRead — heal_email
# ---------------------------------------------------------------------------


class TestKullaniciReadHealEmail:
    def test_none_email_becomes_fallback(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(email=None))
        assert obj.email == "no-email@system.local"

    def test_empty_email_becomes_fallback(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(email="   "))
        assert obj.email == "no-email@system.local"

    def test_valid_email_stripped(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(email="  user@loji.tr  ")
        )
        assert obj.email == "user@loji.tr"


# ---------------------------------------------------------------------------
# KullaniciRead — heal_required_datetime
# ---------------------------------------------------------------------------


class TestKullaniciReadHealRequiredDatetime:
    def test_none_created_at_becomes_now(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(created_at=None))
        assert isinstance(obj.created_at, datetime)

    def test_isostring_parsed(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(created_at="2026-01-01T00:00:00Z")
        )
        assert obj.created_at.year == 2026

    def test_bad_string_becomes_now(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(created_at="bad"))
        assert isinstance(obj.created_at, datetime)

    def test_datetime_object_passthrough(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        obj = KullaniciRead.model_validate(_kullanici_read_payload(created_at=dt))
        assert obj.created_at == dt


# ---------------------------------------------------------------------------
# KullaniciRead — heal_optional_datetime (son_giris, sifre_degisim_tarihi)
# ---------------------------------------------------------------------------


class TestKullaniciReadHealOptionalDatetime:
    def test_none_son_giris_stays_none(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(son_giris=None))
        assert obj.son_giris is None

    def test_isostring_son_giris_parsed(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(son_giris="2026-03-15T08:00:00Z")
        )
        assert obj.son_giris.year == 2026

    def test_bad_son_giris_becomes_none(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(son_giris="not-a-date")
        )
        assert obj.son_giris is None

    def test_datetime_son_giris_passthrough(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        dt = datetime(2025, 12, 1, tzinfo=timezone.utc)
        obj = KullaniciRead.model_validate(_kullanici_read_payload(son_giris=dt))
        assert obj.son_giris == dt

    def test_none_sifre_degisim_tarihi_stays_none(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(sifre_degisim_tarihi=None)
        )
        assert obj.sifre_degisim_tarihi is None


# ---------------------------------------------------------------------------
# KullaniciRead — heal_ip
# ---------------------------------------------------------------------------


class TestKullaniciReadHealIp:
    def test_none_ip_stays_none(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(son_giris_ip=None))
        assert obj.son_giris_ip is None

    def test_empty_ip_becomes_none(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(_kullanici_read_payload(son_giris_ip="   "))
        assert obj.son_giris_ip is None

    def test_valid_ip_stripped(self):
        from v2.modules.auth_rbac.schemas import KullaniciRead

        obj = KullaniciRead.model_validate(
            _kullanici_read_payload(son_giris_ip="  192.168.1.1  ")
        )
        assert obj.son_giris_ip == "192.168.1.1"
