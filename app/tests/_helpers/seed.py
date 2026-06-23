"""Real-row seed helpers for 0-mock tests. No mocks — direct ORM inserts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.database.models import Arac, Sefer, SistemKonfig, Sofor, YakitAlimi


async def seed_arac(
    session,
    *,
    plaka: str = "34ABC001",
    marka: str = "MAN",
    bos_agirlik_kg: float = 14000.0,
    hedef_tuketim: float = 25.0,
    aktif: bool = True,
) -> Arac:
    """Insert a minimal Arac row and flush. Returns the ORM instance."""
    arac = Arac(
        plaka=plaka,
        marka=marka,
        bos_agirlik_kg=bos_agirlik_kg,
        hedef_tuketim=hedef_tuketim,
        aktif=aktif,
        is_deleted=False,
    )
    session.add(arac)
    await session.flush()
    return arac


async def seed_sofor(
    session,
    *,
    ad_soyad: str = "Ali Veli",
    aktif: bool = True,
    telegram_id: str | None = None,
    **extra,
) -> Sofor:
    """Insert a minimal Sofor row and flush. Returns the ORM instance."""
    sofor = Sofor(
        ad_soyad=ad_soyad,
        aktif=aktif,
        is_deleted=False,
        telegram_id=telegram_id,
        **extra,
    )
    session.add(sofor)
    await session.flush()
    return sofor


async def seed_sefer(
    session,
    *,
    arac_id: int,
    sofor_id: int,
    tarih: date | None = None,
    durum: str = "Planned",
    mesafe_km: float = 450.0,
    net_kg: int = 12000,
    bos_agirlik_kg: int = 14000,
    cikis_yeri: str = "Istanbul",
    varis_yeri: str = "Ankara",
    tahmini_tuketim: float | None = None,
    tuketim: float | None = None,
    guzergah_id: int | None = None,
    **extra,
) -> Sefer:
    """Insert a Sefer row respecting the net_kg check constraint.

    Constraint: net_kg = dolu_agirlik_kg - bos_agirlik_kg
    Durum must be one of: 'Planned', 'Completed', 'Cancelled'
    sofor_id is NOT NULL on the model.
    """
    tarih = tarih or date.today()
    dolu_agirlik_kg = bos_agirlik_kg + net_kg
    sefer = Sefer(
        arac_id=arac_id,
        sofor_id=sofor_id,
        tarih=tarih,
        durum=durum,
        mesafe_km=mesafe_km,
        net_kg=net_kg,
        bos_agirlik_kg=bos_agirlik_kg,
        dolu_agirlik_kg=dolu_agirlik_kg,
        cikis_yeri=cikis_yeri,
        varis_yeri=varis_yeri,
        tahmini_tuketim=tahmini_tuketim,
        tuketim=tuketim,
        guzergah_id=guzergah_id,
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        **extra,
    )
    session.add(sefer)
    await session.flush()
    return sefer


async def seed_yakit(
    session,
    *,
    arac_id: int,
    km_sayac: int,
    litre: float,
    tarih: date | None = None,
    fiyat_tl: float = 40.0,
    istasyon: str | None = None,
    fis_no: str | None = None,
    depo_durumu: str = "Bilinmiyor",
    durum: str = "Bekliyor",
    **extra,
) -> YakitAlimi:
    """Insert a minimal YakitAlimi row and flush. Returns the ORM instance.

    Required NOT-NULL / constrained columns:
      - litre > 0  (CheckConstraint)
      - fiyat_tl > 0  (CheckConstraint)
      - toplam_tutar: computed as fiyat_tl * litre
      - durum IN ('Bekliyor', 'Onaylandı', 'Reddedildi')
    """
    toplam_tutar = round(fiyat_tl * litre, 2)
    row = YakitAlimi(
        arac_id=arac_id,
        km_sayac=km_sayac,
        litre=Decimal(str(litre)),
        fiyat_tl=Decimal(str(fiyat_tl)),
        toplam_tutar=Decimal(str(toplam_tutar)),
        tarih=tarih or date.today(),
        istasyon=istasyon,
        fis_no=fis_no,
        depo_durumu=depo_durumu,
        durum=durum,
        aktif=True,
        **extra,
    )
    session.add(row)
    await session.flush()
    return row


async def seed_sistem_konfig(
    session,
    *,
    anahtar: str,
    deger: object,
    tip: str = "json",
    grup: str = "genel",
) -> SistemKonfig:
    """Insert a SistemKonfig row and flush. Returns the ORM instance.

    Required NOT NULL fields beyond anahtar/deger: tip and grup.
    """
    row = SistemKonfig(
        anahtar=anahtar,
        deger=deger,
        tip=tip,
        grup=grup,
    )
    session.add(row)
    await session.flush()
    return row
