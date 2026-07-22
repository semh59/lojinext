"""Admin-configurable external API key management (2026-07-10).

Write-only secret storage for external integrations (Mapbox/OpenRoute/Groq):
an admin can set/replace a key from the UI, but the plaintext is never
readable again through any API response — only a "configured" status
(boolean + last-updated metadata) is ever exposed. Decryption happens in
exactly one place (`get_integration_secret`), used only to build outbound
API requests to the third-party service itself.

Deliberately NOT Redis-cached: this is a 3-row table queried once per
outbound call site invocation, and caching the plaintext anywhere beyond
the single decrypt-and-use call site would widen the exposure surface for
no meaningful performance gain.
"""

from datetime import datetime, timezone
from typing import Optional, TypedDict

from sqlalchemy import select

from v2.modules.admin_platform.infrastructure.models import EntegrasyonAyari
from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.platform_infra.security.pii_encryption import decrypt_pii, encrypt_pii
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = get_logger(__name__)

KNOWN_SERVICES = (
    "mapbox",
    "openroute",
    "groq",
    "telegram_driver_bot",
    "telegram_ops_bot",
)

# Subset of KNOWN_SERVICES whose plaintext value is ever returned to a
# caller other than this module's own outbound-call sites. Telegram bots
# run as separate containers and must authenticate with Telegram's API
# themselves, so (unlike mapbox/openroute/groq, whose plaintext never
# leaves this backend process) the value has to cross a process boundary.
# See app/api/v1/endpoints/internal.py's /bot-token/{servis_adi} — it
# checks membership in THIS set, not KNOWN_SERVICES, so a bug there can
# never leak the non-bot secrets.
BOT_TOKEN_SERVICES = frozenset({"telegram_driver_bot", "telegram_ops_bot"})


class IntegrationStatus(TypedDict):
    servis_adi: str
    configured: bool
    guncellenme_tarihi: Optional[datetime]
    guncelleyen_id: Optional[int]


async def get_integration_secret(
    servis_adi: str, env_fallback: Optional[str]
) -> Optional[str]:
    """Resolve the active secret for a service: DB override, else env fallback.

    Never raises — any DB/decrypt failure falls back to `env_fallback` and
    logs a warning, matching runtime_config.py's "config reads must never
    break the calling workflow" philosophy.
    """
    try:
        async with UnitOfWork() as uow:
            row = await uow.session.scalar(
                select(EntegrasyonAyari).where(
                    EntegrasyonAyari.servis_adi == servis_adi
                )
            )
            if row is None or row.deger_sifreli is None:
                return env_fallback
            return decrypt_pii(row.deger_sifreli)
    except Exception as exc:
        logger.warning(
            "Entegrasyon anahtarı okunamadı (%s): %s — env fallback kullanılıyor",
            servis_adi,
            exc,
        )
        return env_fallback


async def set_integration_secret(
    servis_adi: str, plaintext_value: str, user_id: int
) -> None:
    """Encrypt + upsert a service's API key. Raises ValueError for an unknown
    service name (only KNOWN_SERVICES may be configured this way)."""
    if servis_adi not in KNOWN_SERVICES:
        raise ValueError(f"Bilinmeyen entegrasyon servisi: {servis_adi}")

    # Süper admin sentetik id<=0 — kullanicilar tablosunda karşılığı yok,
    # FK violation'dan kaçınmak için NULL'a düşürülür (admin_audit_log'daki
    # aynı desen, bkz. CLAUDE.md).
    resolved_user_id = user_id if user_id and user_id > 0 else None

    async with UnitOfWork() as uow:
        row = await uow.session.scalar(
            select(EntegrasyonAyari).where(EntegrasyonAyari.servis_adi == servis_adi)
        )
        if row is None:
            row = EntegrasyonAyari(servis_adi=servis_adi)
            uow.session.add(row)
        row.deger_sifreli = encrypt_pii(plaintext_value)
        row.guncelleyen_id = resolved_user_id
        row.guncellenme_tarihi = datetime.now(timezone.utc)
        await uow.commit()


async def get_integration_statuses() -> list[IntegrationStatus]:
    """Status for every known service — configured bool + audit metadata only.
    Never touches/decrypts `deger_sifreli`'s actual value."""
    async with UnitOfWork() as uow:
        rows = await uow.session.scalars(select(EntegrasyonAyari))
        by_name = {r.servis_adi: r for r in rows}

    return [
        IntegrationStatus(
            servis_adi=servis,
            configured=(
                servis in by_name and by_name[servis].deger_sifreli is not None
            ),
            guncellenme_tarihi=by_name[servis].guncellenme_tarihi
            if servis in by_name
            else None,
            guncelleyen_id=by_name[servis].guncelleyen_id
            if servis in by_name
            else None,
        )
        for servis in KNOWN_SERVICES
    ]
