"""
TIR Yakıt Takip - Model Manager
Model versiyonlama, karşılaştırma ve rollback
"""

import asyncio
import json
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent.parent))
from app.database.connection import AsyncSessionLocal
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ModelType(str, Enum):
    """Model tipleri"""

    ENSEMBLE = "ensemble"
    KALMAN = "kalman"
    PHYSICS = "physics"


@dataclass
class ModelVersion:
    """Model versiyonu"""

    id: int
    arac_id: int
    version: int
    model_type: ModelType
    params_json: str
    r2_score: Optional[float]
    mae: Optional[float]
    sample_count: int
    is_active: bool
    created_at: datetime
    notes: Optional[str] = None
    feature_schema_hash: Optional[str] = None
    training_data_hash: Optional[str] = None
    physics_version: Optional[str] = None


class ModelManager:
    """
    Model versiyonlama ve yönetim (Async).
    """

    MAX_VERSIONS = 5

    def __init__(self):
        self._async_lock = asyncio.Lock()

    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, "item"):
                return obj.item()
            if hasattr(obj, "tolist"):
                return obj.tolist()
            return super().default(obj)

    async def save_version(
        self,
        arac_id: int,
        model_type: ModelType,
        params: Dict,
        metrics: Dict,
        notes: str = "",
        **kwargs,
    ) -> int:
        """New model version save with Numpy support (Async)."""
        logger.info(f"Saving version for arac_id={arac_id} type={model_type}")
        async with AsyncSessionLocal() as session:
            # Get max version
            stmt = text("""
                SELECT MAX(version) FROM model_versions
                WHERE arac_id = CAST(:arac_id AS INTEGER) AND model_type = :model_type
            """)
            result = await session.execute(
                stmt, {"arac_id": arac_id, "model_type": model_type.value}
            )
            row = result.fetchone()
            next_version = (row[0] or 0) + 1

            params_json = json.dumps(params, cls=self.NumpyEncoder)

            def to_native(val):
                if hasattr(val, "item"):
                    return val.item()
                return val

            insert_stmt = text("""
                INSERT INTO model_versions
                (arac_id, version, model_type, params_json, r2_score, mae, sample_count, is_active, notes,
                 feature_schema_hash, training_data_hash, physics_version)
                VALUES (:arac_id, :version, :model_type, :params_json, :r2_score, :mae, :sample_count, :is_active, :notes,
                        :f_hash, :t_hash, :p_ver)
                RETURNING id
            """)  # noqa: E501

            cursor = await session.execute(
                insert_stmt,
                {
                    "arac_id": arac_id,
                    "version": next_version,
                    "model_type": model_type.value,
                    "params_json": params_json,
                    "r2_score": to_native(
                        metrics.get("ensemble_r2")
                        or metrics.get("r2_score")
                        or metrics.get("r2")
                        or metrics.get("metrics", {}).get("ensemble_r2")
                        or 0.0
                    ),
                    "mae": to_native(
                        metrics.get("mae")
                        or metrics.get("measurements", {}).get("mae")
                        or metrics.get("physics_mae")
                        or 0.0
                    ),
                    "sample_count": to_native(metrics.get("sample_count", 0)),
                    "is_active": False,
                    "notes": notes,
                    "f_hash": kwargs.get("feature_schema_hash"),
                    "t_hash": kwargs.get("training_data_hash"),
                    "p_ver": kwargs.get("physics_version"),
                },
            )

            version_id = cursor.fetchone()[0]

            # Activate and deactivate old versions in the same transaction so that
            # INSERT + is_active=True are atomic — a crash between them can no longer
            # leave a saved but permanently-inactive version.
            await self._activate_in_session(
                session, version_id, arac_id, model_type.value
            )
            await self._cleanup_in_session(session, arac_id, model_type)

            await session.commit()
            logger.info(f"Saved model version {next_version} for vehicle {arac_id}")
            return version_id

    @staticmethod
    async def _activate_in_session(
        session, version_id: int, arac_id: int, model_type_value: str
    ) -> None:
        """Activate version inside an existing session (no commit)."""
        update_stmt = text("""
            UPDATE model_versions
            SET is_active = CASE WHEN id = :id THEN TRUE ELSE FALSE END
            WHERE arac_id = CAST(:arac_id AS INTEGER) AND model_type = :model_type
        """)
        await session.execute(
            update_stmt,
            {"id": version_id, "arac_id": arac_id, "model_type": model_type_value},
        )
        logger.info(f"Activated model version {version_id}")

    async def activate_version(self, version_id: int) -> bool:
        """Belirli bir versiyonu aktif yap — standalone (kendi session'ını açar)."""
        async with AsyncSessionLocal() as session:
            try:
                stmt = text(
                    "SELECT arac_id, model_type FROM model_versions WHERE id = :id"
                )
                result = await session.execute(stmt, {"id": version_id})
                row = result.fetchone()

                if not row:
                    return False

                arac_id, model_type = row[0], row[1]
                await self._activate_in_session(
                    session, version_id, arac_id, model_type
                )
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Failed to activate version {version_id}: {e}")
                await session.rollback()
                return False

    async def get_active_version(
        self, arac_id: int, model_type: ModelType
    ) -> Optional[ModelVersion]:
        """Aktif model versiyonunu getir (Async)."""
        async with AsyncSessionLocal() as session:
            stmt = text("""
                SELECT * FROM model_versions
                WHERE arac_id = CAST(:arac_id AS INTEGER) AND model_type = :model_type AND is_active = TRUE
            """)
            result = await session.execute(
                stmt, {"arac_id": arac_id, "model_type": model_type.value}
            )
            row = result.fetchone()

            if row:
                return self._row_to_model(dict(row._mapping))
        return None

    async def delete_version(self, version_id: int) -> bool:
        """Versiyonu sil (Async)."""
        async with AsyncSessionLocal() as session:
            stmt = text("SELECT is_active FROM model_versions WHERE id = :id")
            result = await session.execute(stmt, {"id": version_id})
            row = result.fetchone()

            if not row:
                return False

            if row[0]:  # is_active
                logger.warning("Cannot delete active version")
                return False

            await session.execute(
                text("DELETE FROM model_versions WHERE id = :id"), {"id": version_id}
            )
            await session.commit()
            logger.info(f"Deleted model version {version_id}")
            return True

    async def _cleanup_in_session(
        self, session, arac_id: int, model_type: ModelType
    ) -> None:
        """Eski versiyonları sil — mevcut session içinde, commit olmadan."""
        stmt = text("""
            SELECT id FROM model_versions
            WHERE arac_id = CAST(:arac_id AS INTEGER) AND model_type = :model_type AND is_active = FALSE
            ORDER BY created_at DESC
            OFFSET :offset
        """)
        result = await session.execute(
            stmt,
            {
                "arac_id": arac_id,
                "model_type": model_type.value,
                "offset": self.MAX_VERSIONS - 1,
            },
        )
        rows = result.fetchall()
        for row in rows:
            await session.execute(
                text("DELETE FROM model_versions WHERE id = :id"), {"id": row[0]}
            )

    async def _cleanup_old_versions(self, arac_id: int, model_type: ModelType):
        """Eski versiyonları temizle — standalone (kendi session'ını açar)."""
        async with AsyncSessionLocal() as session:
            await self._cleanup_in_session(session, arac_id, model_type)
            await session.commit()

    def _row_to_model(self, row: Dict) -> ModelVersion:
        """Row'u ModelVersion'a dönüştür."""
        return ModelVersion(
            id=row["id"],
            arac_id=row["arac_id"],
            version=row["version"],
            model_type=ModelType(row["model_type"]),
            params_json=row["params_json"],
            r2_score=row["r2_score"],
            mae=row["mae"],
            sample_count=row["sample_count"] or 0,
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            feature_schema_hash=row.get("feature_schema_hash"),
            training_data_hash=row.get("training_data_hash"),
            physics_version=row.get("physics_version"),
            notes=row.get("notes"),
        )


# Singleton
_model_manager = None
_model_manager_lock = threading.Lock()


def get_model_manager() -> ModelManager:
    """Thread-safe singleton erişimi (Sync getter for async manager)."""
    global _model_manager
    if _model_manager is None:
        with _model_manager_lock:
            if _model_manager is None:
                _model_manager = ModelManager()
    return _model_manager
