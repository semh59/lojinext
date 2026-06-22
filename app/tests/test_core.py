"""
TIR Yakıt Takip Sistemi - Unit Tests (Async & Pytest)
Pydantic entities, analiz servisi ve infrastructure testleri
"""

import pickle
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.entities import Arac, Sefer, YakitAlimi, YakitPeriyodu
from app.core.services.analiz_service import AnalizService
from app.infrastructure.cache.cache_manager import CacheManager, _sign
from app.infrastructure.events.event_bus import Event, EventBus, EventType


class TestAracEntity:
    """Araç entity testleri"""

    def test_valid_plaka_format(self):
        """Geçerli plaka formatlarını test et"""
        test_cases = [
            ("34ABC01", "34 ABC 01"),
            ("34 abc 01", "34 ABC 01"),
            ("06XYZ99", "06 XYZ 99"),
            ("01 A 1234", "01 A 1234"),
        ]

        for input_plaka, expected in test_cases:
            arac = Arac(plaka=input_plaka, marka="Mercedes", yil=2020)
            assert arac.plaka == expected

    def test_invalid_plaka_raises_error(self):
        """Geçersiz plaka formatı hata fırlatmalı"""
        with pytest.raises(ValueError):
            Arac(plaka="INVALID", marka="Mercedes", yil=2020)


class TestYakitAlimiEntity:
    """Yakıt alımı entity testleri"""

    def test_computed_toplam_tutar(self):
        """Toplam tutar otomatik hesaplanmalı"""
        yakit = YakitAlimi(
            tarih=date.today(), arac_id=1, fiyat_tl=43.50, litre=250, km_sayac=100000
        )
        assert yakit.toplam_tutar == 10875.0


class TestSeferEntity:
    """Sefer entity testleri"""

    def test_computed_ton(self):
        """Ton otomatik hesaplanmalı"""
        sefer = Sefer(
            tarih=date.today(),
            arac_id=1,
            sofor_id=1,
            net_kg=22500,
            cikis_yeri="Gebze",
            varis_yeri="Ankara",
            mesafe_km=450,
        )
        assert sefer.ton == 22.5


class TestAnalizService:
    """Analiz servisi testleri"""

    @pytest.fixture
    def service(self):
        return AnalizService()

    @pytest.mark.asyncio
    async def test_create_fuel_periods(self, service):
        """Periyot oluşturma testi"""
        fuel_records = [
            YakitAlimi(
                id=1,
                tarih=date(2024, 1, 1),
                arac_id=1,
                fiyat_tl=43,
                litre=200,
                km_sayac=100000,
                depo_durumu="dolu",
            ),
            YakitAlimi(
                id=2,
                tarih=date(2024, 1, 5),
                arac_id=1,
                fiyat_tl=44,
                litre=180,
                km_sayac=100600,
                depo_durumu="dolu",
            ),
            YakitAlimi(
                id=3,
                tarih=date(2024, 1, 10),
                arac_id=1,
                fiyat_tl=45,
                litre=220,
                km_sayac=101400,
                depo_durumu="dolu",
            ),
        ]

        periods = await service.create_fuel_periods(fuel_records)

        assert len(periods) == 2
        assert periods[0].ara_mesafe == 600
        assert periods[1].ara_mesafe == 800

    @pytest.mark.asyncio
    async def test_distribute_fuel_to_trips(self, service):
        """Yakıt dağıtımı testi"""
        period = YakitPeriyodu(
            id=1,
            arac_id=1,
            alim1_id=1,
            alim2_id=2,
            alim1_tarih=date(2024, 1, 1),
            alim1_km=100000,
            alim1_litre=200,
            alim2_tarih=date(2024, 1, 5),
            alim2_km=100600,
            ara_mesafe=600,
            toplam_yakit=180,
        )

        trips = [
            Sefer(
                id=1,
                tarih=date(2024, 1, 2),
                arac_id=1,
                sofor_id=1,
                net_kg=20000,
                cikis_yeri="Gebze",
                varis_yeri="Bursa",
                mesafe_km=300,
            ),
            Sefer(
                id=2,
                tarih=date(2024, 1, 3),
                arac_id=1,
                sofor_id=1,
                net_kg=18000,
                cikis_yeri="Bursa",
                varis_yeri="Gebze",
                mesafe_km=300,
            ),
        ]

        distributed = await service.distribute_fuel_to_trips(period, trips)

        assert distributed[0].dagitilan_yakit > 90.0
        assert distributed[1].dagitilan_yakit < 90.0
        assert (
            abs(distributed[0].dagitilan_yakit + distributed[1].dagitilan_yakit - 180.0)
            < 0.1
        )

    @pytest.mark.asyncio
    async def test_detect_anomalies(self, service):
        """Anomali tespiti testi"""
        consumptions = [30, 31, 32, 29, 30, 31, 33, 30, 55, 32]
        anomalies = await service.detect_anomalies(consumptions)
        assert len(anomalies) > 0
        assert any(a.value == 55 for a in anomalies)


class TestEventBus:
    """EventBus testleri"""

    @pytest.fixture
    def bus(self):
        bus = EventBus()
        # Clean state before test
        bus._subscribers.clear()
        bus.clear_history()

        yield bus

        # Clean state after test
        bus._subscribers.clear()
        bus.clear_history()

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, bus):
        """Abone ol ve olay yayınla"""
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe(EventType.YAKIT_ADDED, handler)
        await bus.publish_async(Event(type=EventType.YAKIT_ADDED, data={"test": 1}))

        assert len(received) == 1
        assert received[0].data["test"] == 1


class TestCacheManager:
    """CacheManager testleri"""

    @pytest.fixture
    def mock_redis(self):
        r = MagicMock()
        r.get.return_value = None
        r.scan_iter.return_value = iter([])
        return r

    @pytest.fixture
    def cache(self, mock_redis):
        # Setup: Reset singleton and inject mock Redis
        with patch("redis.from_url", return_value=mock_redis):
            CacheManager._instance = None
            c = CacheManager()
        c._redis = mock_redis
        yield c
        # Teardown: Reset singleton
        CacheManager._instance = None

    def test_set_and_get(self, cache, mock_redis):
        """Set ve get temel işlevsellik"""
        cache.set("key1", "value1")
        # Simulate round-trip: get returns the signed+pickled value
        mock_redis.get.return_value = _sign(pickle.dumps("value1"))
        assert cache.get("key1") == "value1"

    def test_cache_miss(self, cache, mock_redis):
        """Olmayan anahtar None döndürmeli"""
        mock_redis.get.return_value = None
        assert cache.get("nonexistent") is None

    def test_delete(self, cache, mock_redis):
        """Silme işlemi"""
        cache.set("key1", "value1")
        mock_redis.delete.return_value = 1
        assert cache.delete("key1") is True
        # Simulate key gone after delete
        mock_redis.get.return_value = None
        assert cache.get("key1") is None
