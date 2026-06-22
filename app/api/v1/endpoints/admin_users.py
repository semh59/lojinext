from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.services.user_service import UserService
from app.database.models import Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.permission_checker import require_yetki
from app.schemas.user import KullaniciCreate, KullaniciRead, KullaniciUpdate

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=List[KullaniciRead])
async def list_users(
    current_user: Kullanici = Depends(require_yetki("kullanici_goruntule")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """Kullanıcıları listele"""
    service = UserService()
    return await service.list_users(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=KullaniciRead)
async def get_user(
    user_id: int,
    current_user: Kullanici = Depends(require_yetki("kullanici_goruntule")),
):
    """Kullanıcı detayını getir"""
    service = UserService()
    return await service.get_user(user_id)


@router.post("/", response_model=KullaniciRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: KullaniciCreate,
    current_user: Kullanici = Depends(require_yetki("kullanici_ekle")),
):
    """Yeni kullanıcı oluştur"""
    service = UserService()
    created = await service.create_user(
        data.model_dump(), created_by_id=current_user.id
    )
    await log_audit_event(
        module="kullanici",
        action="create",
        entity_id=str(created.get("id") if isinstance(created, dict) else None),
        new_value={"email": data.email, "rol_id": data.rol_id},
        user_id=current_user.id,
    )
    return created


@router.put("/{user_id}", response_model=KullaniciRead)
async def update_user(
    user_id: int,
    data: KullaniciUpdate,
    current_user: Kullanici = Depends(require_yetki("kullanici_duzenle")),
):
    """Kullanıcıyı güncelle"""
    service = UserService()
    # Filter out None values to avoid overwriting with nulls if update schema allows partials
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    result = await service.update_user(user_id, update_data)
    await log_audit_event(
        module="kullanici",
        action="update",
        entity_id=str(user_id),
        # never log the raw password — only which fields changed
        new_value={k: v for k, v in update_data.items() if k != "sifre"},
        user_id=current_user.id,
    )
    return result


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: Kullanici = Depends(require_yetki("kullanici_sil")),
):
    """Kullanıcıyı sil"""
    service = UserService()
    success = await service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    await log_audit_event(
        module="kullanici",
        action="delete",
        entity_id=str(user_id),
        user_id=current_user.id,
    )
    return None
