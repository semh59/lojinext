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
from v2.modules.location.application.get_all_locations import get_all_locations
from v2.modules.location.application.get_location_by_id import get_location_by_id
from v2.modules.location.application.get_location_segments import (
    get_location_segments,
)
from v2.modules.location.application.get_location_stats import get_location_stats
from v2.modules.location.application.get_stale_locations import get_stale_locations
from v2.modules.location.application.get_unique_location_names import (
    get_unique_location_names,
)
from v2.modules.location.application.hydrate_location import (
    hydrate_location,
)
from v2.modules.location.application.hydration import (
    HydrationResult,
    LokasyonHydrator,
    get_lokasyon_hydrator,
)
from v2.modules.location.application.list_locations import list_locations
from v2.modules.location.application.search_locations_by_route import (
    search_locations_by_route,
)
from v2.modules.location.application.update_location import update_location
from v2.modules.location.domain.route_key import normalize_turkish_title, route_key
from v2.modules.location.infrastructure.models import Lokasyon, LokasyonSegment
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
    # ORM (dalga 16 task #58 — database/models.py bölünmesi)
    "Lokasyon",
    "LokasyonSegment",
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
    "get_all_locations",
    "get_location_by_id",
    "get_location_segments",
    "get_location_stats",
    "get_stale_locations",
    "get_unique_location_names",
    "hydrate_location",
    "search_locations_by_route",
]
