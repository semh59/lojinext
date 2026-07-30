"""Resolve a Telegram bot token from the backend's admin-configurable
override, falling back to the .env-sourced value.

Runs once at process startup, BEFORE Application.builder() constructs the
bot and before the async polling loop starts — a plain sync httpx client
is used here rather than the async client the rest of these bots use for
in-request calls. Mirrors integration_secrets.get_integration_secret()'s
own "a config read must never break the calling workflow" philosophy: any
failure to reach the backend (cold start, network hiccup) falls back to
env_fallback instead of raising.
"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_DELAY_S = 2.0
_TIMEOUT_S = 3.0


def resolve_bot_token(
    servis_adi: str, backend_url: str, internal_secret: str, env_fallback: str
) -> str:
    headers = {"X-Internal-Token": internal_secret} if internal_secret else {}
    url = f"{backend_url}/api/v1/internal/bot-token/{servis_adi}"

    for attempt in range(1, _RETRY_ATTEMPTS + 1):
        try:
            resp = httpx.get(url, headers=headers, timeout=_TIMEOUT_S)
            if resp.status_code == 200:
                token = resp.json().get("token")
                if token:
                    logger.info(
                        "%s: admin-configured token bulundu, kullanılıyor",
                        servis_adi,
                    )
                    return token
            # 404 (not configured / unknown / auth mismatch) — no point
            # retrying, backend answered, it just has nothing for us.
            break
        except httpx.HTTPError as exc:
            logger.warning(
                "%s: backend'e token çekme denemesi %d/%d başarısız: %s",
                servis_adi,
                attempt,
                _RETRY_ATTEMPTS,
                exc,
            )
            if attempt < _RETRY_ATTEMPTS:
                time.sleep(_RETRY_DELAY_S)

    logger.info("%s: env fallback kullanılıyor", servis_adi)
    return env_fallback
