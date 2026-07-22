"""Import pipeline'ının üst-seviye (parse/altyapı) hatalarını monitoring'e bağlar.

Satır-bazlı hatalar zaten her importer'ın kendi iç `try/except`'inde
`errors` listesine toplanıyor ve buraya hiç gelmiyor — bu yalnız DB-down,
beklenmedik bug vb. önceden sessizce "Sistem hatası" string'ine çevrilip
hiçbir alarm tetiklemeyen (Tier B madde 13) durumlar için görünürlük ekler.
Import'un `(count, errors)` dönüş sözleşmesini korumak için exception
yutulmaya devam ediyor.
"""

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def report_infra_failure(source: str, exc: Exception) -> None:
    logger.error("%s: beklenmeyen hata: %s", source, exc, exc_info=True)
    try:
        from v2.modules.platform_infra.monitoring import aemit
        from v2.modules.platform_infra.monitoring.models import (
            ErrorEvent,
            ErrorLayer,
            ErrorSeverity,
        )

        await aemit(
            ErrorEvent(
                layer=ErrorLayer.SERVICE,
                category="import_unexpected_error",
                severity=ErrorSeverity.CRITICAL,
                message=f"{source}: {type(exc).__name__}: {str(exc)[:300]}",
            )
        )
    except Exception:
        pass
