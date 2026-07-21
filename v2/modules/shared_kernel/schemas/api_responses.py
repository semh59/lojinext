"""Generic response envelopes shared across ≥2 v2 modules (dalga 16 —
eski app/schemas/api_responses.py'nin geri kalanı — domain-özel sınıflar
ilgili modüllerin kendi schemas.py'sine taşındı).

Her sınıf/sabit burada kalma gerekçesi: ya ≥2 modül tarafından gerçekten
import ediliyor (`UploadResultResponse`, `SuccessCountResponse`,
`EXCEL_XLSX_RESPONSES` vb.), ya da tasarım gereği domain-agnostik bir zarf
(`MessageResponse`, `SuccessOnlyResponse`, `TaskStatusResponse` — hiçbiri
domain alanı taşımaz).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Plain `{"detail": "..."}` acknowledgement."""

    detail: str


class MessageWithWarningResponse(MessageResponse):
    """Same as `MessageResponse`, plus an optional non-fatal warning
    (e.g. auth logout when token-blacklisting failed but logout still
    succeeded)."""

    warning: Optional[str] = None


class SuccessCountResponse(BaseModel):
    """`{"success": bool, "message": str}` acknowledgement, optionally with
    a count of affected rows."""

    success: bool
    message: str
    count: Optional[int] = None


class ImportResultResponse(BaseModel):
    """Shared shape for Excel/bulk-import endpoints:
    `{"count": int, "errors": [str, ...]}`."""

    count: int
    errors: List[str] = Field(default_factory=list)


class DeleteResultResponse(BaseModel):
    """Shared shape for single-row delete endpoints that report whether the
    row was hard- or soft-deleted."""

    success: bool
    deleted_id: int
    mode: str = Field(..., description="Hard | Soft")


class UploadResultResponse(BaseModel):
    """Shared shape for Excel-upload endpoints:
    `{"success": bool, "message": str, "errors": [str, ...]}`."""

    success: bool
    message: str
    errors: List[str] = Field(default_factory=list)


class TaskStatusResponse(BaseModel):
    """Shared shape for any endpoint polling `BackgroundJobManager` (see
    root CLAUDE.md "Async job pattern")."""

    task_id: str
    status: str = Field(..., description="PROCESSING | SUCCESS | FAILED")
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None


class SuccessOnlyResponse(BaseModel):
    """Bare `{"success": bool}` acknowledgement."""

    success: bool


# ─── Binary/stream media-type documentation ────────────────────────────────
# Tier E madde 33: these endpoints genuinely return non-JSON bodies (Excel/
# PDF/ICS files, SSE streams) — a Pydantic response_model would be wrong for
# them. FastAPI's `responses={...}` param still lets the OpenAPI schema
# declare the real content-type instead of defaulting to nothing, so
# generated SDKs know to treat these as binary/blob/stream rather than
# `unknown`.

EXCEL_XLSX_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "content": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
        },
        "description": "Excel (.xlsx) dosyası",
    }
}

PDF_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {"content": {"application/pdf": {}}, "description": "PDF dosyası"}
}

ICS_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "content": {"text/calendar; charset=utf-8": {}},
        "description": "iCalendar (.ics) dosyası",
    }
}

SSE_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "content": {"text/event-stream": {}},
        "description": "Server-Sent Events akışı",
    }
}
