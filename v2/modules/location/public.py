"""Public surface of the location module.

Other modules that need to call into location must import from here, not
from `application/`, `domain/`, or `infrastructure/` directly (see
TASKS/modules/location.md and .importlinter's forbidden-imports contract,
enforced from FAZ1's import-linter gate task onward).

There is no ``LokasyonService`` class — each use-case is a standalone
function taking an explicit ``LokasyonRepository`` (obtained from the
caller's own UnitOfWork/session, e.g. ``uow.lokasyon_repo``). This avoids
hiding shared repo/event_bus state behind a stateful facade class for six
otherwise-unrelated use-cases (create/update/delete/list/analyze/geocode).
"""

from v2.modules.location.application.analyze_location_route import (
    analyze_location_route,
)
from v2.modules.location.application.create_location import create_location
from v2.modules.location.application.delete_location import delete_location
from v2.modules.location.application.geocode_location import geocode_location
from v2.modules.location.application.hydration import (
    HydrationResult,
    LokasyonHydrator,
    get_lokasyon_hydrator,
)
from v2.modules.location.application.list_locations import list_locations
from v2.modules.location.application.update_location import update_location
from v2.modules.location.domain.route_key import normalize_turkish_title, route_key
from v2.modules.location.infrastructure.repository import (
    LokasyonRepository,
    get_lokasyon_repo,
)
from v2.modules.location.schemas import (
    GeocodeSuggestion,
    LokasyonBase,
    LokasyonCreate,
    LokasyonPaginationResponse,
    LokasyonResponse,
    LokasyonSegmentResponse,
    LokasyonSegmentsResponse,
    LokasyonUpdate,
)

__all__ = [
    "create_location",
    "update_location",
    "delete_location",
    "list_locations",
    "analyze_location_route",
    "geocode_location",
    "route_key",
    "normalize_turkish_title",
    "LokasyonHydrator",
    "HydrationResult",
    "get_lokasyon_hydrator",
    "LokasyonRepository",
    "get_lokasyon_repo",
    "LokasyonBase",
    "LokasyonCreate",
    "LokasyonUpdate",
    "LokasyonResponse",
    "LokasyonSegmentResponse",
    "LokasyonSegmentsResponse",
    "LokasyonPaginationResponse",
    "GeocodeSuggestion",
]
