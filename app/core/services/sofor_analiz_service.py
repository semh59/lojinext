"""
TIR Yakıt Takip Sistemi - Şoför Analiz Servisi (Faz 3)
Şoför performans analizi, karşılaştırma ve trend hesaplama

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: Şoför analiz servisi — performans metrikleri, read-heavy.
CREATED_BY: app/core/container.py (lazy property)
"""

import asyncio
import math
from statistics import mean
from typing import Dict, List, Optional

from app.core.entities import DriverStats
from app.infrastructure.logging.logger import get_logger
from app.services.prediction_service import get_prediction_service

logger = get_logger(__name__)


class SoforAnalizService:
    """
    Şoför performans analiz servisi.

    Özellikler:
    - Şoför istatistikleri hesaplama
    - Şoför karşılaştırma (ranking)
    - Trend analizi (iyileşme/kötüleşme)
    - Güzergah bazlı performans
    - Performans puanı (0-100)
    """

    def __init__(self, uow=None):
        self._uow = uow

    @property
    def analiz_repo(self):
        if self._uow:
            return self._uow.analiz_repo
        from app.database.repositories.analiz_repo import get_analiz_repo

        return get_analiz_repo()

    @property
    def sofor_repo(self):
        if self._uow:
            return self._uow.sofor_repo
        from app.database.repositories.sofor_repo import get_sofor_repo

        return get_sofor_repo()

    @property
    def sefer_repo(self):
        if self._uow:
            return self._uow.sefer_repo
        from app.database.repositories.sefer_repo import get_sefer_repo

        return get_sefer_repo()

    async def get_driver_stats(
        self,
        sofor_id: int = None,
        baslangic: str = None,
        bitis: str = None,
        include_elite_score: bool = True,
        uow=None,
    ) -> List[DriverStats]:
        """
        Tüm şoförlerin veya tek şoförün istatistiklerini hesapla (Async).
        N+1 probleminden arındırılmış, optimize sürüm.
        """
        # Use the passed uow for this call only — do NOT mutate self._uow (singleton leak).
        effective_uow = uow or self._uow
        _analiz_repo = effective_uow.analiz_repo if effective_uow else self.analiz_repo
        _sofor_repo = effective_uow.sofor_repo if effective_uow else self.sofor_repo
        # AUDIT-105 doğrulama bulgusu: elite batch yolu effective_uow None iken
        # (singleton + include_elite_score=True) effective_uow.sefer_repo'ya
        # doğrudan erişip AttributeError veriyordu. Diğer iki repo gibi None-guard'lı
        # erişime çekildi (üretimde elite her zaman uow-bağlı; bu defansif tutarlılık).
        _sefer_repo = effective_uow.sefer_repo if effective_uow else self.sefer_repo

        # 1. Toplu veya tekil metrikleri çek
        if sofor_id is None:
            # Toplu çekim (No N+1)
            sefer_stats = await _analiz_repo.get_bulk_driver_metrics()
        else:
            # Tekil çekim (Sadece ilgili şoför)
            sefer_stats = await _sofor_repo.get_sefer_stats(sofor_id, baslangic, bitis)

        if not sefer_stats:
            return []

        # 2. Filo ortalaması (Async)
        filo_ort = await _analiz_repo.get_filo_ortalama_tuketim(baslangic, bitis)

        # 3. Elite skorları — tek batch DB çekimi, ardından sırayla puan hesapla.
        elite_score_map: Dict[int, Optional[float]] = {}
        if include_elite_score:
            sofor_ids = [stats["sofor_id"] for stats in sefer_stats]
            # N+1 eliminasyonu: tüm şoförlerin seferlerini tek sorguda çek.
            from app.config import settings as _s

            trips_by_driver = await _sefer_repo.get_recent_trips_batch(
                sofor_ids, limit_per_driver=_s.ELITE_SCORE_TRIP_LIMIT
            )

            for sid in sofor_ids:
                try:
                    score = await self._calc_elite_from_trips(
                        trips_by_driver.get(sid, [])
                    )
                    elite_score_map[sid] = score
                except Exception as exc:
                    logger.warning(
                        "Elite score calculation failed for driver %s: %s", sid, exc
                    )
                    elite_score_map[sid] = None
        else:
            # Skor hesaplamayı atla (Eğitim vb. toplu işlemler için)
            elite_score_map = {stats["sofor_id"]: None for stats in sefer_stats}

        # 4. Her şoför için verileri birleştir
        result = []

        for stats in sefer_stats:
            sid = stats["sofor_id"]
            ort_tuketim = stats["ort_tuketim"] or 0.0

            # Filo karşılaştırma (% fark)
            if filo_ort > 0 and ort_tuketim > 0:
                filo_karsilastirma = round(
                    ((filo_ort - ort_tuketim) / filo_ort) * 100, 1
                )
            else:
                filo_karsilastirma = 0.0

            # Elite score map'den al (paralel hesaplandı)
            elite_score = elite_score_map.get(sid)

            driver_stats = DriverStats(
                sofor_id=sid,
                ad_soyad=stats["ad_soyad"],
                toplam_sefer=stats["toplam_sefer"],
                toplam_km=stats["toplam_km"],
                toplam_ton=float(stats.get("toplam_ton", 0) or 0),
                bos_sefer_sayisi=stats.get("bos_sefer_sayisi", 0),
                toplam_yakit=round(stats.get("toplam_yakit", 0) or 0, 1),
                ort_tuketim=round(ort_tuketim, 2),
                en_iyi_tuketim=round(stats["en_iyi_tuketim"], 2)
                if stats.get("en_iyi_tuketim")
                else None,
                en_kotu_tuketim=round(stats["en_kotu_tuketim"], 2)
                if stats.get("en_kotu_tuketim")
                else None,
                filo_karsilastirma=filo_karsilastirma,
                performans_puani=elite_score,
                trend=stats.get("trend", "stable"),  # CTE'den gelebilir veya default
                guzergah_sayisi=stats.get("guzergah_sayisi", 0),
            )

            result.append(driver_stats)

        return result

    async def compare_drivers(self, sofor_ids: List[int] = None) -> Dict:
        """
        Şoförleri karşılaştır ve sırala (async).

        Args:
            sofor_ids: Karşılaştırılacak şoförler (None = tümü)

        Returns:
            {
                'en_verimli': DriverStats,
                'en_az_verimli': DriverStats,
                'filo_ortalama': float,
                'ranking': List[DriverStats]  # Sıralı (en iyiden kötüye)
            }
        """
        # Tüm şoförler (async)
        all_stats = await self.get_driver_stats()

        # Filtrele
        if sofor_ids:
            all_stats = [s for s in all_stats if s.sofor_id in sofor_ids]

        # Minimum sefer kontrolü (en az 5 sefer)
        valid_stats = [
            s for s in all_stats if s.toplam_sefer >= 5 and s.ort_tuketim > 0
        ]

        if not valid_stats:
            return {
                "en_verimli": None,
                "en_az_verimli": None,
                "filo_ortalama": 0.0,
                "ranking": [],
            }

        # Performans puanına göre sırala
        ranking = sorted(
            valid_stats, key=lambda x: x.performans_puani or 0.0, reverse=True
        )

        # Filo ortalaması (async)
        filo_ort = await self.analiz_repo.get_filo_ortalama_tuketim()

        return {
            "en_verimli": ranking[0] if ranking else None,
            "en_az_verimli": ranking[-1] if ranking else None,
            "filo_ortalama": filo_ort,
            "ranking": ranking,
        }

    async def get_driver_trend(self, sofor_id: int, window: int = 10) -> Dict:
        """
        Son N seferdeki trend analizi (async).

        Args:
            sofor_id: Şoför ID
            window: Analiz penceresi (son N sefer)

        Returns:
            {
                'trend': 'improving' | 'stable' | 'declining',
                'slope': float,
                'values': List[float],
                'moving_avg': List[float]
            }
        """
        # Async repo call
        tuketimler = await self.sofor_repo.get_yakit_tuketimi(
            sofor_id, limit=window * 2
        )
        values = [t["tuketim"] for t in reversed(tuketimler) if t.get("tuketim")]

        if len(values) < 5:
            return {
                "trend": "stable",
                "slope": 0.0,
                "values": values,
                "moving_avg": values,
            }

        trend = self.calculate_trend(values[-window:])

        # Hareketli ortalama
        moving_avg = []
        for i in range(len(values)):
            start = max(0, i - 2)
            end = i + 1
            moving_avg.append(round(mean(values[start:end]), 2))

        # Slope hesapla (basit lineer regresyon)
        n = len(values[-window:])
        if n >= 3:
            x_mean = (n - 1) / 2
            y_mean = mean(values[-window:])

            numerator = sum(
                (i - x_mean) * (values[-window:][i] - y_mean) for i in range(n)
            )
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            slope = numerator / denominator if denominator > 0 else 0
        else:
            slope = 0

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "values": values,
            "moving_avg": moving_avg,
        }

    async def get_route_performance(self, sofor_id: int) -> List[Dict]:
        """
        Güzergah bazlı performans (async).

        Args:
            sofor_id: Şoför ID

        Returns:
            [{
                'guzergah': str,
                'sefer_sayisi': int,
                'ort_tuketim': float,
                'en_iyi': float,
                'en_kotu': float,
                'fark': float  # Filo ortalamasına göre
            }]
        """
        # Async repo calls
        guzergahlar = await self.sofor_repo.get_guzergah_performansi(sofor_id)
        filo_ort = await self.analiz_repo.get_filo_ortalama_tuketim()

        result = []
        for g in guzergahlar:
            ort = g.get("ort_tuketim") or 0
            fark = (
                round(((filo_ort - ort) / filo_ort) * 100, 1)
                if filo_ort > 0 and ort > 0
                else 0
            )

            result.append(
                {
                    "guzergah": g["guzergah"],
                    "sefer_sayisi": g["sefer_sayisi"],
                    "toplam_km": g.get("toplam_km", 0),
                    "ort_tuketim": round(ort, 2),
                    "en_iyi": round(g.get("en_iyi") or 0, 2),
                    "en_kotu": round(g.get("en_kotu") or 0, 2),
                    "fark": fark,
                }
            )

        return result

    async def _calc_elite_from_trips(self, seferler: list) -> Optional[float]:
        """ML-deviation elite score (0–100) for the analytics dashboard.

        Scale: 0–100. Baseline 75 = exact match with ML prediction.
        Interpretation: >75 = driver consumes LESS than ML predicts (efficient),
        <75 = driver consumes MORE than ML predicts. Formula: +1.5 pts per 1%
        saving, -2.0 pts per 1% overage. Stored in `performans_puani` field.

        NOT comparable to: `calculate_performance_score` (fleet-average-based) or
        `calculate_hybrid_score` (0.1–2.0 ML correction factor).

        Batch path: pre-fetched trip list — DB-fetch part of
        `calculate_elite_performance_score` is skipped for N+1 prevention.
        """
        if not seferler:
            return None
        pred_service = get_prediction_service()
        sem = asyncio.Semaphore(5)

        async def safe_predict(trip):
            async with sem:
                try:
                    actual = trip.get("tuketim")
                    if not actual or actual <= 0:
                        return None
                    pred = await pred_service.predict_consumption(
                        arac_id=trip["arac_id"],
                        mesafe_km=trip["mesafe_km"],
                        ton=float(trip.get("net_kg", 0)) / 1000.0,
                        ascent_m=trip.get("ascent_m", 0),
                        descent_m=trip.get("descent_m", 0),
                        sofor_id=trip.get("sofor_id"),
                    )
                    expected = pred.get("prediction_l_100km", 0)
                    if expected <= 0:
                        return None
                    return ((actual - expected) / expected) * 100
                except Exception as e:
                    logger.warning("Predict failed for elite score: %s", e)
                    return None

        results = await asyncio.gather(*[safe_predict(t) for t in seferler])
        deviations = [r for r in results if r is not None]
        if not deviations:
            return None
        avg_dev = mean(deviations)
        if avg_dev < 0:
            score = 75 + (abs(avg_dev) * 1.5)
        else:
            score = 75 - (avg_dev * 2.0)
        return round(max(0, min(100, score)), 1)

    async def calculate_elite_performance_score(
        self, sofor_id: int, baslangic: str = None, bitis: str = None, uow=None
    ) -> Optional[float]:
        """
        Elite Puanlama Algoritması.
        Sadece filo ortalaması değil, her sefer için 'Elite Prediction' ile 'Gerçek' arasındaki farkı baz alır.
        Bu sayede zor güzergahta çalışan şoför cezalandırılmaz.
        """
        from app.config import settings
        from app.database.repositories.sefer_repo import get_sefer_repo

        effective_uow = uow or self._uow
        sefer_repo = effective_uow.sefer_repo if effective_uow else get_sefer_repo()

        # Son N seferi çek (Config'den alınır)
        trip_limit = settings.ELITE_SCORE_TRIP_LIMIT
        seferler = await sefer_repo.get_all(
            filters={"sofor_id": sofor_id}, limit=trip_limit
        )
        if not seferler:
            return None

        pred_service = get_prediction_service()
        # FAZ 2.2: Paralel tahmin hesaplama (Semaphore ile limitli)
        sem = asyncio.Semaphore(5)

        async def safe_predict(trip):
            async with sem:
                try:
                    actual = trip.get("tuketim")
                    if not actual or actual <= 0:
                        return None

                    pred = await pred_service.predict_consumption(
                        arac_id=trip["arac_id"],
                        mesafe_km=trip["mesafe_km"],
                        ton=float(trip.get("net_kg", 0)) / 1000.0,
                        ascent_m=trip.get("ascent_m", 0),
                        descent_m=trip.get("descent_m", 0),
                        sofor_id=sofor_id,
                    )

                    expected = pred.get("prediction_l_100km", 0)
                    if expected <= 0:
                        return None

                    return ((actual - expected) / expected) * 100
                except Exception as e:
                    logger.warning(f"Predict failed for elite score: {e}")
                    return None

        # Paralel çalıştır
        results = await asyncio.gather(*[safe_predict(t) for t in seferler])
        deviations = [r for r in results if r is not None]

        if not deviations:
            return None

        avg_dev = mean(deviations)

        # Puanlama:
        # Nötr (0 sapma) = 75 puan
        # %1 Tasarruf = +1.5 puan
        # %1 Agresif = -2.0 puan (Cezalandırma daha sert)

        if avg_dev < 0:
            score = 75 + (abs(avg_dev) * 1.5)
        else:
            score = 75 - (avg_dev * 2.0)

        return round(max(0, min(100, score)), 1)

    def calculate_performance_score(
        self, ort_tuketim: float, filo_ort: float, sefer_sayisi: int
    ) -> float:
        """Fleet-comparison performance score (0–100) for report generation.

        Scale: 0–100. Baseline 50 = fleet average.
        Interpretation: >50 = below-average consumption (efficient), <50 = above-average.
        Used by `report_service` for driver reports — NOT used in the analytics dashboard
        (which uses the ML-deviation elite score via `_calc_elite_from_trips`).

        NOT comparable to: `calculate_hybrid_score` (0.1–2.0 ML factor) or the
        target-vs-actual score in `report_service._calculate_performance_score`.
        """
        if ort_tuketim <= 0 or filo_ort <= 0:
            return 50.0  # Yeterli veri yok

        # Filo karşılaştırma bonusu (%1 fark = 2 puan)
        fark_puan = ((filo_ort - ort_tuketim) / filo_ort) * 200

        # Sefer bonusu (log scale)
        sefer_bonus = min(10, math.log10(max(1, sefer_sayisi)) * 5)

        # Toplam puan
        puan = 50 + fark_puan + sefer_bonus

        # Sınırla
        return round(max(0, min(100, puan)), 1)

    def calculate_trend(self, values: List[float]) -> str:
        """
        Trend yönü hesapla.

        Args:
            values: Tüketim değerleri (kronolojik sıra)

        Returns:
            'improving' | 'stable' | 'declining'
        """
        if len(values) < 5:
            return "stable"

        # İlk ve son yarı ortalamaları
        mid = len(values) // 2
        first_half = mean(values[:mid])
        second_half = mean(values[mid:])

        # Fark yüzdesi
        if first_half > 0:
            change = ((second_half - first_half) / first_half) * 100
        else:
            return "stable"

        # Eşikler: %5'ten fazla değişim = trend
        if change < -5:
            return "improving"  # Tüketim azalıyor = iyi
        elif change > 5:
            return "declining"  # Tüketim artıyor = kötü
        else:
            return "stable"


def get_sofor_analiz_service() -> SoforAnalizService:
    from app.core.container import get_container

    return get_container().sofor_analiz_service
