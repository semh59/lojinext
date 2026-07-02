from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_active_user
from app.core.exceptions import DomainError
from app.core.services.preference_service import PreferenceService
from app.database.models import Kullanici
from app.infrastructure.logging.logger import get_logger
from app.schemas.preference import (
    PreferenceCreate,
    PreferenceItem,
    PreferenceListResponse,
)

router = APIRouter()
preference_service = PreferenceService()
logger = get_logger(__name__)


@router.get("/{modul}", response_model=PreferenceListResponse)
async def get_preferences(
    modul: str,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    ayar_tipi: Optional[str] = Query(None),
):
    """Fetch user preferences for a module (e.g. 'seferler')."""
    items = await preference_service.get_preferences(current_user.id, modul, ayar_tipi)
    return {"items": items}


@router.post("/", response_model=PreferenceItem)
async def save_preference(
    pref_data: PreferenceCreate,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Save or update a user preference."""
    if not current_user.id or current_user.id <= 0:
        raise HTTPException(
            status_code=403, detail="Sistem kullanıcısı tercih kaydedemez"
        )
    try:
        return await preference_service.save_preference(
            user_id=current_user.id,
            modul=pref_data.modul,
            ayar_tipi=pref_data.ayar_tipi,
            deger=pref_data.deger,
            ad=pref_data.ad,
            is_default=pref_data.is_default,
        )
    except DomainError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save preference error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Tercih kaydedilirken bir hata oluştu"
        )


@router.delete("/{pref_id}")
async def delete_preference(
    pref_id: int, current_user: Annotated[Kullanici, Depends(get_current_active_user)]
):
    """Delete a user preference."""
    success = await preference_service.delete_preference(current_user.id, pref_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"success": True}


@router.post("/{pref_id}/default")
async def set_default_preference(
    pref_id: int, current_user: Annotated[Kullanici, Depends(get_current_active_user)]
):
    """Set a preference as default."""
    success = await preference_service.set_default(current_user.id, pref_id)
    if not success:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"success": True}
