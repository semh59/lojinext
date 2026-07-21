"""Şoför Değerlendirme Sistemi — kapsamlı puanlama ve performans karnesi.

Free functions (B.1 — no ``SoforDegerlendirmeService`` class). The
pre-migration class's constructor required ``analiz_repo``/``sofor_repo``
(no meaningful state beyond that) — every function below takes an optional
``uow`` and falls back to module-level singletons, same shape as
``domain/driver_stats.py``.
"""

import math
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field, computed_field

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@runtime_checkable
class _HasAnalizRepo(Protocol):
    """Duck-typed uow shape — every caller passed here only ever needs
    ``.analiz_repo`` (a real ``UnitOfWork`` satisfies this structurally, as
    does ``report_service.py``'s ``_AnalizRepoProxy`` shim)."""

    analiz_repo: object


class DereceEnum(str, Enum):
    """Şoför performans derecesi"""

    A = "A"  # Mükemmel (90-100)
    B = "B"  # İyi (75-89)
    C = "C"  # Ortalama (60-74)
    D = "D"  # Düşük (40-59)
    F = "F"  # Yetersiz (0-39)


class TrendEnum(str, Enum):
    """Performans trendi"""

    IMPROVING = "İyileşiyor"
    STABLE = "Stabil"
    DECLINING = "Kötüleşiyor"


class GuzergahPerformans(BaseModel):
    """Güzergah bazlı performans modeli"""

    guzergah: str
    sefer_sayisi: int
    toplam_km: int
    ort_tuketim: float
    en_iyi: Optional[float] = None
    en_kotu: Optional[float] = None


class SoforDegerlendirme(BaseModel):
    """
    Şoför değerlendirme entity'si

    Puanlama Kriterleri:
    - Verimlilik (40%): Filo ortalamasına göre yakıt tüketimi
    - Tutarlılık (25%): Tüketim standart sapması
    - Deneyim (20%): Toplam km ve sefer sayısı
    - Trend (15%): Son dönem performans değişimi
    """

    sofor_id: int
    ad_soyad: str

    verimlilik_puani: float = Field(ge=0, le=100, description="Filo ortalamasına göre")
    tutarlilik_puani: float = Field(ge=0, le=100, description="Düşük std = yüksek puan")
    deneyim_puani: float = Field(ge=0, le=100, description="Toplam km ve sefer")
    trend_puani: float = Field(ge=0, le=100, description="İyileşme eğilimi")

    toplam_sefer: int = 0
    toplam_km: int = 0
    toplam_ton: float = 0.0
    ort_tuketim: float = 0.0
    filo_ortalama: float = 32.0
    en_iyi_tuketim: Optional[float] = None
    en_kotu_tuketim: Optional[float] = None
    std_sapma: float = 0.0

    trend: TrendEnum = TrendEnum.STABLE
    trend_degisim: float = 0.0  # Son 30 gün vs önceki 30 gün

    guclu_yanlar: List[str] = []
    iyilestirme_alanlari: List[str] = []
    tavsiyeler: List[str] = []

    guzergah_performansi: List[GuzergahPerformans] = []
    en_iyi_guzergah: Optional[str] = None
    en_kotu_guzergah: Optional[str] = None

    degerlendirme_tarihi: datetime = Field(default_factory=datetime.now)

    @computed_field
    @property
    def genel_puan(self) -> float:
        """
        Ağırlıklı genel puan hesapla

        Ağırlıklar:
        - Verimlilik: %40
        - Tutarlılık: %25
        - Deneyim: %20
        - Trend: %15
        """
        puan = (
            self.verimlilik_puani * 0.40
            + self.tutarlilik_puani * 0.25
            + self.deneyim_puani * 0.20
            + self.trend_puani * 0.15
        )
        return round(max(0, min(100, puan)), 1)

    @computed_field
    @property
    def derece(self) -> DereceEnum:
        """Performans derecesi"""
        puan = self.genel_puan
        if puan >= 90:
            return DereceEnum.A
        elif puan >= 75:
            return DereceEnum.B
        elif puan >= 60:
            return DereceEnum.C
        elif puan >= 40:
            return DereceEnum.D
        return DereceEnum.F

    @computed_field
    @property
    def yildiz(self) -> int:
        """1-5 yıldız"""
        puan = self.genel_puan
        if puan >= 85:
            return 5
        elif puan >= 70:
            return 4
        elif puan >= 55:
            return 3
        elif puan >= 40:
            return 2
        return 1

    @computed_field
    @property
    def filo_karsilastirma(self) -> float:
        """Filo ortalamasına göre % fark"""
        if self.filo_ortalama > 0:
            return round(
                ((self.filo_ortalama - self.ort_tuketim) / self.filo_ortalama) * 100, 1
            )
        return 0.0


def _analiz_repo(uow: Optional["_HasAnalizRepo"]):
    if uow is not None:
        return uow.analiz_repo
    from v2.modules.analytics_executive.public import get_analiz_repo

    return get_analiz_repo()


async def _bulk_driver_metrics(uow: Optional["_HasAnalizRepo"]):
    from v2.modules.driver.infrastructure.driver_metrics_queries import (
        get_bulk_driver_metrics,
    )

    return await get_bulk_driver_metrics(uow)


def calculate_verimlilik_puan(ort_tuketim: float, filo_ortalama: float) -> float:
    """
    Verimlilik puanı hesapla (0-100)

    Filo ortalamasından düşük = iyi
    Her %1 düşük = +5 puan (baz 50'den)
    Her %1 yüksek = -5 puan
    """
    if filo_ortalama <= 0:
        return 50.0

    fark_yuzde = ((filo_ortalama - ort_tuketim) / filo_ortalama) * 100
    puan = 50 + (fark_yuzde * 5)

    return round(max(0, min(100, puan)), 1)


def calculate_tutarlilik_puan(std_sapma: float) -> float:
    """
    Tutarlılık puanı hesapla (0-100)

    Düşük std sapma = tutarlı = iyi
    std=0 → 100 puan
    std=2 → 80 puan
    std=5 → 50 puan
    std=10+ → 0 puan
    """
    if std_sapma <= 0:
        return 100.0

    puan = 100 - (std_sapma * 10)
    return round(max(0, min(100, puan)), 1)


def calculate_deneyim_puan(toplam_km: int, toplam_sefer: int) -> float:
    """
    Deneyim puanı hesapla (0-100)

    Log scale kullanılır (ilk seferler daha değerli)
    100K km ve 100 sefer = 80 puan
    500K km ve 500 sefer = 100 puan
    """
    km_puan = min(50, math.log10(max(1, toplam_km)) * 10)  # Max 50
    sefer_puan = min(50, math.log10(max(1, toplam_sefer)) * 15)  # Max 50

    return round(km_puan + sefer_puan, 1)


def calculate_trend_puan(trend_degisim: float) -> float:
    """
    Trend puanı hesapla (0-100)

    İyileşme (negatif değişim) = iyi
    Her %1 iyileşme = +10 puan (baz 50'den)
    """
    puan = 50 - (trend_degisim * 10)
    return round(max(0, min(100, puan)), 1)


def generate_suggestions(degerlendirme: SoforDegerlendirme) -> SoforDegerlendirme:
    """Güçlü yanlar ve iyileştirme alanları belirle"""
    guclu = []
    iyilestirme = []
    tavsiyeler = []

    if degerlendirme.verimlilik_puani >= 70:
        guclu.append("Yakıt verimliliği filo ortalamasının üzerinde")
    elif degerlendirme.verimlilik_puani < 40:
        iyilestirme.append("Yakıt tüketimi yüksek")
        tavsiyeler.append("Ekonomik sürüş eğitimi önerilir")

    if degerlendirme.tutarlilik_puani >= 70:
        guclu.append("Tutarlı sürüş performansı")
    elif degerlendirme.tutarlilik_puani < 40:
        iyilestirme.append("Tüketim değişkenliği yüksek")
        tavsiyeler.append("Sürüş alışkanlıklarını gözden geçirin")

    if degerlendirme.deneyim_puani >= 70:
        guclu.append("Yıllık deneyim ve kilometre birikimi")

    if degerlendirme.trend == TrendEnum.IMPROVING:
        guclu.append("Son dönemde performans artışı")
    elif degerlendirme.trend == TrendEnum.DECLINING:
        iyilestirme.append("Son dönemde performans düşüşü")
        tavsiyeler.append("Yakın zamanlı seferleri inceleyin")

    if degerlendirme.genel_puan < 60:
        tavsiyeler.append("Düzenli bakım ve lastik kontrolü")

    if degerlendirme.filo_karsilastirma < -5:
        tavsiyeler.append("Motor devir kontrolü ve rölanti süresine dikkat")

    if degerlendirme.en_kotu_guzergah:
        tavsiyeler.append(
            f"'{degerlendirme.en_kotu_guzergah}' güzergahında performans düşük"
        )

    if degerlendirme.en_iyi_guzergah:
        guclu.append(
            f"'{degerlendirme.en_iyi_guzergah}' güzergahında yüksek performans"
        )

    degerlendirme.guclu_yanlar = guclu
    degerlendirme.iyilestirme_alanlari = iyilestirme
    degerlendirme.tavsiyeler = tavsiyeler

    return degerlendirme


async def _add_guzergah_performansi(
    degerlendirme: SoforDegerlendirme, sofor_id: int, uow: Optional[Any] = None
) -> SoforDegerlendirme:
    """Güzergah bazlı performans ekle.

    2026-07-18 düzeltmesi (2026-07-14 denetim bulgusu): eskiden
    session'sız modül-singleton `get_sofor_repo()` çağrılıyordu —
    `get_guzergah_performansi` raw-SQL olduğu için her çağrı "Database
    session not initialized" ile patlayıp aşağıdaki `except` tarafından
    yutuluyordu; karnenin güzergah alanları hiç dolmuyordu. Artık
    session-bound `uow.sofor_repo` (varsa) ya da kendi `UnitOfWork`'ü
    kullanılıyor (9206e3f'teki score-breakdown düzeltmesiyle aynı desen).
    """
    try:
        sofor_repo = getattr(uow, "sofor_repo", None)
        if sofor_repo is not None:
            guzergah_data = await sofor_repo.get_guzergah_performansi(sofor_id)
        else:
            from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

            async with UnitOfWork() as own_uow:
                guzergah_data = await own_uow.sofor_repo.get_guzergah_performansi(
                    sofor_id
                )

        if guzergah_data:
            guzergah_list = [
                GuzergahPerformans(
                    guzergah=g["guzergah"],
                    sefer_sayisi=g["sefer_sayisi"],
                    toplam_km=int(g["toplam_km"] or 0),
                    ort_tuketim=round(g["ort_tuketim"] or 0, 1),
                    en_iyi=round(g["en_iyi"], 1) if g["en_iyi"] else None,
                    en_kotu=round(g["en_kotu"], 1) if g["en_kotu"] else None,
                )
                for g in guzergah_data
            ]

            degerlendirme.guzergah_performansi = guzergah_list[:10]

            if guzergah_list:
                en_iyi = min(guzergah_list, key=lambda x: x.ort_tuketim)
                en_kotu = max(guzergah_list, key=lambda x: x.ort_tuketim)

                degerlendirme.en_iyi_guzergah = en_iyi.guzergah
                degerlendirme.en_kotu_guzergah = en_kotu.guzergah

                degerlendirme = generate_suggestions(degerlendirme)
    except Exception as e:
        logger.warning(f"Güzergah performansı alınamadı: {e}")

    return degerlendirme


async def evaluate_driver(
    sofor_id: int,
    pre_metrics: Optional[Dict] = None,
    pre_filo_ortalama: Optional[float] = None,
    include_routes: bool = True,
    uow: Optional["_HasAnalizRepo"] = None,
) -> Optional[SoforDegerlendirme]:
    """
    Şoför için kapsamlı değerlendirme yap (Optimize & Parallel Ready).
    """
    analiz_repo = _analiz_repo(uow)

    if pre_metrics:
        metrics = pre_metrics
    else:
        bulk_data = await _bulk_driver_metrics(uow)
        metrics = next((d for d in bulk_data if d["sofor_id"] == sofor_id), None)
        if not metrics:
            return None

    filo_ortalama = (
        pre_filo_ortalama
        if pre_filo_ortalama is not None
        else await analiz_repo.get_filo_ortalama_tuketim()
    )

    ort_tuketim = metrics.get("ort_tuketim", 0)
    std_sapma = metrics.get("std_sapma", 0) or 0

    recent_avg = metrics.get("recent_avg")
    older_avg = metrics.get("older_avg")
    trend_degisim = 0.0
    trend = TrendEnum.STABLE

    if recent_avg and older_avg:
        trend_degisim = (
            ((recent_avg - older_avg) / older_avg) * 100 if older_avg > 0 else 0
        )
        if trend_degisim < -2:
            trend = TrendEnum.IMPROVING
        elif trend_degisim > 2:
            trend = TrendEnum.DECLINING

    verimlilik_puani = calculate_verimlilik_puan(ort_tuketim, filo_ortalama)
    tutarlilik_puani = calculate_tutarlilik_puan(std_sapma)
    deneyim_puani = calculate_deneyim_puan(
        metrics["toplam_km"], metrics["toplam_sefer"]
    )
    trend_puani = calculate_trend_puan(trend_degisim)

    degerlendirme = SoforDegerlendirme(
        sofor_id=sofor_id,
        ad_soyad=metrics["ad_soyad"],
        verimlilik_puani=verimlilik_puani,
        tutarlilik_puani=tutarlilik_puani,
        deneyim_puani=deneyim_puani,
        trend_puani=trend_puani,
        toplam_sefer=metrics["toplam_sefer"],
        toplam_km=metrics["toplam_km"],
        toplam_ton=metrics["toplam_ton"],
        ort_tuketim=round(ort_tuketim, 2),
        filo_ortalama=filo_ortalama,
        en_iyi_tuketim=metrics["en_iyi_tuketim"],
        en_kotu_tuketim=metrics["en_kotu_tuketim"],
        std_sapma=round(std_sapma, 2),
        trend=trend,
        trend_degisim=round(trend_degisim, 1),
    )

    degerlendirme = generate_suggestions(degerlendirme)

    if include_routes:
        degerlendirme = await _add_guzergah_performansi(
            degerlendirme, sofor_id, uow=uow
        )

    return degerlendirme


async def get_all_evaluations(
    include_routes: bool = False, uow: Optional["_HasAnalizRepo"] = None
) -> List[SoforDegerlendirme]:
    """Tüm aktif şoförleri değerlendir (Optimize: ZERO N+1 Queries)"""
    import asyncio

    analiz_repo = _analiz_repo(uow)

    metrics_task = _bulk_driver_metrics(uow)
    filo_task = analiz_repo.get_filo_ortalama_tuketim()

    bulk_metrics, filo_ort = await asyncio.gather(metrics_task, filo_task)

    metrics_map = {m["sofor_id"]: m for m in bulk_metrics}
    evaluations = []

    for sid, metrics in metrics_map.items():
        eval_ = await evaluate_driver(
            sofor_id=sid,
            pre_metrics=metrics,
            pre_filo_ortalama=filo_ort,
            include_routes=include_routes,
            uow=uow,
        )
        if eval_:
            evaluations.append(eval_)

    evaluations.sort(key=lambda x: x.genel_puan, reverse=True)
    return evaluations


async def get_rankings(uow: Optional["_HasAnalizRepo"] = None) -> Dict[str, List[Dict]]:
    """Şoför sıralamaları"""
    evaluations = await get_all_evaluations(uow=uow)

    return {
        "genel": [
            {
                "sira": i + 1,
                "ad": e.ad_soyad,
                "puan": e.genel_puan,
                "derece": e.derece.value,
            }
            for i, e in enumerate(evaluations)
        ],
        "verimlilik": sorted(
            [{"ad": e.ad_soyad, "puan": e.verimlilik_puani} for e in evaluations],
            key=lambda x: x["puan"],
            reverse=True,
        ),
        "tutarlilik": sorted(
            [{"ad": e.ad_soyad, "puan": e.tutarlilik_puani} for e in evaluations],
            key=lambda x: x["puan"],
            reverse=True,
        ),
    }
