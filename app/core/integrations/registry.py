"""Provider registry — config'deki provider_key → adapter sınıfı eşleme.

Kullanım:
    from app.core.integrations.registry import get_avl_provider, get_fuel_provider
    avl = get_avl_provider()  # .env'deki AVL_PROVIDER'a göre instance döner
    trips = await avl.fetch_trips(since=...)

Yeni provider eklemek için:
  1. avl/ veya fuel/ altına yeni adapter dosyası
  2. AVL_PROVIDERS / FUEL_PROVIDERS dict'ine kayıt
  3. .env config'i güncelle
"""

from __future__ import annotations

from typing import Dict, Optional, Type

from app.config import settings
from app.core.integrations.avl.base import AVLProvider
from app.core.integrations.avl.mobiliz import MobilizAVLProvider
from app.infrastructure.logging.logger import get_logger
from v2.modules.fuel.infrastructure.integrations.opet_client import (
    FuelCardProvider,
    OpetFuelProvider,
)

logger = get_logger(__name__)


AVL_PROVIDERS: Dict[str, Type] = {
    "mobiliz": MobilizAVLProvider,
    # "arvento": ArventoAVLProvider,  # ileride
    # "vodafone": VodafoneAVLProvider,
}


FUEL_PROVIDERS: Dict[str, Type] = {
    "opet": OpetFuelProvider,
    # "shell": ShellFuelProvider,
    # "bp": BpFuelProvider,
    # "po": PetrolOfisiFuelProvider,
}


def get_avl_provider() -> Optional[AVLProvider]:
    """settings.AVL_PROVIDER'a göre adapter instance'ı.

    Provider seçili değilse veya config eksikse None döner —
    integration disabled durumu. Çağıran katman bunu handle eder.
    """
    key = (getattr(settings, "AVL_PROVIDER", "") or "").strip().lower()
    if not key:
        return None
    cls = AVL_PROVIDERS.get(key)
    if cls is None:
        logger.warning("AVL provider '%s' kayıtlı değil; integration disabled.", key)
        return None
    try:
        return cls(
            base_url=getattr(settings, "AVL_BASE_URL", ""),
            api_key=getattr(settings, "AVL_API_KEY", ""),
            account_id=getattr(settings, "AVL_ACCOUNT_ID", ""),
        )
    except Exception as exc:
        logger.warning("AVL provider '%s' init failed: %s", key, exc)
        return None


def get_fuel_provider() -> Optional[FuelCardProvider]:
    """settings.FUEL_PROVIDER'a göre adapter instance'ı."""
    key = (getattr(settings, "FUEL_PROVIDER", "") or "").strip().lower()
    if not key:
        return None
    cls = FUEL_PROVIDERS.get(key)
    if cls is None:
        logger.warning("Fuel provider '%s' kayıtlı değil; integration disabled.", key)
        return None
    try:
        return cls(
            base_url=getattr(settings, "FUEL_BASE_URL", ""),
            api_key=getattr(settings, "FUEL_API_KEY", ""),
            account_id=getattr(settings, "FUEL_ACCOUNT_ID", ""),
        )
    except Exception as exc:
        logger.warning("Fuel provider '%s' init failed: %s", key, exc)
        return None
