import asyncio
import random
import sys
from datetime import datetime

import httpx

# API Base URL
BASE_URL = "http://127.0.0.1:8000/api/v1"
USERNAME = "admin"
PASSWORD = "admin123"


async def main():
    print("STARTING COMPREHENSIVE BACKEND E2E TEST (v9)...", flush=True)
    try:
        print("Initializing AsyncClient...", flush=True)
        async with httpx.AsyncClient() as client:
            print("Client initialized.", flush=True)

            # --- 1. AUTHENTICATION ---
            print("\n1. Authenticating...", flush=True)
            headers = {}
            try:
                resp = await client.post(
                    f"{BASE_URL}/auth/token",
                    data={
                        "username": USERNAME,
                        "password": PASSWORD,
                        "grant_type": "password",
                    },
                )
                if resp.status_code == 200:
                    token = resp.json()["access_token"]
                    headers = {"Authorization": f"Bearer {token}"}
                    print("Login successful.", flush=True)
                else:
                    print(f"Login failed: {resp.status_code} - {resp.text}", flush=True)
                    return
            except Exception as e:
                print(f"Auth error: {e}", flush=True)
                return

            # --- 2. VEHICLE MANAGEMENT (Araç Yönetimi) ---
            print("\n2. Testing Vehicle Management...", flush=True)
            vehicle_id = None
            try:
                # Create
                plaka = f"34TST{random.randint(100, 999)}"
                payload = {
                    "plaka": plaka,
                    "marka": "Mercedes",
                    "model": "Actros",
                    "yil": 2023,
                    "tank_kapasitesi": 600,
                    "hedef_tuketim": 30.5,
                    "aktif": True,
                }
                resp = await client.post(
                    f"{BASE_URL}/vehicles/", json=payload, headers=headers
                )
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    vehicle_id = data["id"]
                    print(f"Vehicle Created: {plaka} (ID: {vehicle_id})", flush=True)
                else:
                    print(
                        f"Vehicle Create Failed: {resp.status_code} - {resp.text}",
                        flush=True,
                    )

                # List
                if vehicle_id:
                    resp = await client.get(f"{BASE_URL}/vehicles/", headers=headers)
                    if resp.status_code == 200 and any(
                        v["id"] == vehicle_id for v in resp.json()
                    ):
                        print("Vehicle Listed successfully.", flush=True)
                    else:
                        print(
                            "Vehicle List Failed or Created Vehicle not found.",
                            flush=True,
                        )

            except Exception as e:
                print(f"Vehicle Test Error: {e}", flush=True)

            # --- 3. DRIVER MANAGEMENT (Şoför Yönetimi) ---
            print("\n3. Testing Driver Management...", flush=True)
            driver_id = None
            try:
                # Create
                payload = {
                    "ad_soyad": "Test Driver E2E",
                    "telefon": "5551234567",
                    "ehliyet_sinifi": "E",
                    "aktif": True,
                }
                resp = await client.post(
                    f"{BASE_URL}/drivers/", json=payload, headers=headers
                )
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    driver_id = data["id"]
                    print(f"Driver Created: Test Driver (ID: {driver_id})", flush=True)
                else:
                    print(
                        f"Driver Create Failed: {resp.status_code} - {resp.text}",
                        flush=True,
                    )
            except Exception as e:
                print(f"Driver Test Error: {e}", flush=True)

            # --- 4. FUEL MANAGEMENT (Yakıt Yönetimi) ---
            print("\n4. Testing Fuel Management...", flush=True)
            if vehicle_id and driver_id:
                try:
                    payload = {
                        "arac_id": vehicle_id,
                        "surucu_id": driver_id,
                        "tarih": datetime.now().date().isoformat(),
                        "litre": 100,
                        "fiyat_tl": 40.5,
                        "toplam_tutar": 4050,
                        "km_sayac": 1000,
                        "istasyon": "Test Istasyonu",
                        "depo_durumu": "Doldu",
                    }
                    resp = await client.post(
                        f"{BASE_URL}/fuel/", json=payload, headers=headers
                    )
                    if resp.status_code in [200, 201]:
                        print("Fuel Record Created.", flush=True)
                    else:
                        print(
                            f"Fuel Record Create Failed: {resp.status_code} - {resp.text}",
                            flush=True,
                        )
                except Exception as e:
                    print(f"Fuel Test Error: {e}", flush=True)
            else:
                print("Skipping Fuel Test (Vehicle or Driver missing).", flush=True)

            # --- 5. ROUTE & AI PREDICTION (Güzergah ve AI) ---
            print("\n5. Testing Route & AI Prediction...", flush=True)
            route_id = None
            try:
                # 1. Create Route (Guzergah) - Needed for Trip
                payload = {
                    "ad": "Test Route E2E",
                    "cikis_yeri": "Istanbul",
                    "varis_yeri": "Ankara",
                    "mesafe_km": 500.5,
                    "varsayilan_arac_id": vehicle_id,
                    "varsayilan_sofor_id": driver_id,
                }
                resp = await client.post(
                    f"{BASE_URL}/guzergahlar/", json=payload, headers=headers
                )
                if resp.status_code in [200, 201]:
                    data = resp.json()
                    route_id = data["id"]
                    print(f"Route Created: Test Route (ID: {route_id})", flush=True)
                else:
                    print(
                        f"Route Create Failed: {resp.status_code} - {resp.text}",
                        flush=True,
                    )

                # 2. List Routes (Verifies AI Endpoint validation healing)
                resp = await client.get(f"{BASE_URL}/guzergahlar/", headers=headers)
                if resp.status_code == 200:
                    print(
                        "Routes endpoint accessible (AI Healing Validated).", flush=True
                    )
                else:
                    print(f"Routes endpoint failed: {resp.status_code}", flush=True)

            except Exception as e:
                print(f"Route Test Error: {e}", flush=True)

            # --- 6. TRIP MANAGEMENT (Sefer Yönetimi) ---
            print("\n6. Testing Trip Management...", flush=True)
            trip_id = None
            if vehicle_id and driver_id and route_id:
                try:
                    # Update: SeferBase requires locations and distance explicitly
                    payload = {
                        "arac_id": vehicle_id,
                        "sofor_id": driver_id,
                        "guzergah_id": route_id,
                        "tarih": datetime.now().date().isoformat(),
                        "saat": "08:30",
                        "baslangic_km": 10000,
                        "durum": "Planlandı",
                        "aciklama": "E2E Test Seferi",
                        # Extra fields required by SeferCreate (duplicated from Route)
                        "cikis_yeri": "Istanbul",
                        "varis_yeri": "Ankara",
                        "mesafe_km": 500.5,
                        "bos_sefer": False,
                    }
                    resp = await client.post(
                        f"{BASE_URL}/trips/", json=payload, headers=headers
                    )
                    if resp.status_code in [200, 201]:
                        data = resp.json()
                        trip_id = data["id"]
                        print(f"Trip Created: ID {trip_id}", flush=True)
                    else:
                        print(
                            f"Trip Create Failed: {resp.status_code} - {resp.text}",
                            flush=True,
                        )
                except Exception as e:
                    print(f"Trip Test Error: {e}", flush=True)
            else:
                print("Skipping Trip Test (Dependencies missing).", flush=True)

            # --- 7. EXCEL EXPORT (Veri İşlemleri) ---
            print("\n7. Testing Excel Export...", flush=True)
            try:
                # Endpoint: /vehicles/export
                resp = await client.get(f"{BASE_URL}/vehicles/export", headers=headers)
                if resp.status_code == 200 and resp.headers.get("content-type") in [
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/octet-stream",
                ]:
                    print("Vehicle Excel Export successful.", flush=True)
                else:
                    print(
                        f"Excel Export failed: {resp.status_code} - {resp.headers.get('content-type')}",
                        flush=True,
                    )
            except Exception as e:
                print(f"Excel Test Error: {e}", flush=True)

            # --- CLEANUP (Optional) ---
            print("\nCleanup...", flush=True)
            if vehicle_id:
                await client.delete(
                    f"{BASE_URL}/vehicles/{vehicle_id}", headers=headers
                )
                print(f"Vehicle {vehicle_id} deleted.")
            if driver_id:
                await client.delete(f"{BASE_URL}/drivers/{driver_id}", headers=headers)
                print(f"Driver {driver_id} deleted.")
            if route_id:
                await client.delete(
                    f"{BASE_URL}/guzergahlar/{route_id}", headers=headers
                )
                print(f"Route {route_id} deleted.")
            if trip_id:
                await client.delete(f"{BASE_URL}/trips/{trip_id}", headers=headers)
                print(f"Trip {trip_id} deleted.")

        print("\nE2E TEST COMPLETED.", flush=True)

    except Exception as e:
        print(f"CRITICAL ERROR IN MAIN: {e}", flush=True)
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    asyncio.run(main())
