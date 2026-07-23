from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMeta(BaseModel):
    """API metadata standard."""

    count: Optional[int] = None
    offset: Optional[int] = None
    limit: Optional[int] = None
    total: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


class StandardResponse(BaseModel, Generic[T]):
    """Standard API Response Format: { data, meta, errors }"""

    data: Optional[T] = None
    meta: Optional[ResponseMeta] = Field(default_factory=ResponseMeta)
    errors: Optional[List[Dict[str, Any]]] = None
