"""AVL (araç takip) provider abstract interface.

Tüm provider adapter'ları bu Protocol'ü implemente eder. Production'da
adapter'ın gerçek API çağrısı yapması beklenir; stub'lar
`NotImplementedError("API key + endpoint URL gerekli")` fırlatır.

Veri normalizasyonu: provider response → AVLTrip / AVLPosition dataclass.
İçe aktarma katmanı external_id ile idempotent insert yapar (aynı trip
iki kez kaydedilmesin).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Protocol


@dataclass
class AVLTrip:
    """Provider'dan gelen tek bir sefer kaydı (normalize edilmiş)."""

    external_id: str  # provider'da unique trip ID (idempotency key)
    plaka: str  # normalize edilmiş plaka (uppercase, no space)
    start_time: datetime
    end_time: Optional[datetime]
    start_lat: Optional[float]
    start_lon: Optional[float]
    end_lat: Optional[float]
    end_lon: Optional[float]
    distance_km: float
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    flat_distance_km: Optional[float] = None
    driver_external_id: Optional[str] = None
    raw_payload: dict = field(default_factory=dict)  # provider'ın orijinal JSON'u


@dataclass
class AVLPosition:
    """Anlık konum bilgisi (canlı takip için)."""

    external_id: str  # provider trip/vehicle ID
    plaka: str
    timestamp: datetime
    lat: float
    lon: float
    speed_kmh: Optional[float] = None
    heading_deg: Optional[float] = None
    raw_payload: dict = field(default_factory=dict)


class AVLProvider(Protocol):
    """Tüm AVL adapter'larının implement etmesi gereken interface.

    `provider_key` adapter registry'sinde kullanılan kısa isim
    (mobiliz/arvento/vodafone vb.).
    """

    provider_key: str

    async def fetch_trips(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[AVLTrip]:
        """`since` zamanından sonra başlamış seferleri döner.

        Production'da pagination + rate-limit aware olmalı.
        """
        ...

    async def fetch_positions(self, plakalar: List[str]) -> List[AVLPosition]:
        """Verilen plakalar için son konum/hız bilgisi.

        Boş liste verilirse provider'ın tüm aktif araçları döner.
        """
        ...

    async def healthcheck(self) -> bool:
        """Provider erişilebilir mi (basit ping/auth doğrulaması)."""
        ...
