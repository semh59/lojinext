import asyncio

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import select

from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.location.public import Lokasyon
from v2.modules.trip.public import SeferORM as Sefer

load_dotenv()


async def prepare_data():
    print("📊 Preparing training data with route analysis...")
    async with AsyncSessionLocal() as session:
        # Fetch trips and locations
        stmt = select(Sefer, Lokasyon).join(Lokasyon, Sefer.guzergah_id == Lokasyon.id)
        result = await session.execute(stmt)
        rows = result.all()

        data = []
        for sefer, lokasyon in rows:
            # Check if route analysis exists
            analysis = lokasyon.route_analysis or {}

            if not analysis:
                # print(f"⚠️ Sefer {sefer.id}: Route analysis eksik")
                continue

            # Feature extraction
            # In our implementation, analysis might be { motorway: {...}, ... }
            # OR { highway: {...}, other: {...} }
            def sum_km(cat_dict):
                if not cat_dict:
                    return 0.0
                return float(
                    cat_dict.get("flat", 0)
                    + cat_dict.get("up", 0)
                    + cat_dict.get("down", 0)
                )

            mesafe = float(sefer.mesafe_km or 0)
            if mesafe <= 0:
                continue

            # Check for highway/other structure first
            if "highway" in analysis and "other" in analysis:
                motorway_km = sum_km(analysis.get("highway"))
                primary_km = sum_km(analysis.get("other"))
                trunk_km = 0.0
                residential_km = 0.0
                unclassified_km = 0.0
            else:
                motorway_km = sum_km(analysis.get("motorway"))
                primary_km = sum_km(analysis.get("primary"))
                trunk_km = sum_km(analysis.get("trunk"))
                residential_km = sum_km(analysis.get("residential"))
                unclassified_km = sum_km(analysis.get("unclassified"))

            row = {
                "id": sefer.id,
                "arac_id": sefer.arac_id,
                "mesafe_km": mesafe,
                "ton": float(sefer.ton or 0),
                "ascent_m": float(lokasyon.ascent_m or 0),
                "descent_m": float(lokasyon.descent_m or 0),
                # Ratios
                "motorway_ratio": motorway_km / mesafe,
                "primary_ratio": (primary_km + trunk_km) / mesafe,
                "residential_ratio": residential_km / mesafe,
                "unclassified_ratio": unclassified_km / mesafe,
                # Target
                "gercek_tuketim": float(sefer.tuketim or 0),
            }
            data.append(row)

        if not data:
            print("❌ No data found with route analysis.")
            return None

        df = pd.DataFrame(data)

        # Veri kalitesi kontrol
        print("Veri hazırlama tamamlandı.")
        print(f"Toplam sefer: {len(df)}")
        print(
            f"Dolu/Toplam: {len(df)} / {len(rows)} ({len(df) / len(rows) * 100:.1f}%)"
        )

        # Save
        output_path = "training_data_with_routes.csv"
        df.to_csv(output_path, index=False)
        print(f"\n✅ Veri kaydedildi: {output_path}")

        return df


if __name__ == "__main__":
    asyncio.run(prepare_data())
