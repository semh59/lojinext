"""
Pydantic Schemas için kapsamlı test suite
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError


class TestSensitiveDataProtection:
    """Sensitive data koruması testleri"""

    def test_password_not_in_response(self):
        """Password response model'de olmamalı"""
        from app.schemas.user import KullaniciRead

        # UserResponse'da (KullaniciRead) password_hash olmamalı
        fields = KullaniciRead.model_fields.keys()
        assert "password" not in fields
        assert "password_hash" not in fields
        assert "sifre" not in fields
        assert "sifre_hash" not in fields


class TestStringValidation:
    """String field validation testleri"""

    def test_max_length_enforced(self):
        """Maximum uzunluk zorlanmalı"""
        from app.schemas.arac import AracCreate

        # Çok uzun plaka reddedilmeli
        with pytest.raises(ValidationError):
            AracCreate(
                plaka="A" * 100,
                marka="Test",
                model="Tir",
                tank_kapasitesi=600,
                hedef_tuketim=30.0,
            )

    def test_empty_string_rejected(self):
        """Boş string reddedilmeli (zorunlu field)"""
        # Arac create plaka min_length=5
        from app.schemas.arac import AracCreate

        with pytest.raises(ValidationError):
            AracCreate(plaka="", marka="Test", tank_kapasitesi=600, hedef_tuketim=30.0)

    def test_turkish_characters_accepted(self):
        """Türkçe karakterler kabul edilmeli"""
        from app.schemas.sofor import SoforCreate

        sofor = SoforCreate(ad_soyad="İsmail Şoför Öğretici")
        assert sofor.ad_soyad == "İsmail Şoför Öğretici"


class TestNumericValidation:
    """Numeric field validation testleri"""

    def test_negative_not_allowed(self):
        """Negatif değerler reddedilmeli"""
        from decimal import Decimal

        from app.schemas.yakit import YakitCreate

        with pytest.raises(ValidationError):
            YakitCreate(
                tarih=date.today(),
                arac_id=1,
                litre=Decimal("-100"),
                fiyat_tl=Decimal("50"),
                toplam_tutar=Decimal("5000"),
                km_sayac=10000,
            )


class TestDateValidation:
    """Date/datetime validation testleri"""

    def test_future_year_validation_arac(self):
        """Araç yılı çok ileri olamaz (Next year + 1 max)"""
        from app.schemas.arac import AracCreate

        year = datetime.now(timezone.utc).year + 5

        with pytest.raises(ValidationError):
            AracCreate(
                plaka="34TST01",
                marka="Test",
                yil=year,
                tank_kapasitesi=600,
                hedef_tuketim=30.0,
            )
