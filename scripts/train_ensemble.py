import asyncio
import os
import sys

import pandas as pd
from sklearn.linear_model import LinearRegression
from sqlalchemy import select

from app.core.ml.ensemble_predictor import get_ensemble_service
from app.database.connection import AsyncSessionLocal
from app.database.models import Arac
from app.infrastructure.logging.logger import setup_logging

# Project root
sys.path.append(os.getcwd())

logger = setup_logging("training")


def calculate_vif(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate the variance inflation factor (VIF).

    VIF > 10 indicates strong multicollinearity.
    """
    vif_data = pd.DataFrame()
    vif_data["feature"] = df.columns
    vif_values = []

    for feature in df.columns:
        x_matrix = df.drop(columns=[feature])
        y_vector = df[feature]
        r2 = LinearRegression().fit(x_matrix, y_vector).score(x_matrix, y_vector)
        vif = 1 / (1 - r2) if r2 < 1 else float("inf")
        vif_values.append(vif)

    vif_data["VIF"] = vif_values
    return vif_data.sort_values("VIF", ascending=False)


async def train_fleet() -> None:
    logger.info("Starting fleet ensemble training.")

    # Shared service instance
    service = get_ensemble_service()

    async with AsyncSessionLocal() as session:
        # Load all active vehicles
        vehicles_result = await session.execute(select(Arac).where(Arac.aktif))
        vehicles = vehicles_result.scalars().all()

        overall_stats = []

        for vehicle in vehicles:
            logger.info(f"Training for vehicle: {vehicle.plaka} (ID: {vehicle.id})")

            # Use the service entry point so fetch, enrichment, fit, and save
            # remain consistent with production training flows.
            result = await service.train_for_vehicle(vehicle.id)

            if result.get("success"):
                ensemble_r2 = result.get("ensemble_r2", 0)
                logger.info(f"  Training succeeded. Ensemble R2: {ensemble_r2:.4f}")

                models = ["gb_test_r2", "rf_test_r2", "xgb_r2", "lgb_r2"]
                scores = [
                    f"{model}: {result.get(model, 0):.3f}"
                    for model in models
                    if result.get(model) is not None
                ]
                logger.info(f"  Detailed scores: {', '.join(scores)}")

                overall_stats.append(ensemble_r2)

                # Optional VIF analysis for feature-correlation checks.
                if result.get("feature_matrix") is not None:
                    try:
                        from app.core.ml.ensemble_predictor import (
                            EnsembleFuelPredictor,
                        )

                        feature_names = EnsembleFuelPredictor.FEATURE_NAMES
                        df_features = pd.DataFrame(
                            result["feature_matrix"], columns=feature_names
                        )
                        vif_df = calculate_vif(df_features)

                        top_vif = vif_df.iloc[0]
                        if top_vif["VIF"] > 8:
                            logger.warning(
                                "  High multicollinearity detected: "
                                f"{top_vif['feature']} (VIF: {top_vif['VIF']:.2f})"
                            )
                        else:
                            logger.info(
                                "  Feature independence is acceptable "
                                f"(max VIF: {top_vif['VIF']:.2f})"
                            )
                    except Exception as exc:
                        logger.error(f"  VIF analysis failed: {exc}")
            else:
                logger.error(f"  Training failed: {result.get('error')}")

        # Train the general fallback model.
        logger.info("Training general fallback model (ID: 0).")
        general_result = await service.train_general_model()
        logger.info(
            "  General model training: "
            f"{general_result.get('success')} "
            f"(samples: {general_result.get('sample_count')})"
        )

        if overall_stats:
            avg_r2 = sum(overall_stats) / len(overall_stats)
            logger.info("=" * 50)
            logger.info(f"FINAL AUDIT: Fleet average R2 = {avg_r2:.4f}")
            if avg_r2 > 0.85:
                logger.info("Training target reached (>0.85).")
            else:
                logger.warning("Training target not reached; inspect data variance.")
            logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(train_fleet())
