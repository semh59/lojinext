"""
Request Context - Correlation ID management
Distributed tracing ve log korelasyonu için

`app/infrastructure/context/request_context.py`'den dalga 17 (platform_infra)
denetiminde taşındı — zaten taşınmış `monitoring.db_probe` ve
`shared_kernel.infrastructure.outbox`'ın bu dosyaya geri bağımlı olması,
genuinely cross-cutting olduğunun doğrudan kanıtıydı.
"""

import contextvars
import uuid
from typing import Optional

# Async-safe context variables
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)
_user_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "user_id", default=None
)
_request_path: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_path", default=""
)


def get_correlation_id() -> str:
    """Mevcut request'in correlation ID'sini döner"""
    cid = _correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Correlation ID ayarla"""
    _correlation_id.set(cid)


def get_current_user_id() -> Optional[int]:
    """Mevcut kullanıcı ID'sini döner"""
    return _user_id.get()


def set_current_user_id(user_id: int) -> None:
    """Kullanıcı ID'si ayarla"""
    _user_id.set(user_id)


def get_request_path() -> str:
    """Aktif request'in HTTP path'i — observability event'lerinde context için."""
    return _request_path.get()


def set_request_path(path: str) -> None:
    """Middleware her request başında çağırır; n_plus_one ve slow_query
    event'leri bu path'i metadata'ya yazar."""
    _request_path.set(path)


def clear_context() -> None:
    """Context'i temizle (request sonunda)"""
    _correlation_id.set("")
    _user_id.set(None)
    _request_path.set("")
