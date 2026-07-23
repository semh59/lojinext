"""Reaktivasyonda teknik özelliklerin geçilmesi — canlı-hazırlık denetimi
bulgusu (2026-07-09), fix kanıtı.

Önceki davranış: AracService._create_arac_impl'in reaktivasyon dalı sadece
marka/model/yil/tank_kapasitesi/hedef_tuketim/notlar'ı güncelliyordu;
bos_agirlik_kg/hava_direnc_katsayisi/on_kesit_alani_m2/motor_verimliligi/
lastik_direnc_katsayisi/maks_yuk_kapasitesi_kg/dingil_sayisi/yakit_tipi/
muayene_tarihi SESSİZCE atılıyordu — bu alanlar PredictionService.
_build_vehicle_specs'in fizik-tabanlı yakıt tahmininde okuduğu gerçek
girdiler, yani reaktive edilen araç eski (yanlış) teknik özelliklerle
tahmin üretmeye devam ediyordu. DorseService.create ise reaktivasyon/
duplicate-check'i HİÇ yapmıyordu (AracService ile asimetrik).

Gerçek DB + gerçek servis; sadece event_bus MagicMock (dış altyapı).
"""

import pytest
from sqlalchemy import insert, select

from v2.modules.fleet.application.create_trailer import create_trailer
from v2.modules.fleet.application.create_vehicle import create_vehicle
from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.fleet.public import Dorse
from v2.modules.fleet.schemas import AracCreate, DorseCreate

pytestmark = pytest.mark.integration


async def _seed_arac(db_session, plaka: str) -> int:
    res = await db_session.execute(
        insert(Arac).values(
            plaka=plaka,
            marka="EskiMarka",
            model="EskiModel",
            aktif=False,
            bos_agirlik_kg=1234.0,
            hava_direnc_katsayisi=0.99,
            motor_verimliligi=0.15,
            maks_yuk_kapasitesi_kg=9999,
        )
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


async def _seed_dorse(db_session, plaka: str, *, aktif: bool = True) -> int:
    res = await db_session.execute(
        insert(Dorse).values(
            plaka=plaka,
            marka="EskiDorseMarka",
            aktif=aktif,
            bos_agirlik_kg=1111.0,
            maks_yuk_kapasitesi_kg=8888,
        )
    )
    await db_session.commit()
    return res.inserted_primary_key[0]


class TestVehicleReactivationCarriesTechnicalSpecs:
    async def test_reactivation_updates_physics_fields(self, db_session):
        plaka = "34 SPEC 001"
        seeded_id = await _seed_arac(db_session, plaka)

        data = AracCreate(
            plaka=plaka,
            marka="YeniMarka",
            model="YeniModel",
            yil=2024,
            tank_kapasitesi=700,
            bos_agirlik_kg=9500.0,
            hava_direnc_katsayisi=0.55,
            motor_verimliligi=0.42,
            maks_yuk_kapasitesi_kg=27000,
        )
        result_id = await create_vehicle(data)
        assert result_id == seeded_id

        row = (
            await db_session.execute(select(Arac).where(Arac.id == seeded_id))
        ).scalar_one()
        assert row.aktif is True
        # Bu satırlar fix'ten ÖNCE eski (1234.0/0.99/0.15/9999) kalırdı.
        assert row.bos_agirlik_kg == 9500.0
        assert row.hava_direnc_katsayisi == 0.55
        assert row.motor_verimliligi == 0.42
        assert row.maks_yuk_kapasitesi_kg == 27000


class TestDorseServiceDuplicateAndReactivation:
    def _repo(self, db_session) -> DorseRepository:
        return DorseRepository(session=db_session)

    async def test_create_reactivates_passive_trailer_with_new_specs(self, db_session):
        plaka = "34 DSPEC 001"
        seeded_id = await _seed_dorse(db_session, plaka, aktif=False)

        repo = self._repo(db_session)
        payload = DorseCreate(
            plaka=plaka,
            marka="YeniDorseMarka",
            bos_agirlik_kg=7000.0,
            maks_yuk_kapasitesi_kg=30000,
        )
        result_id = await create_trailer(repo, **payload.model_dump())
        assert result_id == seeded_id

        row = (
            await db_session.execute(select(Dorse).where(Dorse.id == seeded_id))
        ).scalar_one()
        assert row.aktif is True
        assert row.marka == "YeniDorseMarka"
        # Fix'ten önce DorseService.create hiç reaktivasyon yapmıyordu —
        # bu satır IntegrityError ile patlardı (plaka unique constraint).
        assert row.bos_agirlik_kg == 7000.0
        assert row.maks_yuk_kapasitesi_kg == 30000

    async def test_create_raises_for_existing_active_plate(self, db_session):
        plaka = "34 DSPEC 002"
        await _seed_dorse(db_session, plaka, aktif=True)

        repo = self._repo(db_session)
        payload = DorseCreate(plaka=plaka, marka="Baska")
        with pytest.raises(ValueError, match="already exists"):
            await create_trailer(repo, **payload.model_dump())

    async def test_create_fresh_plate_still_inserts(self, db_session):
        repo = self._repo(db_session)
        payload = DorseCreate(plaka="34 DSPEC 003", marka="TamamenYeni")
        new_id = await create_trailer(repo, **payload.model_dump())
        assert new_id is not None

        row = (
            await db_session.execute(select(Dorse).where(Dorse.id == new_id))
        ).scalar_one()
        assert row.plaka == "34 DSPEC 003"
        assert row.aktif is True
