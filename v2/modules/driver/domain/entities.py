"""Driver internal Pydantic entities — dalga 16'da app/core/entities/models.py'den
taşındı. `DriverStats`, HTTP-yüzeyi `schemas.py`'den AYRI, `application/
driver_stats.py`'nin ürettiği istatistik DTO'sudur.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DriverStats(BaseModel):
    """Şoför bazlı istatistikler"""

    sofor_id: int
    ad_soyad: str
    toplam_sefer: int = 0
    toplam_km: float = 0.0
    ort_tuketim: float = 0.0
    skor: float = 1.0
    toplam_ton: float = 0.0
    bos_sefer_sayisi: int = 0
    toplam_yakit: float = 0.0
    en_iyi_tuketim: Optional[float] = None
    en_kotu_tuketim: Optional[float] = None
    filo_karsilastirma: float = 0.0
    performans_puani: Optional[float] = None
    trend: str = "stable"
    en_cok_gidilen_guzergah: Optional[str] = None
    guzergah_sayisi: int = 0
