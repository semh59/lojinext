"""Mobiliz Araç Takip adapter.

DÜRÜST NOT: Bu adapter gerçek Mobiliz API'sine karşı DOĞRULANMAMIŞ —
Mobiliz'in gerçek endpoint/auth/response şeması henüz elimizde yok (sağlayıcı
seçimi Faz 1, bkz. AVL entegrasyon planı). Aşağıdaki request/response şekli
bu dosyanın önceki "Beklenen request" TODO yorumlarından türetildi ve
api_stub/main.py'deki deterministik stub'a karşı test edilebilir hale
getirildi — gerçek Mobiliz sözleşmesi netleştiğinde bu mapping'in
güncellenmesi gerekir.

Üretime almak için:
  1. .env'ye AVL_PROVIDER=mobiliz, AVL_BASE_URL, AVL_API_KEY,
     AVL_ACCOUNT_ID alanlarını doldur.
  2. Mobiliz'in gerçek API dokümanı geldiğinde bu dosyadaki endpoint
     path'lerini ve response mapping'ini gerçek şemaya göre güncelle.
  3. registry.py'de AVL_PROVIDERS["mobiliz"] = MobilizAVLProvider
     zaten kayıtlı.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import httpx

from v2.modules.admin_platform.infrastructure.integrations.avl.base import (
    AVLPosition,
    AVLTrip,
)
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.monitoring.external_api_probe import (
    emit_network_error,
    get_monitored_client,
)

logger = get_logger(__name__)

_TIMEOUT = 10.0


class MobilizAVLProvider:
    """Mobiliz Araç Takip API adapter."""

    provider_key = "mobiliz"

    def __init__(self, base_url: str, api_key: str, account_id: str) -> None:
        if not (base_url and api_key and account_id):
            raise ValueError(
                "Mobiliz provider için base_url + api_key + account_id zorunlu"
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account_id = account_id

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def fetch_trips(
        self, since: datetime, until: Optional[datetime] = None
    ) -> List[AVLTrip]:
        until_val = until or datetime.now(timezone.utc)
        url = f"{self.base_url}/v1/accounts/{self.account_id}/trips"
        params = {"from": since.isoformat(), "to": until_val.isoformat()}
        try:
            async with get_monitored_client(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=self._headers())
        except httpx.RequestError as exc:
            await emit_network_error(exc, url)
            raise
        resp.raise_for_status()
        payload = resp.json()

        trips: List[AVLTrip] = []
        for item in payload.get("trips", []):
            trips.append(
                AVLTrip(
                    external_id=str(item["trip_id"]),
                    plaka=item["plate"].upper().replace(" ", ""),
                    start_time=datetime.fromisoformat(item["start_time"]),
                    end_time=datetime.fromisoformat(item["end_time"])
                    if item.get("end_time")
                    else None,
                    start_lat=item.get("start_lat"),
                    start_lon=item.get("start_lon"),
                    end_lat=item.get("end_lat"),
                    end_lon=item.get("end_lon"),
                    distance_km=item["distance_km"],
                    driver_external_id=item.get("driver_id"),
                    raw_payload=item,
                )
            )
        return trips

    async def fetch_positions(self, plakalar: List[str]) -> List[AVLPosition]:
        url = f"{self.base_url}/v1/accounts/{self.account_id}/positions/latest"
        params = {"plates": ",".join(plakalar)} if plakalar else {}
        try:
            async with get_monitored_client(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=self._headers())
        except httpx.RequestError as exc:
            await emit_network_error(exc, url)
            raise
        resp.raise_for_status()
        payload = resp.json()

        positions: List[AVLPosition] = []
        for item in payload.get("positions", []):
            positions.append(
                AVLPosition(
                    external_id=str(item["vehicle_id"]),
                    plaka=item["plate"].upper().replace(" ", ""),
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    lat=item["lat"],
                    lon=item["lon"],
                    speed_kmh=item.get("speed_kmh"),
                    heading_deg=item.get("heading_deg"),
                    raw_payload=item,
                )
            )
        return positions

    async def healthcheck(self) -> bool:
        url = f"{self.base_url}/v1/health"
        try:
            async with get_monitored_client(timeout=5.0) as client:
                resp = await client.get(url)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("Mobiliz healthcheck başarısız: %s", exc)
            return False


# Diğer AVL provider'larının iskeleti (Arvento, Vodafone) tamamen aynı yapı —
# sen seçince ekleyeceğim.
