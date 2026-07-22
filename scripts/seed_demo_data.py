"""
Demo seed data script — populates the database with realistic Turkish TIR fleet data.
Run: python scripts/seed_demo_data.py

Creates:
  - 5 vehicles (Merkez TIR fleet)
  - 5 drivers
  - 6 routes (major Turkish freight corridors)
  - 20 trips (spread over last 60 days)
  - 10 fuel records
"""

import asyncio
import os
import random
import sys
from datetime import date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from v2.modules.platform_infra.database.connection import engine
from v2.modules.driver.public import Sofor
from v2.modules.fleet.public import AracORM as Arac
from v2.modules.fuel.public import YakitAlimiORM as YakitAlimi
from v2.modules.location.public import Lokasyon
from v2.modules.trip.public import SeferORM as Sefer

random.seed(42)

ARACLAR = [
    {
        "plaka": "06 TK 001",
        "marka": "MERCEDES",
        "model": "ACTROS 1853",
        "yil": 2021,
        "tank_kapasitesi": 700,
        "hedef_tuketim": 32.0,
    },
    {
        "plaka": "34 LJ 002",
        "marka": "VOLVO",
        "model": "FH 500",
        "yil": 2020,
        "tank_kapasitesi": 650,
        "hedef_tuketim": 30.5,
    },
    {
        "plaka": "35 LJ 003",
        "marka": "SCANIA",
        "model": "R 450",
        "yil": 2022,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 29.0,
    },
    {
        "plaka": "01 LJ 004",
        "marka": "DAF",
        "model": "XF 480",
        "yil": 2019,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 31.5,
    },
    {
        "plaka": "16 LJ 005",
        "marka": "MAN",
        "model": "TGX 460",
        "yil": 2021,
        "tank_kapasitesi": 620,
        "hedef_tuketim": 30.0,
    },
]

SOFORLER = [
    {
        "ad_soyad": "Ahmet Yılmaz",
        "telefon": "5321112233",
        "ehliyet_sinifi": "E",
        "score": 1.1,
        "manual_score": 1.0,
    },
    {
        "ad_soyad": "Mehmet Demir",
        "telefon": "5332223344",
        "ehliyet_sinifi": "E",
        "score": 0.9,
        "manual_score": 0.9,
    },
    {
        "ad_soyad": "Ali Kaya",
        "telefon": "5343334455",
        "ehliyet_sinifi": "E",
        "score": 1.3,
        "manual_score": 1.2,
    },
    {
        "ad_soyad": "Hasan Şahin",
        "telefon": "5354445566",
        "ehliyet_sinifi": "E",
        "score": 0.8,
        "manual_score": 0.8,
    },
    {
        "ad_soyad": "Mustafa Çelik",
        "telefon": "5365556677",
        "ehliyet_sinifi": "E",
        "score": 1.0,
        "manual_score": 1.1,
    },
]

LOKASYONLAR = [
    {
        "cikis_yeri": "İstanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 454,
        "tahmini_sure_saat": 5.5,
        "zorluk": "Normal",
        "ascent_m": 1800,
        "descent_m": 2200,
    },
    {
        "cikis_yeri": "Ankara",
        "varis_yeri": "İzmir",
        "mesafe_km": 590,
        "tahmini_sure_saat": 7.0,
        "zorluk": "Normal",
        "ascent_m": 3200,
        "descent_m": 3500,
    },
    {
        "cikis_yeri": "İstanbul",
        "varis_yeri": "Bursa",
        "mesafe_km": 154,
        "tahmini_sure_saat": 2.5,
        "zorluk": "Kolay",
        "ascent_m": 800,
        "descent_m": 900,
    },
    {
        "cikis_yeri": "Ankara",
        "varis_yeri": "Konya",
        "mesafe_km": 261,
        "tahmini_sure_saat": 3.0,
        "zorluk": "Kolay",
        "ascent_m": 600,
        "descent_m": 700,
    },
    {
        "cikis_yeri": "İzmir",
        "varis_yeri": "Antalya",
        "mesafe_km": 320,
        "tahmini_sure_saat": 4.0,
        "zorluk": "Zor",
        "ascent_m": 5500,
        "descent_m": 5200,
    },
    {
        "cikis_yeri": "Ankara",
        "varis_yeri": "Samsun",
        "mesafe_km": 420,
        "tahmini_sure_saat": 5.0,
        "zorluk": "Normal",
        "ascent_m": 4200,
        "descent_m": 4000,
    },
]

DURUM_CHOICES = ["Completed", "Completed", "Completed", "Planned"]

ISTASYONLAR = [
    "BP Kuzey",
    "Shell Ankara",
    "Petrol Ofisi Istanbul",
    "Opet Bursa",
    "Total Konya",
]


async def seed():
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(select(Arac).limit(1))
        if result.scalar_one_or_none() is not None:
            if "--force" not in sys.argv:
                print(
                    "Database already has vehicles — skipping seed (use --force to override)."
                )
                return
            print("--force: clearing existing seed data...")
            from sqlalchemy import text

            # Delete in FK dependency order
            await session.execute(text("DELETE FROM yakit_alimlari"))
            await session.execute(text("DELETE FROM seferler"))
            await session.execute(text("DELETE FROM lokasyonlar"))
            await session.execute(text("DELETE FROM soforler"))
            await session.execute(text("DELETE FROM araclar"))
            await session.commit()
            print("  Cleared.")

        print("Seeding vehicles...")
        arac_ids = []
        for a in ARACLAR:
            arac = Arac(aktif=True, **a)
            session.add(arac)
            await session.flush()
            arac_ids.append(arac.id)
        await session.commit()
        print(f"  Created {len(ARACLAR)} vehicles: {arac_ids}")

        print("Seeding drivers...")
        sofor_ids = []
        for s in SOFORLER:
            sofor = Sofor(aktif=True, **s)
            session.add(sofor)
            await session.flush()
            sofor_ids.append(sofor.id)
        await session.commit()
        print(f"  Created {len(SOFORLER)} drivers: {sofor_ids}")

        print("Seeding routes...")
        lokasyon_ids = []
        for lok in LOKASYONLAR:
            lokasyon = Lokasyon(aktif=True, **lok)
            session.add(lokasyon)
            await session.flush()
            lokasyon_ids.append(lokasyon.id)
        await session.commit()
        print(f"  Created {len(LOKASYONLAR)} routes: {lokasyon_ids}")

        print("Seeding trips (20 trips over last 60 days)...")
        today = date.today()
        sefer_ids = []
        km_sayac = {aid: 150000 + random.randint(0, 20000) for aid in arac_ids}
        for i in range(20):
            trip_date = today - timedelta(days=random.randint(1, 60))
            arac_id = random.choice(arac_ids)
            sofor_id = random.choice(sofor_ids)
            lok_id = random.choice(lokasyon_ids)
            lok_data = LOKASYONLAR[lokasyon_ids.index(lok_id)]
            mesafe = lok_data["mesafe_km"]
            bos_agirlik_kg = 8500  # typical TIR tare weight
            net_kg = random.randint(8000, 24000)
            dolu_agirlik_kg = bos_agirlik_kg + net_kg
            tuketim = round(
                mesafe * lok_data.get("ascent_m", 0) * 0.00002
                + mesafe * 0.30
                + random.uniform(-5, 10),
                1,
            )

            sefer = Sefer(
                tarih=trip_date,
                saat=f"{random.randint(6, 18):02d}:00",
                arac_id=arac_id,
                sofor_id=sofor_id,
                guzergah_id=lok_id,
                cikis_yeri=lok_data["cikis_yeri"],
                varis_yeri=lok_data["varis_yeri"],
                mesafe_km=mesafe,
                bos_agirlik_kg=bos_agirlik_kg,
                dolu_agirlik_kg=dolu_agirlik_kg,
                net_kg=net_kg,
                ton=round(net_kg / 1000, 2),
                bos_sefer=False,
                durum=random.choice(DURUM_CHOICES),
                tahmini_tuketim=tuketim,
                tuketim=round(tuketim + random.uniform(-3, 3), 1),
                ascent_m=lok_data.get("ascent_m", 0),
                descent_m=lok_data.get("descent_m", 0),
            )
            session.add(sefer)
            await session.flush()
            sefer_ids.append(sefer.id)
            km_sayac[arac_id] += mesafe
        await session.commit()
        print(f"  Created 20 trips: {sefer_ids[:5]}...")

        print("Seeding fuel records (10 records)...")
        yakit_ids = []
        for i in range(10):
            fuel_date = today - timedelta(days=random.randint(1, 55))
            arac_id = random.choice(arac_ids)
            litre = round(random.uniform(200, 550), 1)
            fiyat = round(random.uniform(40.5, 48.0), 2)
            yakit = YakitAlimi(
                tarih=fuel_date,
                arac_id=arac_id,
                istasyon=random.choice(ISTASYONLAR),
                fiyat_tl=fiyat,
                litre=litre,
                toplam_tutar=round(litre * fiyat, 2),
                km_sayac=km_sayac[arac_id] + random.randint(0, 5000),
                depo_durumu=random.choice(["Doldu", "Yarisi", "Ceyrek"]),
                durum="Onaylandi",
                aktif=True,
            )
            session.add(yakit)
            await session.flush()
            yakit_ids.append(yakit.id)
        await session.commit()
        print(f"  Created 10 fuel records: {yakit_ids}")

        print("\nSeed complete!")
        print(
            f"  Vehicles: {len(ARACLAR)} | Drivers: {len(SOFORLER)} | Routes: {len(LOKASYONLAR)}"
        )
        print("  Trips: 20 | Fuel records: 10")


if __name__ == "__main__":
    asyncio.run(seed())
