"""Runtime-config okuma yardımcıları (2026-07-07 runtime-config epiği).

Admin Konfigürasyon alt-sistemi (sistem_konfig tablosu + KonfigService
cache/pubsub/geçmiş altyapısı) uzun süre yazma-tarafı eksiksiz ama OKUMA
tarafı bağlantısız kaldı: servisler değerleri settings'ten (env) okuyordu,
operatörün UI'dan yaptığı değişiklik hiçbir davranışı etkilemiyordu.

Bu modül tek kanonik okuma yolunu sağlar:

    from v2.modules.admin_platform.application.runtime_config import get_runtime_float
    z = await get_runtime_float("ANOMALY_Z_THRESHOLD", settings.ANOMALY_Z_THRESHOLD)

Semantik:
- Değer redis cache -> sistem_konfig satırı -> ``fallback`` sırasıyla çözülür
  (konfig_service.get_config_value; UI'dan güncellemede cache invalidate +
  pubsub zaten çalışıyor, dolayısıyla değişiklik 1 saatlik TTL beklemeden
  yayılır).
- Satır yoksa veya okuma HERHANGİ bir nedenle başarısız olursa fallback
  döner ve warning loglanır — config okuması iş akışını ASLA kırmaz
  (audit-logger'ın best-effort felsefesiyle aynı).
- Seed: migration 0041 varsayılan satırları oluşturur; yeni bir anahtarı
  buradan okumaya başlayan kod, satırını da bir data-migration ile
  seed'lemeli (yoksa UI'da görünmez, sadece fallback çalışır).
"""

from typing import Any, Optional

from v2.modules.admin_platform.application.konfig_service import get_config_value
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)


async def get_runtime_value(
    key: str, fallback: Any, uow: Optional[UnitOfWork] = None
) -> Any:
    """sistem_konfig'ten değer okur; satır yok/okunamıyor ise ``fallback``."""
    try:
        if uow is not None:
            value = await get_config_value(uow.session, key, None)
        else:
            async with UnitOfWork() as own_uow:
                value = await get_config_value(own_uow.session, key, None)
        return fallback if value is None else value
    except Exception as exc:  # config okuması iş akışını kırmamalı
        logger.warning("Runtime config okunamadı (%s): %s — fallback", key, exc)
        return fallback


async def get_runtime_float(
    key: str, fallback: float, uow: Optional[UnitOfWork] = None
) -> float:
    """Sayısal runtime config; tip bozuksa da fallback (warning loglar)."""
    value = await get_runtime_value(key, fallback, uow=uow)
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Runtime config %s sayısal değil (%r) — fallback %s", key, value, fallback
        )
        return fallback
