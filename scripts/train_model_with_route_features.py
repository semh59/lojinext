import asyncio
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import distinct, select

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Load env explicitly
load_dotenv(os.path.join(project_root, ".env"))

from app.database.connection import AsyncSessionLocal
from app.database.models import Sefer
from app.infrastructure.logging.logger import get_logger
from v2.modules.prediction_ml.public import EnsemblePredictorService

logger = get_logger(__name__)


async def train_all_vehicles():
    """
    Tüm araçlar için ML modellerini yeni route feature'ları ile eğitir.
    """
    logger.info("Starting Mass Model Retraining...")

    predictor_service = EnsemblePredictorService()

    async with AsyncSessionLocal() as session:
        # 1. Seferi olan araçları bul
        stmt = select(distinct(Sefer.arac_id)).where(Sefer.durum == "Tamam")
        result = await session.execute(stmt)
        arac_ids = result.scalars().all()

        logger.info(f"Found {len(arac_ids)} vehicles with completed trips.")

        results = []

        for arac_id in arac_ids:
            if not arac_id:
                continue

            logger.info(f"Training model for Vehicle {arac_id}...")
            try:
                # Servis üzerinden eğitim (Bu metot Repo'dan veri çeker, feature hazırlar ve fit eder)
                train_result = await predictor_service.train_for_vehicle(arac_id)

                if train_result.get("success"):
                    # Extract R2 from metrics sub-dict
                    metrics = train_result.get("metrics", {})
                    r2_scores = [
                        metrics.get("gb_test_r2"),
                        metrics.get("rf_test_r2"),
                        metrics.get("xgb_test_r2"),
                        metrics.get("lgb_test_r2"),
                        metrics.get("gb_cv_mean"),
                    ]
                    best_r2 = (
                        max(s for s in r2_scores if s is not None)
                        if any(s is not None for s in r2_scores)
                        else 0.0
                    )

                    results.append(
                        {
                            "arac_id": arac_id,
                            "status": "Success",
                            "r2": best_r2,
                            "samples": train_result.get("sample_count"),
                        }
                    )
                    logger.info(f"Vehicle {arac_id}: Success (R2={best_r2:.3f})")
                else:
                    results.append(
                        {
                            "arac_id": arac_id,
                            "status": "Failed",
                            "error": train_result.get("error"),
                        }
                    )
                    logger.warning(
                        f"Vehicle {arac_id}: Failed ({train_result.get('error')})"
                    )

            except Exception as e:
                logger.error(f"Error training vehicle {arac_id}: {e}")
                results.append({"arac_id": arac_id, "status": "Error", "error": str(e)})

    # Summary
    print("\n" + "=" * 50)
    print("TRAINING SUMMARY")
    print("=" * 50)
    print(f"{'Vehicle ID':<12} | {'Status':<10} | {'Samples':<8} | {'Best R2':<8}")
    print("-" * 50)

    for res in results:
        r2_str = f"{res.get('r2', 0):.3f}" if res.get("r2") else "-"
        print(
            f"{res['arac_id']:<12} | {res['status']:<10} | {res.get('samples', '-'):<8} | {r2_str:<8}"
        )

    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(train_all_vehicles())
