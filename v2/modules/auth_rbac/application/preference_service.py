"""User-specific preferences (saved filters, columns, etc).

Eski ``PreferenceService`` sınıfı kaldırıldı (B.1) — her use-case bağımsız
bir fonksiyon, opsiyonel ``uow: UnitOfWork | None = None`` alır.
"""

from typing import Any, List, Optional

from app.database.models import KullaniciAyari
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


async def get_preferences(
    user_id: int,
    modul: str,
    ayar_tipi: Optional[str] = None,
    uow: Optional[UnitOfWork] = None,
) -> List[KullaniciAyari]:
    """Fetch preferences for a user and module."""
    if uow is not None:
        return await uow.setting_repo.get_user_settings(user_id, modul, ayar_tipi)
    async with UnitOfWork() as owned_uow:
        return await owned_uow.setting_repo.get_user_settings(user_id, modul, ayar_tipi)


async def save_preference(
    user_id: int,
    modul: str,
    ayar_tipi: str,
    deger: Any,
    ad: Optional[str] = None,
    is_default: bool = False,
    uow: Optional[UnitOfWork] = None,
) -> KullaniciAyari:
    """Save or update a user preference."""
    if not user_id or user_id <= 0:
        raise ValueError("Geçersiz kullanıcı için tercih kaydedilemez")
    if uow is not None:
        return await _save_preference(
            uow, user_id, modul, ayar_tipi, deger, ad, is_default
        )
    async with UnitOfWork() as owned_uow:
        return await _save_preference(
            owned_uow, user_id, modul, ayar_tipi, deger, ad, is_default
        )


async def _save_preference(
    uow: UnitOfWork,
    user_id: int,
    modul: str,
    ayar_tipi: str,
    deger: Any,
    ad: Optional[str],
    is_default: bool,
) -> KullaniciAyari:
    if is_default:
        # Clear existing default for this module/type
        await uow.setting_repo.clear_default(user_id, modul, ayar_tipi)

    # Upsert: find existing preference by (user, module, type, name) to prevent
    # duplicate accumulation on repeated saves.
    existing = None
    existing_list = await uow.setting_repo.get_user_settings(user_id, modul, ayar_tipi)
    if existing_list:
        if ayar_tipi == "sutun" or ad is None:
            existing = existing_list[0]
        else:
            existing = next((s for s in existing_list if s.ad == ad), None)

    if existing:
        success = await uow.setting_repo.update(
            existing.id, deger=deger, is_default=is_default
        )
        if success:
            await uow.commit()
            return await uow.session.get(KullaniciAyari, existing.id)

    # Create new preference
    pref = KullaniciAyari(
        kullanici_id=user_id,
        modul=modul,
        ayar_tipi=ayar_tipi,
        deger=deger,
        ad=ad,
        is_default=is_default,
    )
    uow.session.add(pref)
    await uow.commit()
    return pref


async def delete_preference(
    user_id: int, pref_id: int, uow: Optional[UnitOfWork] = None
) -> bool:
    """Delete a user preference."""
    if uow is not None:
        return await _delete_preference(uow, user_id, pref_id)
    async with UnitOfWork() as owned_uow:
        return await _delete_preference(owned_uow, user_id, pref_id)


async def _delete_preference(uow: UnitOfWork, user_id: int, pref_id: int) -> bool:
    pref = await uow.session.get(KullaniciAyari, pref_id)
    if not pref or pref.kullanici_id != user_id:
        return False

    success = await uow.setting_repo.delete(pref_id)
    if success:
        await uow.commit()
    return success


async def set_default(
    user_id: int, pref_id: int, uow: Optional[UnitOfWork] = None
) -> bool:
    """Set a specific preference as the default."""
    if uow is not None:
        return await _set_default(uow, user_id, pref_id)
    async with UnitOfWork() as owned_uow:
        return await _set_default(owned_uow, user_id, pref_id)


async def _set_default(uow: UnitOfWork, user_id: int, pref_id: int) -> bool:
    pref = await uow.session.get(KullaniciAyari, pref_id)
    if not pref or pref.kullanici_id != user_id:
        return False

    await uow.setting_repo.clear_default(user_id, pref.modul, pref.ayar_tipi)
    success = await uow.setting_repo.update(pref_id, is_default=True)
    if success:
        await uow.commit()
    return success
