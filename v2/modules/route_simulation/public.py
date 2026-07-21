"""route_simulation modülünün TEK dışa açık yüzeyi.

Diğer modüller (location, app-tarafı sefer_fuel_estimator, scripts) bu
modüle YALNIZ buradan erişir — `application/`/`domain/`/`infrastructure/`
iç yollarına doğrudan import atılmaz (B.2 sınır kuralı). Bu dosya
2026-07-18 dedektif denetiminde eklendi — o güne kadar modülün public.py'si
yoktu ve tüketiciler iç yollardan import ediyordu (dokümante borç,
`CLAUDE.md` "Bilinen açık notlar").

Not: modülün kendi `api/route_routes.py`'si iç yolları kullanmaya devam
eder (modül-içi erişim serbesttir).
"""

from v2.modules.route_simulation.application.get_route_details import (
    get_route_details,
)
from v2.modules.route_simulation.application.get_route_difficulty import (
    get_route_difficulty,
)
from v2.modules.route_simulation.application.simulate_route import (
    RouteSimulator,
    SimulationResult,
    get_route_simulator,
)
from v2.modules.route_simulation.domain.segment_resampler import resample_segments
from v2.modules.route_simulation.domain.segment_simulator import (
    SegmentInput,
    simulate_route,
)
from v2.modules.route_simulation.infrastructure.mapbox_client import MapboxClient
from v2.modules.route_simulation.infrastructure.models import (
    GuzergahKalibrasyon,
    RoutePath,
    RouteSegment,
    RouteSimulation,
)
from v2.modules.route_simulation.infrastructure.open_meteo_client import (
    OpenMeteoElevationClient,
    get_elevation_client,
)
from v2.modules.route_simulation.infrastructure.openroute_client import (
    OpenRouteClient,
)

__all__ = [
    # ORM (dalga 16 task #58 — database/models.py bölünmesi)
    "RoutePath",
    "GuzergahKalibrasyon",
    "RouteSimulation",
    "RouteSegment",
    "get_route_details",
    "get_route_difficulty",
    "RouteSimulator",
    "SimulationResult",
    "get_route_simulator",
    "resample_segments",
    "SegmentInput",
    "simulate_route",
    "MapboxClient",
    "OpenMeteoElevationClient",
    "get_elevation_client",
    "OpenRouteClient",
]
