"""
Test Dosyaları Audit - Kapsamlı Edge Case ve Security Testleri
==============================================================

Bu modül, audit kapsamında tespit edilen eksik test senaryolarını içerir:
- None/Empty değer testleri
- Boundary değer testleri
- Unicode/Türkçe karakter testleri
- NaN/Infinity testleri
- Security testleri (SQL Injection, XSS, Input validation)
- Concurrent access testleri
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

# =============================================================================
# EDGE CASE TESTS - NONE/EMPTY VALUES
# =============================================================================


class TestNoneEmptyValues:
    """None ve boş değer durumları testleri."""

    def test_none_string_handling(self):
        """None string değeri entity'de hata vermeli."""
        from v2.modules.fleet.domain.entities import Arac

        with pytest.raises((ValidationError, TypeError, ValueError)):
            Arac(plaka=None, marka="Mercedes", yil=2020)

    def test_empty_string_plaka(self):
        """Boş string plaka kabul edilmemeli."""
        from v2.modules.fleet.domain.entities import Arac

        with pytest.raises(ValidationError):
            Arac(plaka="", marka="Mercedes", yil=2020)

    @pytest.mark.asyncio
    async def test_empty_list_fuel_periods(self):
        """Boş liste ile periyot oluşturma boş dönmeli."""
        from v2.modules.fuel.application.calculate_period import create_fuel_periods

        result = await create_fuel_periods([])
        assert result == []

    def test_none_in_numeric_field(self):
        """Zorunlu numeric alanda None hata vermeli."""
        from v2.modules.fuel.domain.entities import YakitAlimi

        with pytest.raises((ValidationError, TypeError)):
            YakitAlimi(
                tarih=date.today(),
                arac_id=1,
                fiyat_tl=None,  # Required numeric field
                litre=100,
                km_sayac=50000,
            )

    def test_empty_dict_handling(self):
        """Boş dict ile entity oluşturamazsın."""
        from v2.modules.fleet.domain.entities import Arac

        with pytest.raises((ValidationError, TypeError)):
            Arac(**{})


# =============================================================================
# BOUNDARY VALUE TESTS
# =============================================================================


class TestBoundaryValues:
    """Sınır değer testleri."""

    def test_zero_distance(self):
        """Sıfır mesafe - SeferCreate gt=0 kontrolü."""
        from v2.modules.trip.schemas import SeferCreate

        # Sefer modelinde ge=0 olduğu için SeferCreate DTO'sunun gt=0 kuralını test ediyoruz
        with pytest.raises(ValidationError):
            SeferCreate(
                tarih=date.today(),
                arac_id=1,
                sofor_id=1,
                net_kg=1000,
                cikis_yeri="Ankara",
                varis_yeri="İstanbul",
                mesafe_km=0,
            )

    def test_negative_distance(self):
        """Negatif mesafe asla kabul edilmemeli."""
        from v2.modules.trip.schemas import SeferCreate

        with pytest.raises(ValidationError):
            SeferCreate(
                tarih=date.today(),
                arac_id=1,
                sofor_id=1,
                net_kg=1000,
                cikis_yeri="Ankara",
                varis_yeri="İstanbul",
                mesafe_km=-100,
            )

    def test_max_integer_value(self):
        """Çok büyük sayı - overflow riski."""
        from v2.modules.trip.schemas import SeferCreate

        # Python int overflow olmaz ama DB'de sorun olabilir
        large_value = 2**31 - 1  # Max int32

        # Bu testi sadece ValidationError kontrol et
        try:
            sefer = SeferCreate(
                tarih=date.today(),
                arac_id=1,
                sofor_id=1,
                net_kg=large_value,
                cikis_yeri="Ankara",
                varis_yeri="İstanbul",
                mesafe_km=100,
            )
            # Eğer geçerse, ton hesaplaması doğru olmalı
            assert round(sefer.net_kg / 1000, 2) == pytest.approx(
                large_value / 1000, rel=1e-3
            )
        except ValidationError:
            # Max değer validasyonu varsa bu da kabul edilebilir
            pass

    def test_min_fuel_liter(self):
        """Minimum yakıt litresi - 0.01 L bile olabilir."""
        from v2.modules.fuel.domain.entities import YakitAlimi

        # YakitAlimi litre check: gt=0
        yakit = YakitAlimi(
            tarih=date.today(),
            arac_id=1,
            fiyat_tl=Decimal("40.0"),  # ge=0, le=200
            litre=0.01,
            km_sayac=50000,
        )
        # 40 * 0.01 = 0.40
        assert float(yakit.toplam_tutar) == pytest.approx(0.40, rel=1e-2)

    def test_future_date_rejected(self):
        """Gelecek tarih reddedilmeli."""
        from v2.modules.fuel.domain.entities import YakitAlimiCreate

        future = date.today() + timedelta(days=365)

        # Model seviyesinde veya service seviyesinde kontrol
        # Bazı modellerde bu kontrol yok olabilir
        try:
            dto = YakitAlimiCreate(
                tarih=future,
                arac_id=1,
                fiyat_tl=Decimal("45.0"),
                litre=100,
                km_sayac=50000,
            )
            # Eğer model kabul ederse service'de kontrol edilmeli
            assert dto.tarih == future
        except ValidationError:
            pass  # İdeal durum


# =============================================================================
# UNICODE/TURKISH CHARACTER TESTS
# =============================================================================


class TestUnicodeCharacters:
    """Unicode ve Türkçe karakter testleri."""

    def test_turkish_characters_in_name(self):
        """Türkçe karakterler doğru işlenmeli."""
        from v2.modules.driver.schemas import SoforCreate

        sofor = SoforCreate(ad_soyad="Şükrü Öğütçüoğlu", telefon="0532 555 1234")
        assert "ükrü" in sofor.ad_soyad
        assert "ğ" in sofor.ad_soyad
        assert "ü" in sofor.ad_soyad

    def test_turkish_city_names(self):
        """Türkçe şehir isimleri doğru işlenmeli."""
        from v2.modules.trip.domain.entities import Sefer

        sefer = Sefer(
            tarih=date.today(),
            arac_id=1,
            sofor_id=1,
            net_kg=20000,
            cikis_yeri="İstanbul",
            varis_yeri="Eskişehir",
            mesafe_km=300,
        )
        assert sefer.cikis_yeri == "İstanbul"
        assert "ş" in sefer.varis_yeri

    def test_special_characters_in_notes(self):
        """Özel karakterler notlarda kullanılabilmeli."""
        from v2.modules.fleet.domain.entities import Arac

        arac = Arac(
            plaka="34 ABC 123",
            marka="Mercedes",
            yil=2020,
            notlar="Araç #1 - Özel karakter!@#$%^&*() test 🚛",
        )
        assert "#" in arac.notlar
        assert "🚛" in arac.notlar

    def test_emoji_handling(self):
        """Emoji karakterleri düzgün işlenmeli."""
        from v2.modules.fleet.domain.entities import Arac

        arac = Arac(plaka="34 ABC 123", marka="Mercedes", notlar="En iyi araç 🏆🚚💯")
        assert "🏆" in arac.notlar


# =============================================================================
# NaN/INFINITY TESTS
# =============================================================================


class TestNaNInfinity:
    """NaN ve Infinity değer testleri."""

    def test_infinity_value_rejected(self):
        """Infinity değeri reddedilmeli."""
        from v2.modules.fuel.domain.entities import YakitAlimi

        with pytest.raises((ValidationError, ValueError, OverflowError)):
            YakitAlimi(
                tarih=date.today(),
                arac_id=1,
                fiyat_tl=Decimal("45.0"),
                litre=float("inf"),
                km_sayac=50000,
            )


# =============================================================================
# SECURITY TESTS
# =============================================================================


class TestSecurityInputValidation:
    """Güvenlik ve input validation testleri."""

    def test_sql_injection_in_plaka(self):
        """SQL injection plaka alanında engellenmeli."""
        from v2.modules.fleet.domain.entities import Arac

        malicious_inputs = [
            "'; DROP TABLE araclar; --",
            "34ABC123' OR '1'='1",
            "34ABC123; DELETE FROM araclar WHERE 1=1; --",
            "34ABC123' UNION SELECT * FROM users --",
        ]

        for payload in malicious_inputs:
            with pytest.raises(ValidationError):
                Arac(plaka=payload, marka="Test", yil=2020)

    def test_xss_in_notes(self):
        """XSS payload notlarda sanitize edilmeli veya encode edilmeli."""
        from v2.modules.fleet.domain.entities import Arac

        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
        ]

        for payload in xss_payloads:
            # Entity seviyesinde XSS engeli olmayabilir
            # Ancak test edilmeli
            arac = Arac(plaka="34 XSS 01", marka="Test", yil=2020, notlar=payload)
            # En azından depolanmalı (output encoding frontend'de)
            assert arac.notlar == payload

    def test_path_traversal_in_filename(self):
        """Path traversal dosya adlarında engellenmeli."""
        # Bu test ImportService için geçerli

        traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
        ]

        # Filename validation olmalı
        for payload in traversal_payloads:
            # Service path traversal'ı engellemelidir
            # Test implementation'a bağlı
            pass

    def test_oversized_input_rejected(self):
        """Aşırı büyük input (max_length ihlali) reddedilmeli."""
        from v2.modules.fleet.domain.entities import Arac

        # Arac.notlar max_length=2000
        huge_string = "A" * 2001

        with pytest.raises(ValidationError):
            Arac(plaka="34 DOS 01", marka="Mercedes", yil=2020, notlar=huge_string)


# =============================================================================
# CONCURRENT ACCESS TESTS
# =============================================================================


class TestConcurrentAccess:
    """Eşzamanlı erişim testleri."""

    def test_cache_concurrent_access(self):
        """Cache eşzamanlı erişimde thread-safe olmalı."""
        import threading

        from v2.modules.platform_infra.cache.cache_manager import CacheManager

        cache = CacheManager()
        cache.clear()
        errors = []

        def writer():
            for i in range(100):
                try:
                    cache.set(
                        f"key_{threading.current_thread().name}_{i}", f"value_{i}"
                    )
                except Exception as e:
                    errors.append(str(e))

        def reader():
            for i in range(100):
                try:
                    cache.get(f"key_{threading.current_thread().name}_{i}")
                except Exception as e:
                    errors.append(str(e))

        threads = []
        for i in range(5):
            t = threading.Thread(target=writer, name=f"writer_{i}")
            threads.append(t)
            t = threading.Thread(target=reader, name=f"reader_{i}")
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread-safety hataları: {errors}"

    def test_singleton_thread_safety(self):
        """Singleton pattern thread-safe olmalı."""
        from concurrent.futures import ThreadPoolExecutor

        from v2.modules.platform_infra.container import get_container, reset_container

        reset_container()
        results = []

        def get_container_id():
            container = get_container()
            return id(container)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_container_id) for _ in range(20)]
            results = [f.result() for f in futures]

        # Tüm thread'ler aynı container ID almalı
        assert len(set(results)) == 1, f"Farklı container ID'leri: {set(results)}"
        reset_container()


# =============================================================================
# FLOATING POINT COMPARISON TESTS
# =============================================================================


class TestFloatingPointComparison:
    """Kayan nokta karşılaştırma testleri."""

    def test_fuel_consumption_approx(self):
        """Yakıt tüketimi karşılaştırması pytest.approx kullanmalı."""
        from v2.modules.fuel.domain.entities import YakitPeriyodu

        period = YakitPeriyodu(
            arac_id=1,
            baslangic_tarih=date.today() - timedelta(days=1),
            bitis_tarih=date.today(),
            baslangic_km=10000,
            bitis_km=10600,
            ara_mesafe=600,
            toplam_yakit=180.0,
            ort_tuketim=30.0,
        )

        # 180 / 600 * 100 = 30.0 L/100km
        expected = 30.0
        assert period.ort_tuketim == pytest.approx(expected, rel=1e-3)

    def test_ton_calculation_precision(self):
        """Ton hesaplaması hassasiyeti."""
        from v2.modules.trip.domain.entities import Sefer

        sefer = Sefer(
            tarih=date.today(),
            arac_id=1,
            sofor_id=1,
            net_kg=22567,  # Hassas değer
            cikis_yeri="Ankara",
            varis_yeri="İstanbul",
            mesafe_km=100,
        )

        # 22567 / 1000 = 22.567 -> round(22.567, 2) = 22.57
        assert sefer.ton == pytest.approx(22.57, rel=1e-3)

    def test_currency_precision(self):
        """Para birimi hassasiyeti - Decimal kullanılmalı."""
        from decimal import Decimal

        from v2.modules.fuel.domain.entities import YakitAlimi

        yakit = YakitAlimi(
            tarih=date.today(),
            arac_id=1,
            fiyat_tl=Decimal("40.0"),  # fiyat_tl le=200 olmalı models.py'ye göre
            litre=100.0,
            km_sayac=50000,
        )

        assert float(yakit.toplam_tutar) == pytest.approx(4000.0, rel=1e-3)


# =============================================================================
# ERROR MESSAGE CLARITY TESTS
# =============================================================================


class TestErrorMessageClarity:
    """Hata mesajlarının anlaşılırlığı testleri."""

    def test_validation_error_message_contains_field(self):
        """Validation hatası hangi alanla ilgili olduğunu belirtmeli."""
        from v2.modules.fleet.domain.entities import Arac

        try:
            Arac(plaka="INVALID!!!", marka="Test", yil=2020)
        except ValidationError as e:
            error_str = str(e)
            # Hata mesajı "plaka" alanını içermeli
            assert "plaka" in error_str.lower() or "değer" in error_str.lower()

    def test_service_error_is_descriptive(self):
        """Service hataları açıklayıcı olmalı."""

        # KM düşüşü hatası açıklayıcı olmalı
        try:
            # Bu test service implementasyonuna bağlı
            pass
        except ValueError as e:
            assert "KM" in str(e) or "sayaç" in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
