"""Akaryakıt kart sistemi provider — OPET Filo Kart adapter + shared Protocol.

DÜRÜST NOT: Bu adapter gerçek OPET API'sine karşı DOĞRULANMAMIŞ — OPET'in
gerçek B2B endpoint/auth/response şeması henüz elimizde yok (sağlayıcı
seçimi Faz 1, bkz. AVL/fuel-card entegrasyon planı). Aşağıdaki request/
response şekli bu dosyanın önceki "Beklenen request" TODO yorumlarından
türetildi ve api_stub/main.py'deki deterministik stub'a karşı test
edilebilir hale getirildi — gerçek OPET sözleşmesi netleştiğinde bu
mapping'in güncellenmesi gerekir.

Üretime almak için:
  1. .env'ye FUEL_PROVIDER=opet, FUEL_BASE_URL, FUEL_API_KEY,
     FUEL_ACCOUNT_ID alanlarını doldur.
  2. OPET'in gerçek B2B dokümanı geldiğinde bu dosyadaki endpoint
     path'lerini ve response mapping'ini gerçek şemaya göre güncelle.
  3. app/core/integrations/registry.py'de FUEL_PROVIDERS["opet"] =
     OpetFuelProvider zaten kayıtlı (platform-infra henüz taşınmadı,
     registry.py bu dosyaya geçici olarak import atar).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Protocol

import httpx

from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.external_api_probe import (
    emit_network_error,
    get_monitored_client,
)

logger = get_logger(__name__)

_TIMEOUT = 10.0


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


class OpetFuelProvider:
    """OPET Filo Kart B2B adapter."""

    provider_key = "opet"

    def __init__(self, base_url: str, api_key: str, account_id: str) -> None:
        if not (base_url and api_key and account_id):
            raise ValueError(
                "OPET provider için base_url + api_key + account_id zorunlu"
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account_id = account_id

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def fetch_transactions(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[FuelTransaction]:
        until_val = until or datetime.now(timezone.utc)
        url = f"{self.base_url}/api/transactions"
        params = {
            "accountId": self.account_id,
            "from": since.isoformat(),
            "to": until_val.isoformat(),
        }
        try:
            async with get_monitored_client(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=self._headers())
        except httpx.RequestError as exc:
            await emit_network_error(exc, url)
            raise
        resp.raise_for_status()
        payload = resp.json()

        transactions: List[FuelTransaction] = []
        for item in payload.get("transactions", []):
            transactions.append(
                FuelTransaction(
                    external_transaction_id=str(item["transactionId"]),
                    plaka=item["plateNumber"].upper().replace(" ", ""),
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    station_name=item.get("stationName", ""),
                    station_city=item.get("stationCity"),
                    liters=item["liters"],
                    price_per_liter=item["unitPrice"],
                    total_amount_tl=item["total"],
                    odometer_km=item.get("odometer"),
                    driver_card_id=item.get("cardId"),
                    receipt_no=item.get("receiptNo"),
                    fuel_type=item.get("fuelType"),
                    raw_payload=item,
                )
            )
        return transactions

    async def healthcheck(self) -> bool:
        url = f"{self.base_url}/api/health"
        try:
            async with get_monitored_client(timeout=5.0) as client:
                resp = await client.get(url)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("OPET healthcheck başarısız: %s", exc)
            return False
