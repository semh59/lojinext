import asyncio
import sys

import httpx

# API Base URL
BASE_URL = "http://localhost:8000/api/v1"


async def main():
    print("STARTING E2E TEST...", flush=True)
    async with httpx.AsyncClient() as client:
        # 1. Login
        print("Authenticating...", flush=True)
        try:
            print("Sending login request...", flush=True)
            resp = await client.post(
                f"{BASE_URL}/auth/token",
                data={
                    "username": "admin",
                    "password": "admin123",
                    "grant_type": "password",
                },
                timeout=10.0,
            )
            print(f"Login Response Code: {resp.status_code}", flush=True)

            if resp.status_code == 200:
                token = resp.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                print("Login successful.", flush=True)
            else:
                print(f"Login failed: {resp.status_code}", flush=True)
                try:
                    print(resp.text, flush=True)
                except Exception:
                    pass
                # headers = {} # Don't proceed without auth if 401
                return

        except Exception as e:
            print(f"Auth error details: {e}", flush=True)
            import traceback

            traceback.print_exc()
            return

        # 2. Create Guzergah with Coords
        # Istanbul (41.0082, 28.9784) -> Ankara (39.9334, 32.8597)
        payload = {
            "ad": "E2E Test Rota - İst-Ank",
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 0,  # Should be updated
            "cikis_lat": 41.0082,
            "cikis_lon": 28.9784,
            "varis_lat": 39.9334,
            "varis_lon": 32.8597,
        }

        print("\nCreating Route via API...", flush=True)
        print(f"Payload: {payload}", flush=True)

        try:
            resp = await client.post(
                f"{BASE_URL}/guzergahlar/", json=payload, headers=headers, timeout=15.0
            )
            print(f"Create Response Code: {resp.status_code}", flush=True)

            if resp.status_code in [200, 201]:
                data = resp.json()
                print("\n--- RESULTS ---", flush=True)
                print(f"ID: {data.get('id')}", flush=True)
                print(f"Name: {data.get('ad')}", flush=True)
                print(f"Distance: {data.get('mesafe_km')} km", flush=True)
                print(f"Ascent: {data.get('ascent_m')} m", flush=True)
                print(f"Descent: {data.get('descent_m')} m", flush=True)

                if data.get("mesafe_km") > 100:
                    print(
                        "\n✅ SUCCESS: Distance calculated automatically!", flush=True
                    )
                else:
                    print(
                        "\n❌ FAILURE: Distance not calculated (remains 0 or low).",
                        flush=True,
                    )

                if data.get("ascent_m") is not None:
                    print("✅ SUCCESS: Elevation data present.", flush=True)
                else:
                    print("❌ FAILURE: Elevation data missing.", flush=True)
            else:
                print(f"\n❌ API Request Failed: {resp.status_code}", flush=True)
                print(resp.text, flush=True)

        except Exception as e:
            print(f"\n❌ Request Exception: {e}", flush=True)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
