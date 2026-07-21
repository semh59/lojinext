from fastapi import APIRouter, Depends, Response

from app.schemas.api_responses import HealthCheckResponse
from v2.modules.admin_platform.application.health_service import (
    HealthService,
    get_health_service,
)

router = APIRouter()

# Fields safe to expose on the PUBLIC (unauthenticated) health endpoint. The
# component dicts from get_full_status() also carry `error` (raw DB/Redis
# exception strings — host, port, database name, credentials in a URL) and
# AI-engine internals (index paths, document counts, model list). Those must
# not leak to anonymous callers; authenticated admins get the full detail via
# the admin health endpoint.
_PUBLIC_COMPONENT_FIELDS = frozenset({"status", "latency_ms"})


@router.get("/", response_model=HealthCheckResponse)
async def health_check(
    response: Response,
    service: HealthService = Depends(get_health_service),
) -> HealthCheckResponse:
    """Liveness/readiness probe — returns 503 when the database is down."""
    payload = await service.get_full_status()
    if payload["components"]["database"]["status"] != "healthy":
        response.status_code = 503

    safe_payload = {
        "status": payload.get("status"),
        "uptime_seconds": payload.get("uptime_seconds"),
        "components": {
            name: {k: v for k, v in component.items() if k in _PUBLIC_COMPONENT_FIELDS}
            for name, component in payload.get("components", {}).items()
        },
    }
    return HealthCheckResponse.model_validate(safe_payload)
