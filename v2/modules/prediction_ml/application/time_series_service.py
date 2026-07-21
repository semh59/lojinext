"""Time-series forecasting service for fuel analytics.

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: ARIMA zaman serisi tahmini — model başlangıçta başlatılır.
CREATED_BY: app/core/container.py (lazy property)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.infrastructure.logging.logger import get_logger
from v2.modules.prediction_ml.domain.advanced_lstm import (
    FORECAST_DAYS as _DEFAULT_FORECAST_DAYS,
)
from v2.modules.prediction_ml.domain.advanced_lstm import (
    ForecastResult,
    get_advanced_ts_engine,
)

logger = get_logger(__name__)


class TimeSeriesDataUnavailable(RuntimeError):
    """Raised when the analytics repository fails to deliver daily summary rows.

    Distinguishes a real upstream failure from "no rows yet" — callers convert
    this into a SERVICE_UNAVAILABLE response so clients see degraded service,
    not the misleading PRECONDITION_NOT_MET (insufficient data) signal.
    """


class TimeSeriesService:
    """Provide training, forecasting, and trend analysis for daily fuel summaries."""

    MIN_TRAINING_DAYS = 42  # SEQ_LEN(30) + FORECAST_DAYS(7) + 5 margin
    MIN_FORECAST_DAYS = 3  # EMA works with 3 days
    MIN_TREND_DAYS = 7

    def __init__(self) -> None:
        self.engine = get_advanced_ts_engine()

    @staticmethod
    def _failure(
        *,
        error_code: str,
        error_message: str,
        status_code: int,
        **extra: Any,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "success": False,
            "error_code": error_code,
            "error": error_message,
            "status_code": status_code,
        }
        payload.update(extra)
        return payload

    @staticmethod
    def _to_engine_records(daily_data: List[Dict[str, Any]]) -> List[Dict]:
        """Convert repository daily-summary format to AdvancedTSEngine format."""
        return [
            {
                "date": row.get("tarih"),
                "consumption": float(row.get("ort_tuketim") or 0.0),
                "km": float(row.get("toplam_km") or 0.0),
                "ton": float(row.get("ort_ton") or 0.0),
                "trips": int(row.get("sefer_sayisi") or 0),
            }
            for row in daily_data
        ]

    async def get_daily_summary(
        self, arac_id: Optional[int] = None, days: int = 90
    ) -> List[Dict[str, Any]]:
        """Return daily aggregates from the analytics repository."""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        days = max(1, min(int(days), 365))

        try:
            async with UnitOfWork() as uow:
                rows = await uow.analiz_repo.get_daily_summary_for_ml(
                    days=days,
                    arac_id=arac_id,
                )
            return [
                {
                    "tarih": row.get("tarih"),
                    "ort_tuketim": float(row.get("ort_tuketim") or 0),
                    "toplam_km": float(row.get("toplam_km") or 0),
                    "ort_ton": float(row.get("ort_ton") or 0),
                    "sefer_sayisi": int(row.get("sefer_sayisi") or 0),
                }
                for row in rows
            ]
        except Exception as exc:
            logger.warning(
                "Daily summary read failed; surfacing as degraded service. "
                "arac_id=%s days=%s error=%s",
                arac_id,
                days,
                exc,
            )
            raise TimeSeriesDataUnavailable(
                f"Daily summary repository unavailable: {exc}"
            ) from exc

    def _filter_outliers(
        self, data: List[Dict[str, Any]], threshold: float = 3.0
    ) -> List[Dict[str, Any]]:
        """Remove extreme outliers with a simple z-score filter."""
        if len(data) < 10:
            return data

        import numpy as np

        consumptions = np.array([d["ort_tuketim"] for d in data])
        mean = np.mean(consumptions)
        std = np.std(consumptions)

        if std == 0:
            return data

        filtered = []
        for item in data:
            z_score = abs(item["ort_tuketim"] - mean) / std
            if z_score <= threshold:
                filtered.append(item)

        removed = len(data) - len(filtered)
        if removed > 0:
            logger.info("Filtered %s outliers from time-series data.", removed)

        return filtered

    async def train_model(
        self, arac_id: Optional[int] = None, days: int = 180, epochs: int = 100
    ) -> Dict[str, Any]:
        """Train the advanced TS engine using repository-backed daily aggregates."""
        import asyncio

        try:
            daily_data = await self.get_daily_summary(arac_id, days)
        except TimeSeriesDataUnavailable as exc:
            return self._failure(
                error_code="SERVICE_UNAVAILABLE",
                error_message=str(exc),
                status_code=503,
                is_degraded=True,
            )

        daily_data = await asyncio.to_thread(self._filter_outliers, daily_data)

        if len(daily_data) < self.MIN_TRAINING_DAYS:
            return self._failure(
                error_code="PRECONDITION_NOT_MET",
                error_message=(
                    f"At least {self.MIN_TRAINING_DAYS} days of daily summary data are "
                    f"required, received {len(daily_data)}."
                ),
                status_code=409,
            )

        records = self._to_engine_records(daily_data)
        result = await asyncio.to_thread(self.engine.train, records)

        if result.get("success"):
            scope = f"vehicle {arac_id}" if arac_id else "fleet"
            logger.info("Advanced TS engine trained for %s.", scope)

        result["success"] = result.get("success", False)
        return result

    async def predict_weekly(self, arac_id: Optional[int] = None) -> Dict[str, Any]:
        """Return weekly forecast using the AdvancedTSEngine."""
        import asyncio
        from datetime import date, timedelta

        try:
            daily_data = await self.get_daily_summary(arac_id, days=120)
        except TimeSeriesDataUnavailable as exc:
            return self._failure(
                error_code="SERVICE_UNAVAILABLE",
                error_message=str(exc),
                status_code=503,
                vehicle_id=arac_id,
                is_degraded=True,
            )

        if len(daily_data) < self.MIN_FORECAST_DAYS and arac_id is not None:
            logger.info(
                "Vehicle %s has insufficient data for time-series forecasting; "
                "falling back to fleet-wide aggregates.",
                arac_id,
            )
            fleet_result = await self.predict_weekly(arac_id=None)
            if not fleet_result.get("success"):
                fleet_result["fallback_vehicle_id"] = arac_id
            return fleet_result

        if len(daily_data) < self.MIN_FORECAST_DAYS:
            return self._failure(
                error_code="PRECONDITION_NOT_MET",
                error_message=(
                    f"At least {self.MIN_FORECAST_DAYS} daily aggregates are required "
                    f"for forecasting, received {len(daily_data)}."
                ),
                status_code=409,
                vehicle_id=arac_id,
            )

        records = self._to_engine_records(daily_data)

        try:
            result: ForecastResult = await asyncio.to_thread(
                self.engine.forecast, records, _DEFAULT_FORECAST_DAYS
            )
        except Exception as exc:
            logger.warning("Advanced TS forecast failed: %s", exc)
            return self._failure(
                error_code="MODEL_EXECUTION_FAILED",
                error_message="Time-series forecast execution failed.",
                status_code=503,
                vehicle_id=arac_id,
            )

        if not result.success:
            return self._failure(
                error_code=result.error_code or "FORECAST_FAILED",
                error_message=result.error_message or "Forecast failed",
                status_code=409,
                vehicle_id=arac_id,
            )

        today = date.today()
        forecast_dates = [
            (today + timedelta(days=i + 1)).isoformat()
            for i in range(len(result.forecast))
        ]

        return {
            "success": True,
            "forecast": result.forecast,
            "forecast_dates": forecast_dates,
            "confidence_low": result.lower_95,
            "confidence_high": result.upper_95,
            "trend": result.trend,
            "method": result.method,
            "vehicle_id": arac_id,
            "input_days": result.input_days,
            "mae": result.mae,
            "is_deep_model": result.is_trained,
        }

    async def get_trend_analysis(
        self, arac_id: Optional[int] = None, days: int = 30
    ) -> Dict[str, Any]:
        """Analyze historical trend data using real daily aggregates only."""
        import numpy as np

        try:
            daily_data = await self.get_daily_summary(arac_id, days)
        except TimeSeriesDataUnavailable as exc:
            return self._failure(
                error_code="SERVICE_UNAVAILABLE",
                error_message=str(exc),
                status_code=503,
                vehicle_id=arac_id,
                is_degraded=True,
            )

        if len(daily_data) < self.MIN_TREND_DAYS:
            return self._failure(
                error_code="PRECONDITION_NOT_MET",
                error_message=(
                    f"At least {self.MIN_TREND_DAYS} daily aggregates are required "
                    f"for trend analysis, received {len(daily_data)}."
                ),
                status_code=409,
                vehicle_id=arac_id,
            )

        consumptions = [d.get("ort_tuketim", 32.0) for d in daily_data]
        total_consumptions = [
            round(
                d.get(
                    "toplam_litre",
                    (d.get("ort_tuketim", 0) * d.get("toplam_km", 0)) / 100.0,
                ),
                2,
            )
            for d in daily_data
        ]

        x = np.arange(len(consumptions))
        y = np.array(consumptions)

        slope = 0.0
        if len(x) > 1:
            slope = float(np.polyfit(x, y, 1)[0])

        if slope < -0.1:
            trend = "decreasing"
            trend_tr = "Azalıyor"
        elif slope > 0.1:
            trend = "increasing"
            trend_tr = "Artıyor"
        else:
            trend = "stable"
            trend_tr = "Sabit"

        moving_average_7 = (
            np.convolve(y, np.ones(7) / 7, mode="valid").tolist() if len(y) >= 7 else []
        )

        return {
            "success": True,
            "trend": trend,
            "trend_tr": trend_tr,
            "slope": round(slope, 4),
            "current_avg": round(float(np.mean(consumptions[-7:])), 2)
            if consumptions
            else 0,
            "previous_avg": round(float(np.mean(consumptions[:7])), 2)
            if len(consumptions) >= 14
            else None,
            "moving_average_7": [round(value, 2) for value in moving_average_7],
            "daily_values": consumptions,
            "daily_total_values": total_consumptions,
            "dates": [d.get("tarih") for d in daily_data],
            "days_analyzed": len(consumptions),
        }

    def get_model_status(self) -> Dict[str, Any]:
        """Return the current engine readiness status."""
        return self.engine.status()


def get_time_series_service() -> TimeSeriesService:
    from app.core.container import get_container

    return get_container().time_series_service
