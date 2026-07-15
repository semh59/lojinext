"""Route simulation persist repository — `route_simulations`+`route_segments`.

B.1/katman-disiplini düzeltmesi (2026-07-15, dalga-1-6+8 dedektif
denetiminde bulundu): bu iki tablo daha önce hiç repository katmanına
sahip değildi — `api/route_routes.py::simulate_route`/`get_route_simulation`
ORM persist/query mantığını doğrudan route içinde çalıştırıyordu. Mekanik
taşıma, davranış değişikliği yok (aynı sorgu/persist sırası, aynı
`selectinload` eager-reload deseni — MissingGreenlet gotcha'sını önlemek
için, bkz. metod docstring'leri).
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.base_repository import BaseRepository
from app.database.models import RouteSegment, RouteSimulation


class SimulationRepository(BaseRepository[RouteSimulation]):
    """`route_simulations`/`route_segments` üzerinde persist + okuma (Async)."""

    model = RouteSimulation

    async def create_with_segments(
        self, sim: RouteSimulation, segments: List[RouteSegment]
    ) -> RouteSimulation:
        """Simülasyonu + segmentlerini kaydeder, eager-loaded olarak yeniden döner.

        `sim.segments.append(...)` çağıranın (application katmanı)
        sorumluluğunda — burada yalnız `session.add`+`commit`+`refresh` +
        eager-reload yapılır. Eager-reload ZORUNLU: `sim.segments`'e
        commit-sonrası lazy erişim async engine altında
        `MissingGreenlet` fırlatır (IO greenlet dışında) — taşımadan
        önce de bu yüzden `selectinload` ile yeniden okunuyordu.
        """
        sim.segments = segments
        self.session.add(sim)
        await self.session.commit()
        await self.session.refresh(sim)
        return await self.get_by_id_with_segments(sim.id)  # type: ignore[return-value]

    async def get_by_id_with_segments(
        self, simulation_id: int
    ) -> Optional[RouteSimulation]:
        return (
            await self.session.execute(
                select(RouteSimulation)
                .where(RouteSimulation.id == simulation_id)
                .options(selectinload(RouteSimulation.segments))
            )
        ).scalar_one_or_none()
