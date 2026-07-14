"""
TIR Yakıt Takip Sistemi - Faz 3 Şoför Analiz Testleri (Async & Pytest)
v2.modules.driver.domain.driver_stats free function'ları için entegrasyon
ve birim testleri.

NOT: eski ``SoforAnalizService`` sınıfı silindi (B.1 free-function split,
bkz. v2/modules/driver/CLAUDE.md). Testler artık ilgili free function'ları
``uow=`` ile mock'lu bir UnitOfWork geçirerek çağırır.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.entities.models import DriverStats
from v2.modules.driver.domain import driver_stats as driver_stats_mod
from v2.modules.driver.domain.driver_stats import (
    calculate_performance_score,
    calculate_trend,
    compare_drivers,
    get_driver_stats,
)


class TestDriverStatsEntity:
    """DriverStats entity testleri"""

    def test_driver_stats_creation(self):
        """DriverStats entity oluşturma"""
        stats = DriverStats(
            sofor_id=1,
            ad_soyad="Ahmet Yılmaz",
            toplam_sefer=50,
            toplam_km=25000,
            toplam_ton=1200.5,
            bos_sefer_sayisi=10,
            toplam_yakit=8500.0,
            ort_tuketim=34.0,
            en_iyi_tuketim=28.5,
            en_kotu_tuketim=42.0,
            filo_karsilastirma=5.2,
            performans_puani=78.5,
            trend="improving",
            en_cok_gidilen_guzergah="Gebze → Ankara",
            guzergah_sayisi=8,
        )

        assert stats.sofor_id == 1
        assert stats.ad_soyad == "Ahmet Yılmaz"
        assert stats.toplam_sefer == 50
        assert stats.toplam_km == 25000
        assert stats.ort_tuketim == 34.0
        assert stats.trend == "improving"

    def test_driver_stats_defaults(self):
        """DriverStats varsayılan değerler"""
        stats = DriverStats(sofor_id=1, ad_soyad="Test Şoför")

        assert stats.toplam_sefer == 0
        assert stats.toplam_km == 0
        assert stats.ort_tuketim == 0.0
        assert stats.trend == "stable"
        assert stats.en_iyi_tuketim is None


class TestDriverStatsFreeFunctions:
    """v2.modules.driver.domain.driver_stats birim testleri"""

    @pytest.fixture
    def mock_uow(self):
        mock_sofor = AsyncMock()
        mock_analiz = AsyncMock()
        # AUDIT-045 refactor: elite skor get_recent_trips_batch yolundan gelir.
        mock_sefer = AsyncMock()
        mock_sefer.get_recent_trips_batch = AsyncMock(return_value={})

        uow = MagicMock()
        uow.sofor_repo = mock_sofor
        uow.analiz_repo = mock_analiz
        uow.sefer_repo = mock_sefer
        return uow

    def test_calculate_performance_score_average(self):
        """Performans puanı - filo ortalamasında"""
        score = calculate_performance_score(
            ort_tuketim=35.0, filo_ort=35.0, sefer_sayisi=10
        )
        assert 50 < score < 65

    def test_calculate_performance_score_better(self):
        """Performans puanı - filo ortalamasından iyi"""
        score = calculate_performance_score(
            ort_tuketim=30.0, filo_ort=35.0, sefer_sayisi=20
        )
        assert score > 70

    def test_calculate_trend_improving(self):
        """Trend analizi - iyileşme"""
        values = [40, 39, 38, 37, 36, 35, 34, 33, 32, 31]
        trend = calculate_trend(values)
        assert trend == "improving"

    @pytest.mark.asyncio
    async def test_get_driver_stats_empty(self, mock_uow):
        """Şoför istatistikleri - boş veri"""
        mock_uow.sofor_repo.get_sefer_stats.return_value = []
        # Bulk query used for None id
        mock_uow.analiz_repo.get_bulk_driver_metrics = AsyncMock(return_value=[])
        result = await get_driver_stats(uow=mock_uow)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_driver_stats_with_data(self, mock_uow):
        """Şoför istatistikleri - veri ile"""
        mock_uow.sofor_repo.get_sefer_stats.return_value = [
            {
                "sofor_id": 1,
                "ad_soyad": "Test Şoför",
                "toplam_sefer": 20,
                "toplam_km": 10000,
                "toplam_ton": 500.0,
                "ort_tuketim": 32.0,
                "en_iyi_tuketim": 28.0,
                "en_kotu_tuketim": 36.0,
                "bos_sefer_sayisi": 5,
            }
        ]

        mock_uow.analiz_repo.get_filo_ortalama_tuketim.return_value = 35.0
        mock_uow.sofor_repo.get_yakit_tuketimi.return_value = []  # for trend
        mock_uow.sofor_repo.get_guzergah_performansi.return_value = []

        # AUDIT-045 refactor: elite skor _calc_elite_from_trips ile hesaplanır.
        with patch.object(
            driver_stats_mod, "_calc_elite_from_trips", new_callable=AsyncMock
        ) as mock_elite:
            mock_elite.return_value = 85.0

            result = await get_driver_stats(sofor_id=1, uow=mock_uow)

            assert len(result) == 1
            assert result[0].sofor_id == 1
            assert result[0].ad_soyad == "Test Şoför"
            assert result[0].performans_puani == 85.0

    @pytest.mark.asyncio
    async def test_compare_drivers_ranking(self, mock_uow):
        """Şoför karşılaştırma - sıralama"""
        # get_driver_stats returns a list of DriverStats
        with patch.object(
            driver_stats_mod, "get_driver_stats", new_callable=AsyncMock
        ) as mock_stats:
            mock_stats.return_value = [
                DriverStats(
                    sofor_id=1,
                    ad_soyad="A",
                    performans_puani=90,
                    toplam_sefer=10,
                    ort_tuketim=30,
                    toplam_km=1000,
                ),
                DriverStats(
                    sofor_id=2,
                    ad_soyad="B",
                    performans_puani=70,
                    toplam_sefer=10,
                    ort_tuketim=35,
                    toplam_km=1000,
                ),
            ]

            mock_uow.analiz_repo.get_filo_ortalama_tuketim.return_value = 32.0

            result = await compare_drivers(uow=mock_uow)

            # Mock verification
            mock_stats.assert_called_once()

            assert result["en_verimli"].sofor_id == 1
            assert result["en_az_verimli"].sofor_id == 2
            assert len(result["ranking"]) == 2
