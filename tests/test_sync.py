import json
import urllib.parse
import urllib.request

BASE_URL = "http://localhost:8000/api/v1"
OUTPUT_FILE = "test_result_sync.txt"


def log(msg):
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    log("STARTING SYNC TEST...")

    # 1. Login
    url = f"{BASE_URL}/auth/token"
    data = urllib.parse.urlencode(
        {"username": "admin", "password": "admin123", "grant_type": "password"}
    ).encode()

    log(f"Requesting {url}")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            log(f"Login Response: {response.status}")
            token_data = json.loads(res_body)
            token = token_data["access_token"]
            log("Login successful.")
    except Exception as e:
        log(f"Login Failed: {e}")
        return

    # 2. Create Route
    url = f"{BASE_URL}/guzergahlar/"
    payload = {
        "ad": "Sync Test Rota",
        "cikis_yeri": "İstanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 0,
        "cikis_lat": 41.0082,
        "cikis_lon": 28.9784,
        "varis_lat": 39.9334,
        "varis_lon": 32.8597,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    log("Creating route...")
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req) as response:
            res_body = response.read()
            log(f"Create Response: {response.status}")
            data = json.loads(res_body)

            log(f"ID: {data.get('id')}")
            log(f"Distance: {data.get('mesafe_km')}")
            log(f"Ascent: {data.get('ascent_m')}")

            if data.get("mesafe_km") > 100:
                log("RESULT: SUCCESS")
            else:
                log("RESULT: FAILURE")

    except Exception as e:
        log(f"Create Failed: {e}")
        # Try to read error body
        try:
            log(f"Error Body: {e.read().decode()}")
        except Exception:
            pass


if __name__ == "__main__":
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("")
    main()
