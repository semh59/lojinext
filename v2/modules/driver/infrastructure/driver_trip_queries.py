"""Şofore özel sefer sorguları (dalga 14 — trip'in ``sefer_repo.py``'sinden taşındı).

``get_by_sofor_id``, ``get_with_route_analysis``,
``get_driver_trips_with_route_analysis``, ``get_driver_trips_by_route_type``,
``get_recent_trips_batch``, ``search_driver_ids_by_name`` (eski
``_search_driver_ids_by_name``) — hepsi ``seferler`` tablosunu (trip'in
tablosu) sorguluyor ama şoför-özel raporlama/arama için var; driver'ın kendi
``driver_metrics_queries.py``'siyle aynı gerekçeyle (B.1) serbest fonksiyon
olarak tutuldu — tek-tablo CRUD değil, salt-okunur sorgu kümesi.

Şema not: ``Sofor``/``SoforAdSoyadTrigram`` ORM modelleri henüz paylaşılan
``app/database/models.py``'de (models.py bölünmesi ayrı bir görev) — bu
dosyanın onları doğrudan import etmesi mevcut projedeki tüm diğer
modüllerle aynı, kabul edilmiş desendir. ``Sefer`` dalga 16 (task #58)'de
trip modülüne taşındı, ``trip.public.SeferORM`` üzerinden import edilir.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text

from app.database.unit_of_work import UnitOfWork
from v2.modules.driver.infrastructure.models import Sofor, SoforAdSoyadTrigram
from v2.modules.trip.public import SeferORM as Sefer


async def _resolve_session(uow: Optional[Any]):
    return getattr(uow, "session", None) if uow is not None else None


async def get_by_sofor_id(
    sofor_id: int,
    limit: int = 10,
    onay_durumu: Optional[str] = None,
    uow: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Şofore ait sefer listesi (en yeni önce). Opsiyonel onay_durumu filtresi."""

    async def _run(session) -> List[Dict[str, Any]]:
        stmt = select(Sefer).where(Sefer.sofor_id == sofor_id, ~Sefer.is_deleted)
        if onay_durumu:
            stmt = stmt.where(Sefer.onay_durumu == onay_durumu)
        stmt = stmt.order_by(Sefer.tarih.desc()).limit(min(limit, 500))
        result = await session.execute(stmt)
        rows = []
        for s in result.scalars().all():
            d = s.__dict__.copy()
            d.pop("_sa_instance_state", None)
            rows.append(d)
        return rows

    session = await _resolve_session(uow)
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)


async def get_with_route_analysis(
    days: int = 90, limit: int = 200, uow: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Son N günün route_analysis ve gercek_tuketim dolu seferlerini döndürür."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async def _run(session) -> List[Dict[str, Any]]:
        result = await session.execute(
            select(Sefer)
            .where(
                Sefer.created_at >= cutoff,
                Sefer.rota_detay.isnot(None),
                Sefer.tuketim.isnot(None),
                ~Sefer.is_deleted,
            )
            .limit(limit)
        )
        return [
            {
                "id": s.id,
                "mesafe_km": s.mesafe_km,
                "route_analysis": (s.rota_detay or {}).get("route_analysis")
                or s.rota_detay
                or {},
                "gercek_tuketim": s.tuketim,
            }
            for s in result.scalars().all()
        ]

    session = await _resolve_session(uow)
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)


async def get_driver_trips_with_route_analysis(
    sofor_id: int,
    limit: int = 200,
    days: int = 365,
    uow: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Şoförün rota analizi olan tamamlanmış seferlerini ham olarak döner.

    Route-type bucketing service katmanında tek geçişle yapılır — 4 ayrı
    sorgu yerine 1 sorgu (N+1 önlenir).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async def _run(session) -> List[Dict[str, Any]]:
        result = await session.execute(
            select(Sefer)
            .where(
                Sefer.sofor_id == sofor_id,
                Sefer.tuketim.isnot(None),
                Sefer.tahmini_tuketim.isnot(None),
                Sefer.rota_detay.isnot(None),
                Sefer.created_at >= cutoff,
                ~Sefer.is_deleted,
            )
            .order_by(Sefer.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": s.id,
                "gercek_tuketim": float(s.tuketim or 0),
                "tahmini_tuketim": float(s.tahmini_tuketim or 0),
                "rota_detay": s.rota_detay or {},
            }
            for s in result.scalars().all()
        ]

    session = await _resolve_session(uow)
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)


async def get_driver_trips_by_route_type(
    sofor_id: int,
    route_type: str,
    limit: int = 50,
    uow: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Şofore ait tamamlanmış seferleri döndürür; route_type'a göre Python tarafında filtreler."""
    from v2.modules.driver.public import classify_route

    cutoff = datetime.now(timezone.utc) - timedelta(days=365)

    async def _run(session) -> List[Dict[str, Any]]:
        result = await session.execute(
            select(Sefer)
            .where(
                Sefer.sofor_id == sofor_id,
                Sefer.tuketim.isnot(None),
                Sefer.tahmini_tuketim.isnot(None),
                Sefer.rota_detay.isnot(None),
                Sefer.created_at >= cutoff,
                ~Sefer.is_deleted,
            )
            .order_by(Sefer.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": s.id,
                "gercek_tuketim": s.tuketim,
                "tahmini_tuketim": s.tahmini_tuketim,
            }
            for s in result.scalars().all()
            if classify_route(
                (s.rota_detay or {}).get("route_analysis") or s.rota_detay or {}
            )
            == route_type
        ]

    session = await _resolve_session(uow)
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)


async def get_recent_trips_batch(
    sofor_ids: List[int],
    limit_per_driver: int = 10,
    uow: Optional[Any] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """N şoförün son limit_per_driver seferini tek sorguda çeker.

    Window function (ROW_NUMBER) ile her şoför için ayrı sıralama yapar;
    N şoför için N ayrı get_all çağrısını (N+1) elimine eder.
    Sonucu {sofor_id: [trip_dict, ...]} olarak döner.
    """
    if not sofor_ids:
        return {}

    async def _run(session) -> Dict[int, List[Dict[str, Any]]]:
        rows = (
            (
                await session.execute(
                    text("""
                    WITH ranked AS (
                        SELECT
                            id, sofor_id, arac_id, tarih, mesafe_km,
                            tuketim, tahmini_tuketim, net_kg, ton,
                            ascent_m, descent_m,
                            ROW_NUMBER() OVER (
                                PARTITION BY sofor_id
                                ORDER BY tarih DESC
                            ) AS rn
                        FROM seferler
                        WHERE sofor_id = ANY(:ids)
                          AND is_deleted = FALSE
                    )
                    SELECT * FROM ranked WHERE rn <= :lim
                """),
                    {"ids": sofor_ids, "lim": limit_per_driver},
                )
            )
            .mappings()
            .all()
        )
        result: Dict[int, List[Dict[str, Any]]] = {}
        for r in rows:
            sid = int(r["sofor_id"])
            result.setdefault(sid, []).append(dict(r))
        return result

    session = await _resolve_session(uow)
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)


async def search_driver_ids_by_name(
    search: str, uow: Optional[Any] = None
) -> List[int]:
    """Substring-search candidate driver IDs (Tier E madde 26).

    Sofor.ad_soyad is encrypted at rest, so the general trip search box
    can't ILIKE it directly. Trigram-hash membership gives a candidate
    superset (collisions possible); each candidate's real name is then
    decrypted and re-checked for the actual substring before it's used
    to filter Sefer.sofor_id. (trip'in ``infrastructure/repository.py::
    get_all``'ının genel arama özelliği bunu çağırır.)
    """
    from app.infrastructure.security.pii_encryption import trigram_blind_indexes

    async def _run(session) -> List[int]:
        hashes = trigram_blind_indexes(search)
        if not hashes:
            return []
        candidate_ids = (
            (
                await session.execute(
                    select(SoforAdSoyadTrigram.sofor_id)
                    .where(SoforAdSoyadTrigram.trigram_hash.in_(hashes))
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        if not candidate_ids:
            return []
        needle = search.strip().upper()
        drivers = (
            await session.execute(
                select(Sofor.id, Sofor.ad_soyad).where(Sofor.id.in_(candidate_ids))
            )
        ).all()
        return [d.id for d in drivers if needle in (d.ad_soyad or "").upper()]

    session = await _resolve_session(uow)
    if session is not None:
        return await _run(session)
    async with UnitOfWork() as owned_uow:
        return await _run(owned_uow.session)
