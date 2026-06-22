import asyncio
import sys

import httpx

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"
OUTPUT_FILE = "test_result.txt"


def log(msg):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


async def main():
    log("STARTING E2E TEST...")
    async with httpx.AsyncClient() as client:
        # 1. Login
        log("Authenticating...")
        try:
            log("Sending login request...")
            resp = await client.post(
                f"{BASE_URL}/auth/token",
                data={
                    "username": "admin",
                    "password": "admin123",
                    "grant_type": "password",
                },
                timeout=10.0,
            )
            log(f"Login Response Code: {resp.status_code}")

            if resp.status_code == 200:
                token = resp.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                log("Login successful.")
            else:
                log(f"Login failed: {resp.status_code}")
                try:
                    log(resp.text)
                except Exception:
                    pass
                return

        except Exception as e:
            log(f"Auth error details: {e}")
            return

        # 2. Create Guzergah with Coords
        payload = {
            "ad": "E2E Test Rota - İst-Ank",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 0,
            "cikis_lat": 41.0082,
            "cikis_lon": 28.9784,
            "varis_lat": 39.9334,
            "varis_lon": 32.8597,
        }

        log(f"Creating Route via API... Payload: {payload}")

        try:
            resp = await client.post(
                f"{BASE_URL}/guzergahlar/", json=payload, headers=headers, timeout=15.0
            )
            log(f"Create Response Code: {resp.status_code}")

            if resp.status_code in [200, 201]:
                data = resp.json()
                log(f"ID: {data.get('id')}")
                log(f"Name: {data.get('ad')}")
                log(f"Distance: {data.get('mesafe_km')} km")
                log(f"Ascent: {data.get('ascent_m')} m")

                if data.get("mesafe_km") > 100:
                    log("RESULT: SUCCESS - Distance calculated automatically!")
                else:
                    log("RESULT: FAILURE - Distance not calculated (remains 0 or low).")

                if data.get("ascent_m") is not None:
                    log("RESULT: SUCCESS - Elevation data present.")
                else:
                    log("RESULT: FAILURE - Elevation data missing.")
            else:
                log(f"API Request Failed: {resp.status_code}")
                log(resp.text)

        except Exception as e:
            log(f"Request Exception: {e}")


if __name__ == "__main__":
    # Clear file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
