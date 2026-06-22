import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Load env explicitly
load_dotenv(os.path.join(project_root, ".env"))

from contextlib import asynccontextmanager  # noqa: E402

from sqlalchemy import select, update  # noqa: E402

from app.database.connection import AsyncSessionLocal  # noqa: E402
from app.database.models import Lokasyon, Sefer  # noqa: E402
from app.infrastructure.logging.logger import get_logger  # noqa: E402
from app.infrastructure.routing.openroute_client import OpenRouteClient  # noqa: E402

logger = get_logger(__name__)


@asynccontextmanager
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def enrich_data():
    """
    Mevcut sefer verilerini OpenRouteService analizi ile zenginleştirir.
    'rota_detay' alanına yol tipi ve eğim verilerini ekler.
    """
    client = OpenRouteClient()
    if not client.api_key:
        logger.error("API Key not found!")
        return

    print("Starting data enrichment process...", flush=True)

    async with get_session() as session:
        # 1. Tamamlanmış ve analizi eksik seferleri getir
        # Not: JSON kontrolü veritabanına göre değişebilir, basitçe hepsini alıp kodda kontrol edelim
        # Also ensure we only fetch what we need if possible, but ORM fetches objects
        stmt = select(Sefer).where(Sefer.durum == "Completed")
        result = await session.execute(stmt)
        seferler = result.scalars().all()

        print(f"Checking {len(seferler)} completed trips for enrichment...", flush=True)

        updated_count = 0
        skipped_count = 0
        error_count = 0

        for sefer in seferler:
            try:
                # Check if already enriched (basit kontrol)
                if sefer.rota_detay and "route_analysis" in sefer.rota_detay:
                    # logger.debug(f"Sefer {sefer.id} already enriched. Skipping.")
                    skipped_count += 1
                    continue

                # Lokasyon koordinatlarını bulmaya çalış
                origin = None
                destination = None

                # 1. Güzergah (Lokasyon) varsa oradan al
                if sefer.guzergah_id:
                    lokasyon = await session.get(Lokasyon, sefer.guzergah_id)
                    if lokasyon and lokasyon.cikis_lat and lokasyon.varis_lat:
                        origin = (lokasyon.cikis_lat, lokasyon.cikis_lon)
                        destination = (lokasyon.varis_lat, lokasyon.varis_lon)

                # 2. Koordinat yoksa Geocoding ile bulmaya çalış
                if not origin:
                    logger.info(f"Geocoding origin: {sefer.cikis_yeri}")
                    origin = await client.geocode(sefer.cikis_yeri)
                    if origin and sefer.guzergah_id:
                        await session.execute(
                            update(Lokasyon)
                            .where(Lokasyon.id == sefer.guzergah_id)
                            .values(cikis_lat=origin[0], cikis_lon=origin[1])
                        )

                if not destination:
                    logger.info(f"Geocoding destination: {sefer.varis_yeri}")
                    destination = await client.geocode(sefer.varis_yeri)
                    if destination and sefer.guzergah_id:
                        await session.execute(
                            update(Lokasyon)
                            .where(Lokasyon.id == sefer.guzergah_id)
                            .values(varis_lat=destination[0], varis_lon=destination[1])
                        )

                if not origin or not destination:
                    logger.warning(
                        f"Sefer {sefer.id} still has no coordinates after geocoding. Skipping."
                    )
                    skipped_count += 1
                    continue

                # Analiz yap
                logger.info(
                    f"Analyzing Trip {sefer.id}: {sefer.cikis_yeri} -> {sefer.varis_yeri}"
                )

                # include_details=True ile detaylı analiz al
                analysis = client.get_distance(
                    origin=origin,
                    destination=destination,
                    use_cache=True,  # Cache kullan
                    include_details=True,
                )

                if analysis:
                    # Mevcut rota_detay'ı koru veya yeni oluştur
                    current_detay = dict(sefer.rota_detay) if sefer.rota_detay else {}

                    # Analiz sonuçlarını ekle
                    current_detay["route_analysis"] = analysis.get("details")
                    current_detay["api_mesafe_km"] = analysis.get("distance_km")
                    current_detay["ascent_m"] = analysis.get("ascent_m")
                    current_detay["descent_m"] = analysis.get("descent_m")

                    # Veritabanını güncelle
                    await session.execute(
                        update(Sefer)
                        .where(Sefer.id == sefer.id)
                        .values(
                            rota_detay=current_detay,
                            ascent_m=analysis.get("ascent_m"),
                            descent_m=analysis.get("descent_m"),
                            flat_distance_km=0,  # Hesaplamadım şu an
                        )
                    )
                    updated_count += 1
                    print(
                        f"Enriched Sefer {sefer.id} ({updated_count}/{len(seferler)})",
                        flush=True,
                    )

                    if updated_count % 5 == 0:
                        await session.commit()
                        print("Committed batch.", flush=True)

                    # Rate limit dostu bekleme (cache varsa hızlı geçer)
                    await asyncio.sleep(0.1)
                else:
                    error_count += 1
                    print(f"Failed to analyze Sefer {sefer.id}", flush=True)

            except Exception as e:
                logger.error(f"Error enriching Sefer {sefer.id}: {e}")
                error_count += 1

        await session.commit()

    logger.info("Enrichment Completed.")
    logger.info(f"Updated: {updated_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Errors: {error_count}")


if __name__ == "__main__":
    asyncio.run(enrich_data())
