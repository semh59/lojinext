from typing import Any, Dict, Optional

from sqlalchemy import select

try:
    from geoalchemy2.shape import from_shape
    from shapely.geometry import LineString
except ImportError:
    LineString = None
    from_shape = None

from app.database.models import GuzergahKalibrasyon
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RouteCalibrationService:
    """
    Handles spatial route matching and calibration using PostGIS.
    """

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    @staticmethod
    def _get_value(obj: Any, field: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    async def _get_sefer(self, sefer_id: int) -> Optional[Any]:
        return await self.uow.sefer_repo.get_by_id(sefer_id)

    async def _get_lokasyon(self, lokasyon_id: int) -> Optional[Any]:
        return await self.uow.lokasyon_repo.get_by_id(lokasyon_id)

    async def get_calibration_for_lokasyon(
        self, lokasyon_id: int
    ) -> Optional[GuzergahKalibrasyon]:
        """Fetch calibration data for a specific route."""
        stmt = select(GuzergahKalibrasyon).where(
            GuzergahKalibrasyon.lokasyon_id == lokasyon_id
        )
        result = await self.uow.session.execute(stmt)
        return result.scalar_one_or_none()

    async def match_sefer_to_path(self, sefer_id: int) -> Dict[str, Any]:
        """Check prerequisites for spatial route matching (not yet implemented).

        Always returns verification_available=False; spatial buffer analysis
        is not implemented — callers receive SPATIAL_VERIFICATION_NOT_IMPLEMENTED.
        """
        sefer = await self._get_sefer(sefer_id)
        rota_detay = self._get_value(sefer, "rota_detay")
        guzergah_id = self._get_value(sefer, "guzergah_id")
        if not sefer or not rota_detay or not guzergah_id:
            return {
                "status": "skipped",
                "matches": False,
                "verification_available": False,
                "error_code": "MISSING_TRIP_CONTEXT",
                "reason": "Trip route details or assigned route id is missing.",
            }

        calibration = await self.get_calibration_for_lokasyon(guzergah_id)
        target_path = getattr(calibration, "hedef_path", None) if calibration else None
        if not calibration or not target_path:
            return {
                "status": "not_calibrated",
                "matches": False,
                "verification_available": False,
                "error_code": "CALIBRATION_MISSING",
                "target_lokasyon_id": guzergah_id,
                "reason": "No calibration path is defined for this route.",
            }

        # 1. Parse trip coordinates from JSON
        coord_data = rota_detay.get("coordinates", [])
        if not coord_data:
            return {
                "status": "verification_unavailable",
                "matches": False,
                "verification_available": False,
                "error_code": "TRIP_COORDINATES_MISSING",
                "target_lokasyon_id": guzergah_id,
                "reason": "Trip route detail does not contain coordinates.",
            }

        return {
            "status": "verification_unavailable",
            "sefer_id": sefer_id,
            "target_lokasyon_id": guzergah_id,
            "matches": False,
            "verification_available": False,
            "error_code": "SPATIAL_VERIFICATION_NOT_IMPLEMENTED",
            "reason": (
                "Spatial route verification is not available for runtime trip matching."
            ),
        }

    async def calibrate_route_from_trip(self, sefer_id: int) -> bool:
        """
        Use a high-quality real trip to set the target 'Golden Path' for a route.
        """
        if LineString is None or from_shape is None:
            raise RuntimeError(
                "Route calibration requires 'shapely' and 'geoalchemy2' dependencies."
            )

        sefer = await self._get_sefer(sefer_id)
        rota_detay = self._get_value(sefer, "rota_detay")
        guzergah_id = self._get_value(sefer, "guzergah_id")
        if not sefer or not rota_detay or not guzergah_id:
            return False

        coord_data = rota_detay.get("coordinates", [])
        if len(coord_data) < 2:
            return False

        # Build the LineString and store its WKB as raw bytes. hedef_path is a
        # plain BYTEA column (no PostGIS anywhere), so we persist the WKB bytes
        # directly rather than a geoalchemy2 WKBElement — the latter binds via
        # ST_GeomFromEWKB and raised UndefinedFunction without PostGIS, breaking
        # this method in production.
        line = LineString(coord_data)
        geom_bytes = bytes(from_shape(line, srid=4326).data)

        # Update or create calibration
        stmt = select(GuzergahKalibrasyon).where(
            GuzergahKalibrasyon.lokasyon_id == guzergah_id
        )
        result = await self.uow.session.execute(stmt)
        calibration = result.scalar_one_or_none()

        if calibration:
            calibration.hedef_path = geom_bytes
            calibration.match_count = 1
        else:
            calibration = GuzergahKalibrasyon(
                lokasyon_id=guzergah_id,
                buffer_meters=250.0,
                hedef_path=geom_bytes,
            )
            self.uow.session.add(calibration)

        await self.uow.commit()
        return True
