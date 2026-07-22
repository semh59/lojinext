import asyncio
import os
import sys

import httpx
from sqlalchemy import select

# Add project root to path
sys.path.append(os.getcwd())

from app.config import settings
from v2.modules.platform_infra.database.connection import AsyncSessionLocal
from v2.modules.location.public import Lokasyon

# COORDINATE MAPPING
CITY_COORDS = {
    "İstanbul": (28.9784, 41.0082),
    "Ankara": (32.8597, 39.9334),
    "İzmir": (27.1428, 38.4237),
    "Bursa": (29.0610, 40.1885),
    "Antalya": (30.7133, 36.8969),
    "Adana": (35.3308, 36.9914),
    "Samsun": (36.3300, 41.2867),
    "Trabzon": (39.7168, 41.0027),
    "Edirne": (26.5557, 41.6771),
    "Mersin": (34.6415, 36.8121),
    "Antep": (37.3833, 37.0662),
    "Sivas": (37.0125, 39.7477),
}

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"


async def enrich_locations():
    """ORS kullanarak lokasyon verilerini zenginleştirir"""
    print("🚀 Starting Geographic Metadata Enrichment...")

    api_key = settings.OPENROUTESERVICE_API_KEY
    if not api_key:
        print("❌ Error: OPENROUTESERVICE_API_KEY is missing.")
        return

    async with AsyncSessionLocal() as db:
        stmt = select(Lokasyon)
        result = await db.execute(stmt)
        locations = result.scalars().all()

        print(f"📊 Found {len(locations)} location records.")

        async with httpx.AsyncClient(timeout=30.0) as client:
            for loc in locations:
                start_coords = CITY_COORDS.get(loc.cikis_yeri)
                end_coords = CITY_COORDS.get(loc.varis_yeri)

                if not start_coords or not end_coords:
                    print(
                        f"⚠️ Skip: {loc.cikis_yeri} -> {loc.varis_yeri} (Coords not found)"
                    )
                    continue

                print(
                    f"🌐 Fetching ORS data for {loc.cikis_yeri} -> {loc.varis_yeri}..."
                )

                try:
                    body = {
                        "coordinates": [start_coords, end_coords],
                        "elevation": True,
                        "extra_info": ["steepness"],
                    }
                    headers = {
                        "Authorization": api_key,
                        "Content-Type": "application/json",
                    }

                    response = await client.post(ORS_URL, json=body, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        feature = data["features"][0]
                        props = feature["properties"]
                        summary = props["summary"]

                        # Elevation data (GeoJSON extracts from props)
                        ascent = props.get("ascent", 0)
                        descent = props.get("descent", 0)
                        distance = summary["distance"] / 1000.0  # m to km

                        # Fix Zorluk based on ascent
                        zorluk = "Normal"
                        if ascent > 1500:
                            zorluk = "Zor"
                        elif ascent < 500:
                            zorluk = "Kolay"

                        # Update Location
                        loc.ascent_m = float(ascent)
                        loc.descent_m = float(descent)
                        loc.api_mesafe_km = float(distance)
                        loc.zorluk = zorluk
                        loc.cikis_lat, loc.cikis_lon = start_coords[1], start_coords[0]
                        loc.varis_lat, loc.varis_lon = end_coords[1], end_coords[0]

                        print(f"   ✅ Success: {ascent}m ascent, {zorluk} difficulty.")
                    else:
                        print(f"   ❌ API Error: {response.status_code}")

                except Exception as e:
                    print(f"   ❌ Error: {e}")

                # Rate limit protection
                await asyncio.sleep(1)

        await db.commit()
        print("\n✨ Enrichment Complete! All metadata committed to DB.")


if __name__ == "__main__":
    asyncio.run(enrich_locations())
