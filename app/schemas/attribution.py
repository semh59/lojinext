from typing import Optional

from pydantic import BaseModel, Field


class AttributionOverrideRequest(BaseModel):
    sefer_id: int
    new_arac_id: Optional[int] = None
    new_sofor_id: Optional[int] = None
    reason: str = Field(..., min_length=5, max_length=255)


class AttributionOverrideResponse(BaseModel):
    sefer_id: int
    success: bool
    message: str
