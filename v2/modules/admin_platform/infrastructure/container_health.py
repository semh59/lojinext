"""Read-only Docker Engine API queries via docker-socket-proxy.

Used to report the actual running/health state of a container whose status
can't be inferred from application-level state alone — the telegram bot
containers are the motivating case: their tokens are typically provisioned
via container-local `.env` (see docker-compose.yml), not through the admin
Integrations panel's DB-backed key store, so `configured: bool` there can
be False while the bot is in fact running fine. This module lets the admin
panel show the bot's real container state alongside that flag.

Never raises — any failure (proxy unreachable, container not found) returns
found=False so a transient monitoring hiccup can't break the admin
Integrations page. Uses docker-socket-proxy (CONTAINERS+NETWORKS+EVENTS=1,
POST=0 — see docker-compose.yml) rather than the raw socket, matching how
Traefik already queries it; the backend itself gets no socket mount.
"""

from __future__ import annotations

import json
from typing import Optional, TypedDict

import httpx

from app.config import settings
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT = 3.0


class ContainerStatus(TypedDict):
    found: bool
    running: bool
    health: Optional[
        str
    ]  # "healthy" | "unhealthy" | "starting" | None (no healthcheck)


async def get_container_status(compose_service: str) -> ContainerStatus:
    """Look up a docker-compose service's container by its
    `com.docker.compose.service` label (stable across container renames /
    `docker compose up --scale`). Returns found=False on any failure or if
    no matching container exists — never raises."""
    filters = json.dumps({"label": [f"com.docker.compose.service={compose_service}"]})
    url = f"{settings.DOCKER_SOCKET_PROXY_URL}/containers/json"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params={"all": "true", "filters": filters})
            resp.raise_for_status()
            containers = resp.json()
    except Exception as exc:
        logger.warning(
            "Docker socket proxy sorgusu başarısız (%s): %s", compose_service, exc
        )
        return ContainerStatus(found=False, running=False, health=None)

    if not containers:
        return ContainerStatus(found=False, running=False, health=None)

    container = containers[0]
    state = container.get("State", "")
    status_text = container.get("Status", "")  # e.g. "Up 2 hours (healthy)"
    health: Optional[str] = None
    if "(healthy)" in status_text:
        health = "healthy"
    elif "(unhealthy)" in status_text:
        health = "unhealthy"
    elif "(health: starting)" in status_text:
        health = "starting"
    return ContainerStatus(found=True, running=state == "running", health=health)
