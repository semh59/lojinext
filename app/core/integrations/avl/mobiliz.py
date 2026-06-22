"""Mobiliz Araç Takip adapter stub.

Üretime almak için:
  1. .env'ye AVL_PROVIDER=mobiliz, AVL_BASE_URL, AVL_API_KEY,
     AVL_ACCOUNT_ID alanlarını doldur.
  2. Aşağıdaki TODO'ları gerçek API endpoint'lerine bağla
     (https://api.mobiliz.com — örnek; provider dokümanına göre).
  3. registry.py'de AVL_PROVIDERS["mobiliz"] = MobilizAVLProvider
     zaten kayıtlı.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from app.core.integrations.avl.base import AVLPosition, AVLTrip
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class MobilizAVLProvider:
    """Mobiliz Araç Takip API adapter (stub)."""

    provider_key = "mobiliz"

    def __init__(self, base_url: str, api_key: str, account_id: str) -> None:
        if not (base_url and api_key and account_id):
            raise ValueError(
                "Mobiliz provider için base_url + api_key + account_id zorunlu"
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account_id = account_id

    async def fetch_trips(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[AVLTrip]:
        # Beklenen request:
        #   GET {base_url}/v1/accounts/{account_id}/trips
        #   ?from={since.isoformat()}&to={(until or now).isoformat()}
        #   Header: Authorization: Bearer {api_key}
        # Response → AVLTrip listesine map et:
        #   trip_id → external_id
        #   plate → plaka (normalize)
        #   start_lat/start_lon, end_lat/end_lon, distance_km, ...
        raise NotImplementedError(
            "Mobiliz fetch_trips: gerçek API endpoint'i ve response şeması "
            "provider dokümanından doldurulacak."
        )

    async def fetch_positions(self, plakalar: List[str]) -> List[AVLPosition]:
        # Beklenen request:
        #   GET {base_url}/v1/accounts/{account_id}/positions/latest
        #   ?plates={','.join(plakalar)}
        raise NotImplementedError("Mobiliz fetch_positions: stub")

    async def healthcheck(self) -> bool:
        # Beklenen: GET {base_url}/v1/health veya benzeri
        return False  # stub her zaman False → /admin/health'te uyarı olur


# Diğer AVL provider'larının iskeleti (Arvento, Vodafone) tamamen aynı yapı —
# sen seçince ekleyeceğim.
