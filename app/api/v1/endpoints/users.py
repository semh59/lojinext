"""Users endpoints — read-only access for any authenticated caller.

Administrative CRUD (create / update / delete) lives at /api/v1/admin/users
(see app.api.v1.endpoints.admin_users). This module exposes:

- GET /me                — the currently authenticated user's profile
- PATCH /me              — update own profile fields (ad_soyad)
- POST /me/change-password — change own password
- GET /                  — paginated list of active users
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_current_active_admin, get_current_active_user
from app.core.services.user_service import UserService
from app.database.models import Kullanici
from app.schemas.user import KullaniciRead

router = APIRouter()


class UpdateMeRequest(BaseModel):
    ad_soyad: Optional[str] = Field(None, min_length=2, max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        from app.schemas.validators import validate_password_complexity

        return validate_password_complexity(v)


@router.get("/me", response_model=KullaniciRead)
async def read_current_user(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
) -> Kullanici:
    """Return the currently authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=KullaniciRead)
async def update_me(
    data: UpdateMeRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Update the currently authenticated user's own profile fields."""
    service = UserService()
    update_data = data.model_dump(exclude_unset=True)
    return await service.update_user(current_user.id, update_data)


@router.post("/me/change-password", status_code=200)
async def change_my_password(
    data: ChangePasswordRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Change the currently authenticated user's password."""
    # ARCH-001: the env break-glass superadmin's password is managed via the
    # SUPER_ADMIN_PASSWORD environment variable, not the DB row it now resolves
    # to — block API password edits for that session.
    if getattr(current_user, "is_env_superadmin", False):
        raise HTTPException(
            status_code=403,
            detail="Sistem yöneticisi şifresi ortam değişkeni üzerinden yönetilir.",
        )
    service = UserService()
    success = await service.change_password(
        current_user.id, data.current_password, data.new_password
    )
    if not success:
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")
    return {"detail": "Şifreniz başarıyla güncellendi"}


@router.get("/", response_model=List[KullaniciRead])
async def list_users(
    current_user: Annotated[Kullanici, Depends(get_current_active_admin)],
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum users to return"),
):
    """Return active users — admin only (exposes PII: email, IP, role permissions)."""
    service = UserService()
    return await service.list_users(skip=skip, limit=limit)
