"""
TIR Yakıt Takip - Şoför Değerlendirme Sistemi
Kapsamlı puanlama ve performans karnesi
"""

import math
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


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

    # Alt puanlar (0-100)
    verimlilik_puani: float = Field(ge=0, le=100, description="Filo ortalamasına göre")
    tutarlilik_puani: float = Field(ge=0, le=100, description="Düşük std = yüksek puan")
    deneyim_puani: float = Field(ge=0, le=100, description="Toplam km ve sefer")
    trend_puani: float = Field(ge=0, le=100, description="İyileşme eğilimi")

    # İstatistikler
    toplam_sefer: int = 0
    toplam_km: int = 0
    toplam_ton: float = 0.0
    ort_tuketim: float = 0.0
    filo_ortalama: float = 32.0
    en_iyi_tuketim: Optional[float] = None
    en_kotu_tuketim: Optional[float] = None
    std_sapma: float = 0.0

    # Trend
    trend: TrendEnum = TrendEnum.STABLE
    trend_degisim: float = 0.0  # Son 30 gün vs önceki 30 gün

    # Öneriler
    guclu_yanlar: List[str] = []
    iyilestirme_alanlari: List[str] = []
    tavsiyeler: List[str] = []

    # Güzergah performansı
    guzergah_performansi: List[GuzergahPerformans] = []
    en_iyi_guzergah: Optional[str] = None
    en_kotu_guzergah: Optional[str] = None

    # Zaman damgası
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


class SoforDegerlendirmeService:
    """Şoför değerlendirme iş mantığı"""

    def __init__(self, analiz_repo, sofor_repo):
        if not analiz_repo or not sofor_repo:
            raise ValueError(
                "SoforDegerlendirmeService requires 'analiz_repo' and 'sofor_repo'"
            )
        self.analiz_repo = analiz_repo
        self.sofor_repo = sofor_repo

    # Properties removed, direct attribute access used via self.analiz_repo / self.sofor_repo

    def calculate_verimlilik_puan(
        self, ort_tuketim: float, filo_ortalama: float
    ) -> float:
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

    def calculate_tutarlilik_puan(self, std_sapma: float) -> float:
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

        # Lineer interpolasyon
        puan = 100 - (std_sapma * 10)
        return round(max(0, min(100, puan)), 1)

    def calculate_deneyim_puan(self, toplam_km: int, toplam_sefer: int) -> float:
        """
        Deneyim puanı hesapla (0-100)

        Log scale kullanılır (ilk seferler daha değerli)
        100K km ve 100 sefer = 80 puan
        500K km ve 500 sefer = 100 puan
        """
        km_puan = min(50, math.log10(max(1, toplam_km)) * 10)  # Max 50
        sefer_puan = min(50, math.log10(max(1, toplam_sefer)) * 15)  # Max 50

        return round(km_puan + sefer_puan, 1)

    def calculate_trend_puan(self, trend_degisim: float) -> float:
        """
        Trend puanı hesapla (0-100)

        İyileşme (negatif değişim) = iyi
        Her %1 iyileşme = +10 puan (baz 50'den)
        """
        # trend_degisim: pozitif = kötüleşme, negatif = iyileşme
        puan = 50 - (trend_degisim * 10)
        return round(max(0, min(100, puan)), 1)

    def generate_suggestions(
        self, degerlendirme: SoforDegerlendirme
    ) -> SoforDegerlendirme:
        """Güçlü yanlar ve iyileştirme alanları belirle"""
        guclu = []
        iyilestirme = []
        tavsiyeler = []

        # Verimlilik analizi
        if degerlendirme.verimlilik_puani >= 70:
            guclu.append("Yakıt verimliliği filo ortalamasının üzerinde")
        elif degerlendirme.verimlilik_puani < 40:
            iyilestirme.append("Yakıt tüketimi yüksek")
            tavsiyeler.append("Ekonomik sürüş eğitimi önerilir")

        # Tutarlılık analizi
        if degerlendirme.tutarlilik_puani >= 70:
            guclu.append("Tutarlı sürüş performansı")
        elif degerlendirme.tutarlilik_puani < 40:
            iyilestirme.append("Tüketim değişkenliği yüksek")
            tavsiyeler.append("Sürüş alışkanlıklarını gözden geçirin")

        # Deneyim analizi
        if degerlendirme.deneyim_puani >= 70:
            guclu.append("Yıllık deneyim ve kilometre birikimi")

        # Trend analizi
        if degerlendirme.trend == TrendEnum.IMPROVING:
            guclu.append("Son dönemde performans artışı")
        elif degerlendirme.trend == TrendEnum.DECLINING:
            iyilestirme.append("Son dönemde performans düşüşü")
            tavsiyeler.append("Yakın zamanlı seferleri inceleyin")

        # Genel tavsiyeler
        if degerlendirme.genel_puan < 60:
            tavsiyeler.append("Düzenli bakım ve lastik kontrolü")

        if degerlendirme.filo_karsilastirma < -5:
            tavsiyeler.append("Motor devir kontrolü ve rölanti süresine dikkat")

        # Güzergah bazlı öneriler
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

    async def evaluate_driver(
        self,
        sofor_id: int,
        pre_metrics: Optional[Dict] = None,
        pre_filo_ortalama: Optional[float] = None,
        include_routes: bool = True,
    ) -> Optional[SoforDegerlendirme]:
        """
        Şoför için kapsamlı değerlendirme yap (Optimize & Parallel Ready).
        """
        # 1. Metrikleri al (N+1 FIX: pre_metrics varsa DB'ye gitme)
        if pre_metrics:
            metrics = pre_metrics
        else:
            bulk_data = await self.analiz_repo.get_bulk_driver_metrics()
            metrics = next((d for d in bulk_data if d["sofor_id"] == sofor_id), None)
            if not metrics:
                return None

        # 2. Filo ortalaması (N+1 FIX: pre_filo_ortalama varsa DB'ye gitme)
        filo_ortalama = (
            pre_filo_ortalama
            if pre_filo_ortalama is not None
            else await self.analiz_repo.get_filo_ortalama_tuketim()
        )

        # 3. İstatistiksel değerler
        ort_tuketim = metrics.get("ort_tuketim", 0)
        std_sapma = metrics.get("std_sapma", 0) or 0

        # 4. Trend hesapla
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

        # 5. Puanları hesapla
        verimlilik_puani = self.calculate_verimlilik_puan(ort_tuketim, filo_ortalama)
        tutarlilik_puani = self.calculate_tutarlilik_puan(std_sapma)
        deneyim_puani = self.calculate_deneyim_puan(
            metrics["toplam_km"], metrics["toplam_sefer"]
        )
        trend_puani = self.calculate_trend_puan(trend_degisim)

        # 6. Değerlendirme objesini oluştur
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

        # 7. Önerileri ve Güzergahları ekle
        degerlendirme = self.generate_suggestions(degerlendirme)

        # Optimize: Liste görünümünde güzergah detaylarına gerek olmayabilir
        if include_routes:
            degerlendirme = await self._add_guzergah_performansi(
                degerlendirme, sofor_id
            )

        return degerlendirme

    async def _add_guzergah_performansi(
        self, degerlendirme: SoforDegerlendirme, sofor_id: int
    ) -> SoforDegerlendirme:
        """Güzergah bazlı performans ekle"""
        from app.database.repositories.sofor_repo import get_sofor_repo

        try:
            guzergah_data = await get_sofor_repo().get_guzergah_performansi(sofor_id)

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

                degerlendirme.guzergah_performansi = guzergah_list[:10]  # En fazla 10

                # En iyi ve en kötü güzergah
                if guzergah_list:
                    en_iyi = min(guzergah_list, key=lambda x: x.ort_tuketim)
                    en_kotu = max(guzergah_list, key=lambda x: x.ort_tuketim)

                    degerlendirme.en_iyi_guzergah = en_iyi.guzergah
                    degerlendirme.en_kotu_guzergah = en_kotu.guzergah

                    # Önerileri güncelle
                    degerlendirme = self.generate_suggestions(degerlendirme)
        except Exception as e:
            from app.infrastructure.logging.logger import get_logger

            get_logger(__name__).warning(f"Güzergah performansı alınamadı: {e}")

        return degerlendirme

    async def get_all_evaluations(
        self, include_routes: bool = False
    ) -> List[SoforDegerlendirme]:
        """Tüm aktif şoförleri değerlendir (Optimize: ZERO N+1 Queries)"""
        import asyncio

        # 1. Toplu verileri bir kez çek (Tek Sorgu + Tek Cache Call)
        metrics_task = self.analiz_repo.get_bulk_driver_metrics()
        filo_task = self.analiz_repo.get_filo_ortalama_tuketim()

        bulk_metrics, filo_ort = await asyncio.gather(metrics_task, filo_task)

        metrics_map = {m["sofor_id"]: m for m in bulk_metrics}
        evaluations = []

        # 2. Döngü içinde DB'ye gitmeden hesapla
        for sid, metrics in metrics_map.items():
            eval = await self.evaluate_driver(
                sofor_id=sid,
                pre_metrics=metrics,
                pre_filo_ortalama=filo_ort,
                include_routes=include_routes,
            )
            if eval:
                evaluations.append(eval)

        # Genel puana göre sırala
        evaluations.sort(key=lambda x: x.genel_puan, reverse=True)
        return evaluations

    async def get_rankings(self) -> Dict[str, List[Dict]]:
        """Şoför sıralamaları"""
        evaluations = await self.get_all_evaluations()

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


# Removed local singleton to use central Container instead.
