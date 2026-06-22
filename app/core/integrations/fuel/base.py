"""Akaryakıt kart sistemi provider abstract interface.

Tüm fuel-card adapter'ları bu Protocol'ü implemente eder. Provider'dan
gelen işlem (transaction) kaydı normalize edilip yakit_alimlari'na
external_transaction_id ile idempotent insert edilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Protocol


@dataclass
class FuelTransaction:
    """Provider'dan gelen tek bir akaryakıt fişi (normalize edilmiş)."""

    external_transaction_id: str  # provider'da unique işlem ID (idempotency)
    plaka: str  # normalize plaka
    timestamp: datetime
    station_name: str  # "Shell Maslak" vb.
    station_city: Optional[str]
    liters: float
    price_per_liter: float
    total_amount_tl: float
    odometer_km: Optional[int]  # araç km sayacı (fişte basılı)
    driver_card_id: Optional[str]  # kart başına şoför çözümleme
    receipt_no: Optional[str]
    fuel_type: Optional[str] = None  # "DIZEL", "MOTORIN" vs.
    raw_payload: dict = field(default_factory=dict)


class FuelCardProvider(Protocol):
    """Tüm akaryakıt kart adapter'larının implement etmesi gereken interface.

    `provider_key` adapter registry'sinde kullanılan kısa isim
    (opet/shell/bp/po vb.).
    """

    provider_key: str

    async def fetch_transactions(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[FuelTransaction]:
        """`since` zamanından sonraki tüm işlemler.

        Production'da pagination + rate-limit aware olmalı.
        """
        ...

    async def healthcheck(self) -> bool:
        """Provider erişilebilir mi."""
        ...
