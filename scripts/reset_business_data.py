"""Production veri girişine başlamadan önce iş verisini TRUNCATE eder.

Korunur:
  - kullanicilar, roller, kullanici_yetkileri (auth)
  - alembic_version (migration durumu)
  - sentry/monitoring konfig

Silinir (CASCADE sırasıyla):
  - seferler, sefer_belgeleri, sefer_log
  - yakit_alimlari, yakit_periyotlari
  - anomalies, fuel_investigations, coaching_deliveries
  - bakimlar, vehicle_event_log
  - outbox_events, error_events
  - araclar, soforler, dorseler, lokasyonlar  (master data)
  - sefer_istatistik_mv (materialized view refresh edilecek)

Sequence'lar 1'e reset edilir (ID'ler tahmin edilebilir kalsın).

KULLANIM:
    docker compose exec backend python scripts/reset_business_data.py --confirm
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.platform_infra.logging.logger import get_logger

logger = get_logger(__name__)


TABLES_IN_DELETE_ORDER = [
    # Yaprak tablolar (FK gelen) önce — gerçek tablo isimleri
    "sefer_belgeler",
    "seferler_log",
    "fuel_investigations",
    "coaching_deliveries",
    "anomalies",
    "outbox_events",
    "vehicle_event_log",
    "error_events",
    "error_occurrences",
    "yakit_alimlari",
    "yakit_periyotlari",
    "arac_bakimlari",
    "guzergah_kalibrasyonlari",
    "prediction_results",
    "sofor_adaptasyon",
    "route_paths",
    # Sefer master tablosu
    "seferler",
    # Lokasyon (sefer onu referans alıyor)
    "lokasyonlar",
    # Araç/şoför/dorse — kullanıcı yeniden seed edecek
    "soforler",
    "dorseler",
    "araclar",
]


async def reset(confirm: bool) -> None:
    if not confirm:
        print("--confirm bayrağı eksik. İptal edildi.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        # FK'leri geçici devre dışı bırak (PostgreSQL session_replication_role)
        await session.execute(text("SET session_replication_role = 'replica';"))
        for table in TABLES_IN_DELETE_ORDER:
            try:
                await session.execute(
                    text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
                )
                logger.info("TRUNCATE %s OK", table)
            except Exception as exc:
                logger.warning("TRUNCATE %s skipped: %s", table, exc)
        await session.execute(text("SET session_replication_role = 'origin';"))
        await session.commit()

        # Materialized view yeniden hesapla
        try:
            await session.execute(
                text("REFRESH MATERIALIZED VIEW sefer_istatistik_mv;")
            )
            await session.commit()
            logger.info("MV refresh OK")
        except Exception as exc:
            logger.warning("MV refresh failed: %s", exc)

    print("İş verisi temizlendi. Auth/migration korundu.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Onay bayrağı (olmadan çalışmaz).",
    )
    args = parser.parse_args()
    asyncio.run(reset(args.confirm))


if __name__ == "__main__":
    main()
