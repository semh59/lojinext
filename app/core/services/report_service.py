"""
Fleet reporting service.

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: Rapor servisi — analiz sorguları, read-only.
CREATED_BY: app/core/container.py (lazy property)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Optional

from app.core.utils.clock import current_date
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrendReport:
    """Trend report model."""

    period: str
    start_date: date
    end_date: date
    toplam_sefer: int
    toplam_km: int
    toplam_yakit: float
    ortalama_tuketim: float
    onceki_tuketim: Optional[float] = None
    tuketim_degisim: Optional[float] = None


class ReportService:
    """Async reporting facade."""

    def __init__(
        self,
        sefer_repo=None,
        yakit_repo=None,
        arac_repo=None,
        sofor_repo=None,
        analiz_repo=None,
        session=None,
    ):
        self._analiz_repo = analiz_repo
        self._degerlendirme_service = None

        if session is not None:
            from app.database.repositories.sefer_repo import SeferRepository
            from app.database.repositories.sofor_repo import SoforRepository
            from app.database.repositories.yakit_repo import YakitRepository
            from v2.modules.fleet.infrastructure.vehicle_repository import (
                AracRepository,
            )

            self.arac_repo = arac_repo or AracRepository(session=session)
            self.sofor_repo = sofor_repo or SoforRepository(session=session)
            self.sefer_repo = sefer_repo or SeferRepository(session=session)
            self.yakit_repo = yakit_repo or YakitRepository(session=session)
            if self._analiz_repo is None:
                from app.database.repositories.analiz_repo import get_analiz_repo

                self._analiz_repo = get_analiz_repo(session=session)
            return

        if arac_repo:
            self.arac_repo = arac_repo
        else:
            from v2.modules.fleet.infrastructure.vehicle_repository import (
                get_arac_repo,
            )

            self.arac_repo = get_arac_repo()

        if sofor_repo:
            self.sofor_repo = sofor_repo
        else:
            from app.database.repositories.sofor_repo import get_sofor_repo

            self.sofor_repo = get_sofor_repo()

        if sefer_repo:
            self.sefer_repo = sefer_repo
        else:
            from app.database.repositories.sefer_repo import get_sefer_repo

            self.sefer_repo = get_sefer_repo()

        if yakit_repo:
            self.yakit_repo = yakit_repo
        else:
            from app.database.repositories.yakit_repo import get_yakit_repo

            self.yakit_repo = get_yakit_repo()

        shared_session = None
        for repo in (self.arac_repo, self.sofor_repo, self.sefer_repo, self.yakit_repo):
            shared_session = getattr(repo, "_session", None)
            if shared_session is not None:
                break

        if shared_session is not None:
            from app.database.repositories.analiz_repo import get_analiz_repo

            try:
                self._analiz_repo = get_analiz_repo(session=shared_session)
            except TypeError:
                self._analiz_repo = get_analiz_repo()

    @property
    def analiz_repo(self):
        if self._analiz_repo is not None:
            return self._analiz_repo

        from app.database.repositories.analiz_repo import get_analiz_repo

        return get_analiz_repo()

    @property
    def degerlendirme_service(self):
        if self._degerlendirme_service is None:
            from app.core.entities.sofor_degerlendirme import SoforDegerlendirmeService

            self._degerlendirme_service = SoforDegerlendirmeService(
                analiz_repo=self.analiz_repo, sofor_repo=self.sofor_repo
            )
        return self._degerlendirme_service

    @staticmethod
    def _calculate_performance_score(
        actual_consumption: Optional[float], target_consumption: Optional[float]
    ) -> float:
        """Target-vs-actual consumption score (0–100) for report generation.

        Scale: 0–100. 100 = actual matches target exactly, decreases as actual
        exceeds target. Clamps at 0 (never negative). Distinct from the fleet-
        average score in `sofor_analiz_service.calculate_performance_score` and
        from the ML-deviation elite score — all three 0-100 scales are report-
        or dashboard-specific and are not interchangeable.
        """
        actual = float(actual_consumption or 0)
        target = float(target_consumption or 0)
        if actual <= 0 or target <= 0:
            return 0.0
        deviation_pct = ((actual - target) / target) * 100
        return round(max(0.0, min(100.0, 100.0 - max(0.0, deviation_pct))), 1)

    @staticmethod
    def _get_first_available(data: Dict, *keys, default=0):
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return default

    @staticmethod
    def _prefer_positive(primary, fallback):
        try:
            if float(primary) > 0:
                return primary
        except (TypeError, ValueError):
            if primary:
                return primary
        return fallback

    async def get_dashboard_summary(self, days: int = 30) -> Dict:
        summary = await self.generate_fleet_summary(days=days)
        return {
            "toplam_sefer": summary.get("total_trips", 0),
            "toplam_km": summary.get("total_distance", 0),
            "toplam_yakit": summary.get("total_fuel", 0),
            "filo_ortalama": summary.get("avg_consumption", 0),
            "toplam_harcama": summary.get("total_cost", 0),
            "toplam_arac": summary.get("total_vehicles", 0),
            "aktif_arac": summary.get("total_vehicles", 0),
        }

    async def get_monthly_comparison(self, year: int = None, month: int = None) -> Dict:
        trend = await self.generate_monthly_trend(year=year, month=month)
        changes = trend.get("degisimler", {})
        return {
            "sefer_degisim": changes.get("toplam_sefer_degisim", 0),
            "km_degisim": changes.get("toplam_km_degisim", 0),
            "tuketim_degisim": changes.get("ortalama_tuketim_degisim", 0),
            "yakit_degisim": changes.get("toplam_yakit_degisim", 0),
        }

    async def get_daily_consumption_trend(self, days: int = 30):
        return await self.analiz_repo.get_daily_consumption_series(days)

    async def generate_monthly_trend(self, year: int = None, month: int = None) -> Dict:
        today = current_date()
        year = year or today.year
        month = month or today.month

        bu_ay_bas = date(year, month, 1)
        if month == 12:
            bu_ay_son = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            bu_ay_son = date(year, month + 1, 1) - timedelta(days=1)

        gecen_ay_son = bu_ay_bas - timedelta(days=1)
        gecen_ay_bas = gecen_ay_son.replace(day=1)

        bu_ay_data = await self.analiz_repo.get_period_stats(bu_ay_bas, bu_ay_son)
        gecen_ay_data = await self.analiz_repo.get_period_stats(
            gecen_ay_bas, gecen_ay_son
        )

        degisimler = {}
        for key in ["toplam_sefer", "toplam_km", "toplam_yakit", "ortalama_tuketim"]:
            bu = bu_ay_data.get(key, 0) or 0
            gecen = gecen_ay_data.get(key, 0) or 0
            if gecen > 0:
                degisimler[f"{key}_degisim"] = round((bu - gecen) / gecen * 100, 1)
            else:
                degisimler[f"{key}_degisim"] = 0

        return {
            "donem": f"{year}-{month:02d}",
            "bu_ay": bu_ay_data,
            "gecen_ay": gecen_ay_data,
            "degisimler": degisimler,
        }

    async def generate_vehicle_report(
        self, arac_id: int, month: int = None, year: int = None, days: int = 30
    ) -> Dict:
        # Raporlar tarihsel veri okur — pasifleştirilmiş araç için de üretilebilmeli
        arac = await self.arac_repo.get_by_id(arac_id, include_inactive=True)
        if not arac:
            return {"error": "Arac bulunamadi"}

        if month and year:
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        else:
            end_date = current_date()
            start_date = end_date - timedelta(days=days)

        stats = await self.analiz_repo.get_vehicle_summary_stats(arac_id, start_date)
        gunluk = await self.analiz_repo.get_daily_consumption_series(days)
        guzergahlar = await self.analiz_repo.get_top_routes_by_vehicle(
            arac_id, start_date, limit=5
        )

        hedef_tuketim = arac.get(
            "hedef_tuketim", getattr(self.analiz_repo, "DEFAULT_FILO_ORTALAMA", 32.0)
        )
        return {
            "plaka": arac["plaka"],
            "marka": arac["marka"],
            "model": arac.get("model", ""),
            "hedef_tuketim": hedef_tuketim,
            "performance_score": self._calculate_performance_score(
                stats.get("ort_tuketim"),
                hedef_tuketim,
            ),
            "arac": arac,
            "donem": f"{month}/{year}" if month else f"Son {days} gun",
            "istatistikler": stats,
            "gunluk_trend": gunluk,
            "top_guzergahlar": guzergahlar,
        }

    async def generate_driver_report(self, sofor_id: int, days: int = 30) -> Dict:
        # Raporlar tarihsel veri okur — pasifleştirilmiş şoför için de üretilebilmeli
        sofor = await self.sofor_repo.get_by_id(sofor_id, include_inactive=True)
        if not sofor:
            return {"error": "Sofor bulunamadi"}

        degerlendirme = await self.degerlendirme_service.evaluate_driver(sofor_id)
        return {
            "sofor": sofor,
            "donem": f"Son {days} gun",
            "degerlendirme": degerlendirme.model_dump() if degerlendirme else None,
        }

    async def generate_fleet_summary(
        self, start_date: date = None, end_date: date = None, days: int = 30
    ) -> Dict:
        if not start_date:
            start_date = current_date() - timedelta(days=days)

        try:
            stats = await self.analiz_repo.get_fleet_performance_stats(start_date)
        except Exception:
            stats = {}
        yakit_stats = {}
        get_stats = getattr(self.yakit_repo, "get_stats", None)
        if callable(get_stats):
            try:
                yakit_stats = await get_stats(
                    baslangic_tarih=start_date,
                    bitis_tarih=end_date,
                )
            except Exception:
                yakit_stats = {}

        total_vehicles = self._get_first_available(
            stats, "total_vehicles", "toplam_arac", default=0
        )
        if total_vehicles == 0:
            count_all = getattr(self.arac_repo, "count_all", None)
            if callable(count_all):
                total_vehicles = await count_all()

        try:
            araclar = await self.analiz_repo.get_top_performing_vehicles(limit=15)
        except Exception:
            araclar = []
        total_distance = self._get_first_available(
            stats, "total_distance", "toplam_km", default=0
        )
        total_fuel = self._get_first_available(
            stats, "total_fuel", "toplam_yakit", default=0
        )
        avg_consumption = self._get_first_available(
            stats,
            "avg_consumption",
            "filo_ortalama",
            "ortalama_tuketim",
            default=0,
        )
        total_cost = self._get_first_available(
            stats, "total_cost", "toplam_harcama", default=0
        )

        total_distance = self._prefer_positive(
            total_distance,
            self._get_first_available(yakit_stats, "total_distance", default=0),
        )
        total_fuel = self._prefer_positive(
            total_fuel,
            self._get_first_available(yakit_stats, "total_consumption", default=0),
        )
        avg_consumption = self._prefer_positive(
            avg_consumption,
            self._get_first_available(yakit_stats, "avg_consumption", default=0),
        )
        total_cost = self._prefer_positive(
            total_cost,
            self._get_first_available(yakit_stats, "total_cost", default=0),
        )

        return {
            "donem": f"Son {days} gun"
            if not end_date
            else f"{start_date} - {end_date}",
            "genel": stats,
            "total_vehicles": total_vehicles,
            "total_trips": self._get_first_available(
                stats, "total_trips", "toplam_sefer", default=0
            ),
            "total_distance": total_distance,
            "total_fuel": total_fuel,
            "avg_consumption": avg_consumption,
            "total_cost": total_cost,
            "vehicle_performance": araclar,
        }


def get_report_service() -> ReportService:
    from app.core.container import get_container

    return get_container().report_service
