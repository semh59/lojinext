"""OPET Filo Kart adapter stub.

Üretime almak için:
  1. .env'ye FUEL_PROVIDER=opet, FUEL_BASE_URL, FUEL_API_KEY,
     FUEL_ACCOUNT_ID alanlarını doldur.
  2. Aşağıdaki TODO'ları OPET'in B2B fiş entegrasyon endpoint'lerine
     bağla.
  3. registry.py'de FUEL_PROVIDERS["opet"] = OpetFuelProvider
     zaten kayıtlı.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from app.core.integrations.fuel.base import FuelTransaction
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class OpetFuelProvider:
    """OPET Filo Kart B2B adapter (stub)."""

    provider_key = "opet"

    def __init__(self, base_url: str, api_key: str, account_id: str) -> None:
        if not (base_url and api_key and account_id):
            raise ValueError(
                "OPET provider için base_url + api_key + account_id zorunlu"
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account_id = account_id

    async def fetch_transactions(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[FuelTransaction]:
        # Beklenen request:
        #   GET {base_url}/api/transactions
        #   ?accountId={account_id}&from={since}&to={until or now}
        # Response → FuelTransaction listesine map et:
        #   transactionId → external_transaction_id
        #   plateNumber → plaka
        #   stationName, stationCity, liters, unitPrice, total, odometer
        raise NotImplementedError(
            "OPET fetch_transactions: gerçek API endpoint'i ve response şeması "
            "OPET filo kart dokümantasyonundan doldurulacak."
        )

    async def healthcheck(self) -> bool:
        return False  # stub her zaman False
