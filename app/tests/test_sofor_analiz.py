"""
TIR Yakıt Takip Sistemi - Faz 3 Şoför Analiz Testleri (Async & Pytest)
SoforAnalizService ve DB sorguları için entegrasyon ve birim testleri
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.entities.models import DriverStats
from app.core.services.sofor_analiz_service import SoforAnalizService


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


class TestSoforAnalizService:
    """SoforAnalizService birim testleri"""

    @pytest.fixture
    def service(self):
        return SoforAnalizService()

    @pytest.fixture
    def mock_repos(self, service, monkeypatch):
        mock_sofor = AsyncMock()
        mock_analiz = AsyncMock()
        # AUDIT-045 refactor: elite skor get_recent_trips_batch yolundan gelir.
        mock_sefer = AsyncMock()
        mock_sefer.get_recent_trips_batch = AsyncMock(return_value={})

        # Monkeypatch properties
        monkeypatch.setattr(
            SoforAnalizService, "sofor_repo", property(lambda self: mock_sofor)
        )
        monkeypatch.setattr(
            SoforAnalizService, "analiz_repo", property(lambda self: mock_analiz)
        )
        monkeypatch.setattr(
            SoforAnalizService, "sefer_repo", property(lambda self: mock_sefer)
        )

        return mock_sofor, mock_analiz

    def test_calculate_performance_score_average(self, service):
        """Performans puanı - filo ortalamasında"""
        score = service.calculate_performance_score(
            ort_tuketim=35.0, filo_ort=35.0, sefer_sayisi=10
        )
        assert 50 < score < 65

    def test_calculate_performance_score_better(self, service):
        """Performans puanı - filo ortalamasından iyi"""
        score = service.calculate_performance_score(
            ort_tuketim=30.0, filo_ort=35.0, sefer_sayisi=20
        )
        assert score > 70

    def test_calculate_trend_improving(self, service):
        """Trend analizi - iyileşme"""
        values = [40, 39, 38, 37, 36, 35, 34, 33, 32, 31]
        trend = service.calculate_trend(values)
        assert trend == "improving"

    @pytest.mark.asyncio
    async def test_get_driver_stats_empty(self, service, mock_repos):
        """Şoför istatistikleri - boş veri"""
        mock_sofor, _ = mock_repos
        mock_sofor.get_sefer_stats.return_value = []
        # Bulk query used for None id
        with patch.object(
            service.analiz_repo, "get_bulk_driver_metrics", new_callable=AsyncMock
        ) as mock_bulk:
            mock_bulk.return_value = []
            result = await service.get_driver_stats()
            assert result == []

    @pytest.mark.asyncio
    async def test_get_driver_stats_with_data(self, service, mock_repos):
        """Şoför istatistikleri - veri ile"""
        mock_sofor, mock_analiz = mock_repos

        # Mock DB responses
        mock_sofor.get_sefer_stats.return_value = [
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

        mock_analiz.get_filo_ortalama_tuketim.return_value = 35.0
        mock_sofor.get_yakit_tuketimi.return_value = []  # for trend
        mock_sofor.get_guzergah_performansi.return_value = []

        # AUDIT-045 refactor: elite skor _calc_elite_from_trips ile hesaplanır.
        with patch.object(
            service, "_calc_elite_from_trips", new_callable=AsyncMock
        ) as mock_elite:
            mock_elite.return_value = 85.0

            result = await service.get_driver_stats(sofor_id=1)

            assert len(result) == 1
            assert result[0].sofor_id == 1
            assert result[0].ad_soyad == "Test Şoför"
            assert result[0].performans_puani == 85.0

    @pytest.mark.asyncio
    async def test_compare_drivers_ranking(self, service, mock_repos):
        """Şoför karşılaştırma - sıralama"""
        mock_sofor, mock_analiz = mock_repos

        # get_driver_stats returns a list of DriverStats
        with patch.object(
            service, "get_driver_stats", new_callable=AsyncMock
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

            mock_analiz.get_filo_ortalama_tuketim.return_value = 32.0

            result = await service.compare_drivers()

            # Mock verification
            mock_stats.assert_called_once()

            assert result["en_verimli"].sofor_id == 1
            assert result["en_az_verimli"].sofor_id == 2
            assert len(result["ranking"]) == 2
