"""
TIR Yakıt Takip Sistemi - Analiz Servisi (Facade)
Gelişmiş analizleri koordine eden ana servis.
Bu servis artık fuel modülünün periyot use-case'lerine ve
AnomalyDetectionService'e delegasyon yapar.

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: Analiz servisi — dashboard istatistikleri, facade pattern.
CREATED_BY: app/core/container.py (lazy property)
"""

import threading
from statistics import mean
from typing import Any, List, Optional, TypedDict, cast

from app.core.entities import (
    AnomalyResult,
    Sefer,
    VehicleStats,
    YakitAlimi,
    YakitPeriyodu,
)
from app.core.services.anomaly_detection_service import get_anomaly_detection_service
from app.infrastructure.cache.cache_manager import get_cache_manager
from app.infrastructure.logging.logger import get_logger
from v2.modules.fuel.application.calculate_period import create_fuel_periods
from v2.modules.fuel.application.distribute_fuel_to_trips import (
    distribute_fuel_to_trips,
    match_periods_with_trips,
)
from v2.modules.fuel.application.recalculate_vehicle_periods import (
    recalculate_vehicle_periods,
)
from v2.modules.fuel.domain.period_matcher import PeriyotSeferMatch

logger = get_logger(__name__)


class TrendResult(TypedDict):
    slope: float
    direction: str
    strength: float


class RegressionResult(TypedDict):
    ortalama: float
    guvenilirlik: float
    toplam_km: int
    toplam_yakit: float


class AnalizService:
    """
    Analiz Servisi Facade.
    Mevcut metot imzalarını koruyarak iş mantığını alt servislere yönlendirir.
    """

    def __init__(self, yakit_repo=None, sefer_repo=None, arac_repo=None):
        # Repositories (DI and fallback)
        if yakit_repo:
            self.yakit_repo = yakit_repo
        else:
            from v2.modules.fuel.infrastructure.repository import get_yakit_repo

            self.yakit_repo = get_yakit_repo()

        if sefer_repo:
            self.sefer_repo = sefer_repo
        else:
            from app.database.repositories.sefer_repo import get_sefer_repo

            self.sefer_repo = get_sefer_repo()

        self.arac_repo = arac_repo
        self.cache = get_cache_manager()
        self.anomaly_service = get_anomaly_detection_service()

    # ============== DELEGATED METHODS ==============

    async def create_fuel_periods(
        self, fuel_records: List[YakitAlimi]
    ) -> List[YakitPeriyodu]:
        """Periyot oluşturmayı fuel modülünün use-case'ine delege eder."""
        return await create_fuel_periods(fuel_records)

    async def distribute_fuel_to_trips(
        self, period: YakitPeriyodu, trips: List[Sefer]
    ) -> List[Sefer]:
        """Yakıt dağıtımını fuel modülünün use-case'ine delege eder."""
        return await distribute_fuel_to_trips(period, trips)

    async def match_periods_with_trips(
        self, periods: List[YakitPeriyodu], all_trips: List[Sefer]
    ) -> List[PeriyotSeferMatch]:
        """Eşleştirmeyi fuel modülünün use-case'ine delege eder."""
        return await match_periods_with_trips(periods, all_trips)

    async def recalculate_vehicle_periods(self, arac_id: int):
        """Yeniden hesaplamayı fuel modülünün use-case'ine delege eder."""
        return await recalculate_vehicle_periods(
            arac_id, yakit_repo=self.yakit_repo, sefer_repo=self.sefer_repo
        )

    async def detect_anomalies(
        self,
        consumptions: List[float],
        z_threshold: Optional[float] = None,
        use_iqr: bool = True,
    ) -> List[AnomalyResult]:
        """Anomali tespitini AnomalyDetectionService'e delege eder.
        z_threshold=None → settings.ANOMALY_Z_THRESHOLD (AnomalyDetector ile aynı değer).
        """
        return await self.anomaly_service.detect_anomalies(
            consumptions, z_threshold, use_iqr
        )

    async def analyze_vehicle_consumption(
        self, arac_id: int, consumptions: List[float]
    ) -> VehicleStats:
        """Araç analizini AnomalyDetectionService'e delege eder."""
        return await self.anomaly_service.analyze_vehicle_consumption(
            arac_id, consumptions
        )

    def calculate_eei(
        self, actual_consumption: float, predicted_consumption: float
    ) -> float:
        """EEI hesabını AnomalyDetectionService'e delege eder."""
        return self.anomaly_service.calculate_eei(
            actual_consumption, predicted_consumption
        )

    # ============== CORE STATS LOGIC (In-house) ==============

    async def get_fleet_average(self, year: int, month: int) -> float:
        """Filo ortalaması (cached)."""
        cache_key = f"fleet:avg:{year}:{month}"
        cached_val = self.cache.get(cache_key)
        if cached_val is not None:
            return cached_val

        from app.database.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            val = await uow.analiz_repo.get_filo_ortalama_tuketim()
        self.cache.set(cache_key, val, ttl_seconds=3600)
        return val

    def calculate_moving_average(
        self, values: List[float], window: int = 5
    ) -> List[Optional[float]]:
        """Hareketli ortalama hesapla."""
        result: List[Any] = []
        for i in range(len(values)):
            if i < window - 1:
                result.append(None)
            else:
                window_values = values[i - window + 1 : i + 1]
                result.append(round(mean(window_values), 2))
        return result

    def calculate_trend(self, values: List[float]) -> TrendResult:
        """Trend analizi (basit lineer regresyon)."""
        if len(values) < 3:
            return {"slope": 0, "direction": "stable", "strength": 0}

        n = len(values)
        x = list(range(n))
        x_mean = mean(x)
        y_mean = mean(values)

        num = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((x[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den != 0 else 0

        direction = (
            "stable"
            if abs(slope) < 0.1
            else ("increasing" if slope > 0 else "decreasing")
        )

        ss_tot = sum((v - y_mean) ** 2 for v in values)
        y_pred = [y_mean + slope * (i - x_mean) for i in x]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return {
            "slope": round(slope, 4),
            "direction": direction,
            "strength": round(r_squared, 4),
        }

    async def calculate_long_term_stats(
        self, arac_id: int
    ) -> Optional[RegressionResult]:
        """Uzun dönem regresyon analizi."""
        cache_key = f"arac:{arac_id}:regression"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        raw = await self.yakit_repo.get_all(arac_id=arac_id, limit=1000, desc=False)
        # YakitRepository.get_all returns {"items": [...], "total": N}; unwrap defensively.
        alimlar = raw.get("items", raw) if isinstance(raw, dict) else raw
        if len(alimlar) < 3:
            return None

        x_data, y_data = [], []
        cum_liter: float = 0.0
        start_km = int(alimlar[0]["km_sayac"])

        for a in alimlar:
            cum_liter += float(a["litre"])
            dist = int(a["km_sayac"]) - start_km
            if dist > 0:
                x_data.append(dist)
                y_data.append(cum_liter)

        if len(x_data) < 3:
            return None

        n = len(x_data)
        x_mean, y_mean = sum(x_data) / n, sum(y_data) / n
        num = sum((x_data[i] - x_mean) * (y_data[i] - y_mean) for i in range(n))
        den = sum((x_data[i] - x_mean) ** 2 for i in range(n))
        if den == 0:
            return None

        slope = num / den
        r_sq = (
            (
                1
                - sum(
                    (y_data[i] - (y_mean + slope * (x_data[i] - x_mean))) ** 2
                    for i in range(n)
                )
                / sum((y - y_mean) ** 2 for y in y_data)
            )
            if sum((y - y_mean) ** 2 for y in y_data) > 0
            else 0
        )

        result = {
            "ortalama": round(slope * 100, 2),
            "guvenilirlik": round(r_sq * 100, 1),
            "toplam_km": x_data[-1],
            "toplam_yakit": cum_liter,
        }
        self.cache.set(cache_key, result, ttl_seconds=86400)
        return cast("RegressionResult", result)

    def clear_cache(self):
        """Tüm cache'i temizle"""
        self.cache.clear()


# Singleton Instance
_analiz_service: Optional[AnalizService] = None
_analiz_service_lock = threading.Lock()


def get_analiz_service() -> AnalizService:
    global _analiz_service
    if _analiz_service is None:
        with _analiz_service_lock:
            if _analiz_service is None:
                _analiz_service = AnalizService()
    return _analiz_service
