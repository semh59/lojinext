import asyncio
import os
import sys

sys.path.append(os.getcwd())

from datetime import date

from app.services.prediction_service import get_prediction_service


async def test_pred():
    print("Initializing Prediction Service...")
    service = get_prediction_service()

    # Params from Trip 198
    arac_id = 24
    mesafe_km = 177.6
    ton = 25.52
    ascent = 1288.0
    descent = 1311.4
    sofor_id = 53
    target_date = date(2026, 2, 17)

    print(f"Predicting for Payload: {ton} Ton, Dist: {mesafe_km} km")

    try:
        pred = await service.predict_consumption(
            arac_id=arac_id,
            mesafe_km=mesafe_km,
            ton=ton,
            ascent_m=ascent,
            descent_m=descent,
            flat_distance_km=0.0,
            sofor_id=sofor_id,
            target_date=target_date,
            bos_sefer=False,
            route_analysis={"weather_factor": 1.0},
        )
        print("Prediction Result:", pred)
    except Exception as e:
        print(f"Prediction Failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_pred())
