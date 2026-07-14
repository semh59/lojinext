"""Use-case: bir aracın tüm yakıt periyotlarını yeniden hesapla, seferlerle eşleştir ve kaydet."""

from datetime import date
from decimal import Decimal

from app.core.entities import Sefer, YakitAlimi
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.cache.cache_manager import get_cache_manager
from v2.modules.fuel.domain.period_matcher import (
    sync_create_fuel_periods,
    sync_match_periods_with_trips,
)


async def recalculate_vehicle_periods(
    arac_id: int, yakit_repo=None, sefer_repo=None
) -> None:
    """Bir aracın tüm yakıt periyotlarını yeniden hesapla, seferlerle eşleştir ve kaydet (Async)."""
    if yakit_repo is None:
        from v2.modules.fuel.infrastructure.repository import get_yakit_repo

        yakit_repo = get_yakit_repo()

    if sefer_repo is None:
        from app.database.repositories.sefer_repo import get_sefer_repo

        sefer_repo = get_sefer_repo()

    raw_alimlar_result = await yakit_repo.get_all(
        arac_id=arac_id, limit=2000, desc=False
    )
    raw_alimlar = (
        raw_alimlar_result.get("items", [])
        if isinstance(raw_alimlar_result, dict)
        else raw_alimlar_result
    )
    fuel_records = [
        YakitAlimi(
            id=r["id"],
            tarih=date.fromisoformat(r["tarih"])
            if isinstance(r["tarih"], str)
            else r["tarih"],
            arac_id=r["arac_id"],
            istasyon=r["istasyon"],
            fiyat_tl=Decimal(str(round(float(r["fiyat_tl"]), 2))),
            litre=float(r["litre"]),
            km_sayac=int(r["km_sayac"]),
            fis_no=r["fis_no"],
            depo_durumu=r.get("depo_durumu") or "Bilinmiyor",
        )
        for r in raw_alimlar
    ]

    raw_seferler = await sefer_repo.get_all(arac_id=arac_id, limit=5000, desc=False)
    all_trips = [
        Sefer(
            id=s["id"],
            tarih=date.fromisoformat(s["tarih"])
            if isinstance(s["tarih"], str)
            else s["tarih"],
            arac_id=s["arac_id"],
            sofor_id=s["sofor_id"],
            cikis_yeri=s["cikis_yeri"],
            varis_yeri=s["varis_yeri"],
            mesafe_km=int(s["mesafe_km"]),
            net_kg=int(s["net_kg"]),
            durum=s["durum"],
        )
        for s in raw_seferler
    ]

    periods = sync_create_fuel_periods(fuel_records)
    if periods:
        async with UnitOfWork() as uow:
            await uow.yakit_repo.save_fuel_periods(periods, clear_existing=True)
            matches = sync_match_periods_with_trips(periods, all_trips)
            updated_trips = []
            for m in matches:
                updated_trips.extend(m.seferler)
            if updated_trips:
                await uow.sefer_repo.update_trips_fuel_data(updated_trips)
            await uow.commit()

    cache = get_cache_manager()
    cache.delete_pattern(f"arac:{arac_id}:*")
    cache.delete_pattern("fleet:avg:*")
    cache.delete_pattern("dashboard:*")
