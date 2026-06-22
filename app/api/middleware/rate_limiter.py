"""
Rate limiter adapter.

If `slowapi` is not installed, expose a no-op limiter so module imports do not
break in lightweight test/dev environments.
"""

import logging
from typing import TYPE_CHECKING, Any

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    # Type-check against the real classes; the runtime fallback below is only
    # for environments where slowapi is not installed.
    from slowapi import Limiter
    from slowapi.util import get_remote_address
else:
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
    except ImportError:
        Limiter = None
        get_remote_address = None


class _NoopLimiter:
    def limit(self, *_args, **_kwargs):
        def _decorator(func):
            return func

        return _decorator


limiter: Any
if Limiter:
    # RATE_LIMIT_ENABLED=False (kapasite yük testi) → slowapi limit'lerini de devre dışı bırak.
    try:
        from app.config import settings as _settings

        _rl_enabled = getattr(_settings, "RATE_LIMIT_ENABLED", True)
    except Exception:
        _rl_enabled = True
    limiter = Limiter(key_func=get_remote_address, enabled=_rl_enabled)
else:
    _log.critical(
        "slowapi is not installed — ALL RATE LIMITS ARE DISABLED. "
        "Install slowapi to enable rate limiting."
    )
    limiter = _NoopLimiter()
