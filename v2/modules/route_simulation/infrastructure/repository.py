"""
TIR Yakıt Takip - Route Path Repository
Rota geometrisi ve API cache yönetimi
"""

from typing import Dict, Optional

from sqlalchemy import and_, select

from v2.modules.platform_infra.logging.logger import get_logger
from v2.modules.route_simulation.infrastructure.models import RoutePath
from v2.modules.shared_kernel.infrastructure.base_repository import BaseRepository

logger = get_logger(__name__)


class RouteRepository(BaseRepository[RoutePath]):
    """RoutePath veritabanı operasyonları (Async)"""

    model = RoutePath

    async def get_by_coords(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        tolerance: float = 0.0005,  # Yaklaşık 50m tolerans
    ) -> Optional[Dict]:
        """Koordinatlara göre cache'lenmiş rota getir"""
        session = self.session
        # SQLite ABS logic using select
        stmt = (
            select(self.model)
            .where(
                and_(
                    self.model.origin_lat >= origin_lat - tolerance,
                    self.model.origin_lat <= origin_lat + tolerance,
                    self.model.origin_lon >= origin_lon - tolerance,
                    self.model.origin_lon <= origin_lon + tolerance,
                    self.model.dest_lat >= dest_lat - tolerance,
                    self.model.dest_lat <= dest_lat + tolerance,
                    self.model.dest_lon >= dest_lon - tolerance,
                    self.model.dest_lon <= dest_lon + tolerance,
                )
            )
            .limit(1)
        )

        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()
        return self._to_dict(obj)

    async def save_route(self, data: Dict) -> int:
        """Yeni rota geometrisini kaydet veya güncelle"""
        # Unique constraint (origin_lat, origin_lon, dest_lat, dest_lon)
        # exists check
        existing = await self.get_by_coords(
            data["origin_lat"], data["origin_lon"], data["dest_lat"], data["dest_lon"]
        )

        if existing:
            # Update
            return await self.update(existing["id"], **data)
        else:
            # Create
            return await self.create(**data)
