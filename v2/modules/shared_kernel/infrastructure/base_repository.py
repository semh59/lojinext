"""
TIR Yakıt Takip - Base Repository
SQLAlchemy ORM tabanlı güvenli versiyon.
"""

from abc import ABC
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from v2.modules.platform_infra.logging.logger import get_logger

if TYPE_CHECKING:
    from v2.modules.shared_kernel.infrastructure.base import Base

logger = get_logger(__name__)

T = TypeVar("T", bound="Base")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository using SQLAlchemy ORM.
    Tüm işlemler ORM modelleri üzerinden yapılır (SQL Injection Safe).
    """

    model: Type[T] = None  # Alt sınıfta tanımlanmalı (örn: model = Arac)

    def __init__(self, session: Optional[AsyncSession] = None):
        if self.model is None:
            raise TypeError(
                f"{self.__class__.__name__}.model tanımlanmamış. "
                "Alt sınıfta `model = MyModel` satırını ekleyin."
            )
        self._session = session

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                f"Database session not initialized in {self.__class__.__name__}. "
                "Ensure the repository is used within a UnitOfWork context or "
                "initialized with a valid session."
            )
        return self._session

    @session.setter
    def session(self, value: AsyncSession):
        self._session = value

    @asynccontextmanager
    async def _get_session(self):
        """
        Async context manager that yields a session.
        Uses the pre-assigned session if available; otherwise acquires one from
        the connection pool.  Designed to be mockable in unit tests.
        """
        if self._session is not None:
            yield self._session
        else:
            from v2.modules.platform_infra.database.connection import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                yield session

    def _to_dict(self, obj: Any) -> Optional[Dict[str, Any]]:
        """ORM objesini dictionary'e çevirir"""
        if not obj:
            return None

        if isinstance(obj, dict):
            return obj

        if hasattr(obj, "_mapping"):
            return dict(obj._mapping)

        if hasattr(obj, "model_dump"):
            return obj.model_dump()

        try:
            mapper = inspect(obj.__class__)
            result = {c.key: getattr(obj, c.key) for c in mapper.column_attrs}

            # Include relationships the caller explicitly eager-loaded (e.g.
            # via get_all(..., load_relations=["rol"])). Without this, every
            # joinedload/selectinload was silently dropped here — the ORM
            # object had the related row populated in memory, but only
            # column_attrs made it into the returned dict, so API responses
            # built on get_all/get_by_id always serialized eager-loaded
            # relations as missing (e.g. KullaniciRead.rol was always None
            # even when rol_id pointed at a real, existing role). Only
            # attributes already loaded are read — checking `state.unloaded`
            # avoids triggering a lazy-load query, which would raise
            # MissingGreenlet under an async session.
            state = inspect(obj)
            for rel in mapper.relationships:
                if rel.key in state.unloaded:
                    continue
                value = getattr(obj, rel.key)
                if isinstance(value, list):
                    result[rel.key] = [self._to_dict(v) for v in value]
                else:
                    result[rel.key] = (
                        self._to_dict(value) if value is not None else None
                    )
            return result
        except Exception:
            if hasattr(obj, "__dict__"):
                return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
            return dict(obj)

    # Pagination & Search Security
    MAX_LIMIT = 1000
    search_columns: List[str] = []

    async def get_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_inactive: bool = False,
        load_relations: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Tüm kayıtları getir (ORM)."""
        limit = max(1, min(int(limit), self.MAX_LIMIT))
        offset = max(0, int(offset))

        stmt = select(self.model)

        # N+1 Prevention: Handle eager loading
        if load_relations:
            from sqlalchemy.orm import joinedload

            for rel in load_relations:
                if hasattr(self.model, rel):
                    stmt = stmt.options(joinedload(getattr(self.model, rel)))

        if hasattr(self.model, "aktif") and not include_inactive:
            stmt = stmt.where(getattr(self.model, "aktif").is_(True))

        if filters:
            from sqlalchemy import or_

            _filters = filters.copy()

            # Handle standardized search
            search_query = _filters.pop("search", None)
            if search_query and self.search_columns:
                search_filters = []
                for col in self.search_columns:
                    if hasattr(self.model, col):
                        search_filters.append(
                            getattr(self.model, col).ilike(f"%{search_query}%")
                        )
                if search_filters:
                    stmt = stmt.where(or_(*search_filters))

            # Handle regular equality and range filters
            for k, v in _filters.items():
                if v is None:
                    continue

                # Range filters
                if k.endswith("_ge"):
                    real_k = k[:-3]
                    if hasattr(self.model, real_k):
                        stmt = stmt.where(getattr(self.model, real_k) >= v)
                elif k.endswith("_le"):
                    real_k = k[:-3]
                    if hasattr(self.model, real_k):
                        stmt = stmt.where(getattr(self.model, real_k) <= v)
                # Equality filters
                elif hasattr(self.model, k):
                    stmt = stmt.where(getattr(self.model, k) == v)

        order_clauses = []
        if order_by:
            # Supports comma-separated multi-column ordering
            # ("cikis_yeri asc, varis_yeri asc"). Only real table columns are
            # honoured — arbitrary attributes/methods/relationships are ignored
            # so a caller-supplied string can never reach an unsafe getattr or
            # crash on a non-orderable attribute.
            valid_columns = self.model.__table__.columns.keys()
            for part in order_by.split(","):
                tokens = part.split()
                if not tokens:
                    continue
                col_name = tokens[0]
                direction = tokens[1].lower() if len(tokens) > 1 else "asc"
                if col_name in valid_columns:
                    col = getattr(self.model, col_name)
                    order_clauses.append(
                        col.desc() if direction == "desc" else col.asc()
                    )

        if order_clauses:
            stmt = stmt.order_by(*order_clauses)
        else:
            pk = inspect(self.model).primary_key[0]
            stmt = stmt.order_by(pk.desc())

        stmt = stmt.limit(limit).offset(offset)

        session = self.session
        result = await session.execute(stmt)
        objs = result.scalars().all()
        return [self._to_dict(obj) for obj in objs]

    async def get_paged(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        aktif_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Standardized paged query."""
        _filters = (filters or {}).copy()
        if search:
            _filters["search"] = search

        return await self.get_all(
            filters=_filters, limit=limit, offset=skip, include_inactive=not aktif_only
        )

    async def get_by_id(
        self, id: int, for_update: bool = False, include_inactive: bool = False
    ) -> Optional[Dict[str, Any]]:
        """ID ile kayıt getir.

        Varsayılan olarak soft-delete edilmiş kayıtları (``aktif=False``
        ve/veya ``is_deleted=True``) hariç tutar — ``get_all()``/``count()``
        ile tutarlı davranış. Silinmiş/pasif bir kaydı kasıtlı olarak görmek
        gereken akışlar (ör. smart-delete'in ikinci aşaması, az önce
        oluşturulan kaydı aynı transaction içinde geri okuma) ``include_inactive=True``
        geçmelidir.
        """
        session = self.session
        pk_col = inspect(self.model).primary_key[0]
        conditions = [pk_col == id]
        if not include_inactive:
            if hasattr(self.model, "aktif"):
                conditions.append(getattr(self.model, "aktif").is_(True))
            if hasattr(self.model, "is_deleted"):
                conditions.append(getattr(self.model, "is_deleted").is_(False))

        if for_update:
            stmt = select(self.model).where(*conditions).with_for_update()
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
        elif len(conditions) == 1:
            # Fast path: no soft-delete filtering applicable/requested.
            obj = await session.get(self.model, id)
        else:
            stmt = select(self.model).where(*conditions)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()
        return self._to_dict(obj)

    async def bulk_create(self, data_list: List[Dict[str, Any]]) -> List[Any]:
        """Toplu kayıt oluştur."""
        if not data_list:
            return []

        session = self.session
        try:
            physical_columns = {c.name for c in self.model.__table__.columns}
            objs = []
            for data in data_list:
                dropped = set(data) - physical_columns
                if dropped:
                    logger.debug(
                        "%s.bulk_create: unknown fields dropped: %s",
                        self.model.__name__,
                        sorted(dropped),
                    )
                filtered_data = {k: v for k, v in data.items() if k in physical_columns}
                objs.append(self.model(**filtered_data))

            session.add_all(objs)
            await session.flush()

            # Fetch IDs (obj.id logic)
            pk_attr = inspect(self.model).primary_key[0].name
            return [getattr(obj, pk_attr) for obj in objs]
        except Exception as e:
            logger.error(f"Bulk create error for {self.model.__name__}: {e}")
            raise e

    async def create(self, **data: Any) -> Any:
        """Yeni kayıt oluştur (En güvenli ve ilkel yöntem)"""
        session = self.session
        try:
            # SADECE fiziksel kolonları metadata üzerinden filtrele
            physical_columns = {c.name for c in self.model.__table__.columns}
            dropped = set(data) - physical_columns
            if dropped:
                logger.debug(
                    "%s.create: unknown fields dropped: %s",
                    self.model.__name__,
                    sorted(dropped),
                )
            filtered_data = {k: v for k, v in data.items() if k in physical_columns}

            # [INJECTION] Eğer created_at kolonu varsa ve veride yoksa, otomatik ekle
            if "created_at" in physical_columns and "created_at" not in filtered_data:
                from datetime import datetime, timezone

                filtered_data["created_at"] = datetime.now(timezone.utc)

            # ORM implementation for better identity management and visibility
            new_obj = self.model(**filtered_data)
            session.add(new_obj)
            await session.flush()

            # Retrieve ID (SQLAlchemy will populate it after flush)
            pk_attr = inspect(self.model).primary_key[0].name
            new_id = getattr(new_obj, pk_attr)

            logger.debug(f"Created {self.model.__tablename__} record id={new_id}")
            return new_id
        except Exception as e:
            logger.error(f"Create error for {self.model.__name__}: {e}")
            raise e

    async def update(self, id: int, **data: Any) -> bool:
        """Kayıt güncelle"""
        if not data:
            return False

        session = self.session
        try:
            # Filter data to only include physical columns
            physical_columns = {c.name for c in self.model.__table__.columns}
            filtered_data = {k: v for k, v in data.items() if k in physical_columns}

            if not filtered_data:
                return False

            if "updated_at" in physical_columns and "updated_at" not in filtered_data:
                from datetime import datetime, timezone

                filtered_data["updated_at"] = datetime.now(timezone.utc)

            # ORM implementation for better identity management and consistency
            stmt = select(self.model).where(inspect(self.model).primary_key[0] == id)
            result = await session.execute(stmt)
            obj = result.scalar_one_or_none()

            if not obj:
                return False

            # Update object attributes — coerce StrEnum to .value (Python 3.11+
            # changed str(MyStrEnum.X) to return "MyStrEnum.X" instead of the value)
            import enum as _enum

            for key, value in filtered_data.items():
                setattr(
                    obj, key, value.value if isinstance(value, _enum.Enum) else value
                )

            await session.flush()
            return True
        except Exception as e:
            logger.error(f"Update error for {self.model.__name__}: {e}")
            raise e

    async def delete(self, id: int) -> bool:
        """Kayıt sil."""
        if hasattr(self.model, "aktif"):
            return await self.update(id, aktif=False)
        else:
            return await self.hard_delete(id)

    async def hard_delete(self, id: int) -> bool:
        """Kalıcı silme"""
        pk = inspect(self.model).primary_key[0]
        session = self.session
        try:
            stmt = delete(self.model).where(pk == id)
            result = await session.execute(stmt)
            await session.flush()
            return getattr(result, "rowcount", 0) > 0
        except Exception as e:
            raise e

    async def exists(self, id: int) -> bool:
        pk = inspect(self.model).primary_key[0]
        stmt = select(1).where(pk == id).limit(1)
        session = self.session
        result = await session.execute(stmt)
        return result.scalar() is not None

    async def count(
        self, filters: Optional[Dict[str, Any]] = None, include_inactive: bool = False
    ) -> int:
        """Kayıt sayısını getir (ORM, Filtre Destekli)."""
        stmt = select(func.count()).select_from(self.model)

        if hasattr(self.model, "aktif") and not include_inactive:
            stmt = stmt.where(getattr(self.model, "aktif").is_(True))

        if filters:
            from sqlalchemy import or_

            _filters = filters.copy()

            # Handle standardized search
            search_query = _filters.pop("search", None)
            if search_query and self.search_columns:
                search_filters = []
                for col in self.search_columns:
                    if hasattr(self.model, col):
                        search_filters.append(
                            getattr(self.model, col).ilike(f"%{search_query}%")
                        )
                if search_filters:
                    stmt = stmt.where(or_(*search_filters))

            # Handle regular equality and range filters
            for k, v in _filters.items():
                if v is None:
                    continue

                # Range filters
                if k.endswith("_ge"):
                    real_k = k[:-3]
                    if hasattr(self.model, real_k):
                        stmt = stmt.where(getattr(self.model, real_k) >= v)
                elif k.endswith("_le"):
                    real_k = k[:-3]
                    if hasattr(self.model, real_k):
                        stmt = stmt.where(getattr(self.model, real_k) <= v)
                # Equality filters
                elif hasattr(self.model, k):
                    stmt = stmt.where(getattr(self.model, k) == v)

        session = self.session
        try:
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Count error for {self.model.__name__}: {e}", exc_info=True)
            raise

    async def execute_query(
        self, query: str, params: Optional[dict] = None
    ) -> List[Dict[str, Any]]:
        """Custom Raw SQL support."""
        session = self.session
        try:
            result = await session.execute(text(query), params or {})
            return [dict(row) for row in result.mappings().all()]
        except Exception as e:
            logger.error(f"Database query error: {e}", exc_info=True)
            await session.rollback()
            raise

    async def execute_scalar(self, query: str, params: Optional[dict] = None) -> Any:
        session = self.session
        result = await session.execute(text(query), params or {})
        return result.scalar()
