"""
TIR Yakıt Takip Sistemi - Anomali Tespit Servisi
Z-Score ve IQR yöntemleri ile yakıt tüketim anomalilerini tespit eder ve araç istatistiklerini hesaplar.
"""

import asyncio
import threading
from statistics import mean, stdev
from typing import List, Optional

from app.core.entities import (
    AnomalyResult,
    AnomalyType,
    SeverityEnum,
    VehicleStats,
)
from app.infrastructure.cache.cache_manager import get_cache_manager
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors

logger = get_logger(__name__)


class AnomalyDetectionService:
    """Statistical anomaly detector for the analytics service layer.

    ARCHITECTURE NOTE — two anomaly subsystems exist intentionally:
    - This class (AnomalyDetectionService): pure Z-score + IQR, no ML,
      no DB writes. Used by analiz_service for in-memory fleet analytics.
    - AnomalyDetector (anomaly_detector.py): ML-augmented (LightGBM), persists
      Anomaly rows to DB, used by /anomalies endpoints and coaching engine.

    Threshold: resolved through runtime config (sistem_konfig row
    ANOMALY_Z_THRESHOLD, admin UI'dan ayarlanabilir; satır yoksa
    settings.ANOMALY_Z_THRESHOLD fallback) so both subsystems use the same
    configurable value. Callers can override per-call.
    """

    def __init__(self):
        self.cache = get_cache_manager()

    @monitor_errors(category="anomaly_detection", severity="error")
    async def detect_anomalies(
        self,
        consumptions: List[float],
        z_threshold: Optional[float] = None,
        use_iqr: bool = True,
    ) -> List[AnomalyResult]:
        """Z-Score ve IQR ile anomali tespiti (Async). Threshold: runtime config."""
        if z_threshold is None:
            from app.config import settings as _s
            from app.core.services.runtime_config import get_runtime_float

            z_threshold = await get_runtime_float(
                "ANOMALY_Z_THRESHOLD", _s.ANOMALY_Z_THRESHOLD
            )
        return await asyncio.to_thread(
            self._sync_detect_anomalies, consumptions, z_threshold, use_iqr
        )

    def _sync_detect_anomalies(
        self, consumptions: List[float], z_threshold: float = 2.5, use_iqr: bool = True
    ) -> List[AnomalyResult]:
        """Z-Score ve IQR ile anomali tespiti (Sync)"""
        # NaN/inf filtrele — statistics.mean/stdev ValueError fırlatır.
        # Üst katmandan gelmiş kirli veri ile crash etmek yerine sessizce geç.
        import math

        consumptions = [
            c for c in consumptions if isinstance(c, (int, float)) and math.isfinite(c)
        ]
        if len(consumptions) < 5:
            return []

        avg = mean(consumptions)
        std = stdev(consumptions) if len(consumptions) > 1 else 1
        z_scores = [(c - avg) / std if std > 0 else 0 for c in consumptions]

        sorted_c = sorted(consumptions)
        n = len(sorted_c)
        q1 = sorted_c[n // 4]
        q3 = sorted_c[3 * n // 4]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        anomalies = []
        for i, c in enumerate(consumptions):
            z = z_scores[i]
            is_z_anomaly = abs(z) > z_threshold
            is_iqr_anomaly = c < lower_bound or c > upper_bound
            deviation_pct = ((c - avg) / avg) * 100 if avg > 0 else 0.0

            severity = None
            message = ""

            if use_iqr:
                if is_z_anomaly and is_iqr_anomaly:
                    severity = (
                        SeverityEnum.CRITICAL if abs(z) > 3.5 else SeverityEnum.HIGH
                    )
                    message = f"{severity.value} anomali: {c:.1f} L/100km (Z={z:.2f})"
                elif is_z_anomaly or is_iqr_anomaly:
                    severity = SeverityEnum.MEDIUM
                    message = f"Orta anomali: {c:.1f} L/100km"
            else:
                if is_z_anomaly:
                    if abs(z) > 3.5:
                        severity = SeverityEnum.CRITICAL
                    elif abs(z) > 3.0:
                        severity = SeverityEnum.HIGH
                    else:
                        severity = SeverityEnum.MEDIUM
                    message = f"Anomali: {c:.1f} L/100km (Z={z:.2f})"

            if severity:
                anomalies.append(
                    AnomalyResult(
                        tip=AnomalyType.TUKETIM,
                        kaynak_tip="analiz",
                        kaynak_id=i,
                        deger=round(c, 2),
                        beklenen_deger=round(avg, 2),
                        sapma_yuzde=round(deviation_pct, 1),
                        severity=severity,
                        aciklama=message,
                        index=i,
                        z_score=round(z, 4),
                    )
                )

        return anomalies

    @monitor_errors(category="anomaly_detection", severity="error")
    async def analyze_vehicle_consumption(
        self, arac_id: int, consumptions: List[float]
    ) -> VehicleStats:
        """Araç tüketim analizi (Async - Structured Caching)"""
        n = len(consumptions)
        last = round(consumptions[-1], 3) if consumptions else 0
        cache_key = f"arac:{arac_id}:stats:n{n}:last{last}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        result = await asyncio.to_thread(
            self._sync_analyze_vehicle_consumption, arac_id, consumptions
        )
        self.cache.set(cache_key, result, ttl_seconds=3600)
        return result

    def _sync_analyze_vehicle_consumption(
        self, arac_id: int, consumptions: List[float]
    ) -> VehicleStats:
        """Araç tüketim analizi (Sync)"""
        import math

        # Pre-filter NaN/inf so indices produced by _sync_detect_anomalies (which
        # also filters internally) stay consistent with the list we enumerate below.
        valid_consumptions = [
            c for c in consumptions if isinstance(c, (int, float)) and math.isfinite(c)
        ]
        anomalies = self._sync_detect_anomalies(valid_consumptions)
        anomaly_indices = {
            a.index
            for a in anomalies
            if a.index is not None
            and a.severity in [SeverityEnum.HIGH, SeverityEnum.CRITICAL]
        }
        clean_consumptions = [
            c for i, c in enumerate(valid_consumptions) if i not in anomaly_indices
        ]

        avg_consumption = (
            mean(clean_consumptions)
            if clean_consumptions
            else (mean(valid_consumptions) if valid_consumptions else 0)
        )

        return VehicleStats(
            arac_id=arac_id,
            plaka="",
            ort_tuketim=round(avg_consumption, 2),
            toplam_sefer=len(consumptions),
            en_iyi_tuketim=min(valid_consumptions) if valid_consumptions else None,
            en_kotu_tuketim=max(valid_consumptions) if valid_consumptions else None,
            anomali_sayisi=len(anomalies),
            eei=self.calculate_eei(avg_consumption, 30.0),
        )

    def calculate_eei(
        self, actual_consumption: float, predicted_consumption: float
    ) -> float:
        """Energy Efficiency Index (EEI) hesaplar."""
        if not actual_consumption or actual_consumption <= 0:
            return 0.0
        if not predicted_consumption or predicted_consumption <= 0:
            return 100.0
        return round((predicted_consumption / actual_consumption) * 100, 1)


# Singleton
_anomaly_service: Optional[AnomalyDetectionService] = None
_anomaly_service_lock = threading.Lock()


def get_anomaly_detection_service() -> AnomalyDetectionService:
    global _anomaly_service
    if _anomaly_service is None:
        with _anomaly_service_lock:
            if _anomaly_service is None:
                _anomaly_service = AnomalyDetectionService()
    return _anomaly_service
