import os

import requests

BASE_URL = "http://localhost:8000/api/v1"
_TEST_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


def test_flow():
    # 1. Login
    print("1. Logging in...")
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/token",
            data={"username": "admin", "password": _TEST_PASSWORD},
        )
        print(f"Login Status: {resp.status_code}")
        if resp.status_code != 200:
            print("Login Failed:", resp.text)
            return

        token = resp.json()["access_token"]
        print(f"Token received. Length: {len(token)}")

        headers = {"Authorization": f"Bearer {token}"}

    except Exception as e:
        print(f"Login Exception: {e}")
        return

    # 2. Test /me (Control Group)
    print("\n2. Testing /auth/me ...")
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print("Response:", resp.text)

    # 3. Test /vehicles/ (Treatment Group)
    print("\n3. Testing /vehicles/?skip=0&limit=10 ...")
    resp = requests.get(f"{BASE_URL}/vehicles/?skip=0&limit=10", headers=headers)
    print(f"Status: {resp.status_code}")
    print("Response First 100 chars:", resp.text[:100])

    # Check if slash matters
    print("\n4. Testing /vehicles (No Slash) ...")
    resp = requests.get(f"{BASE_URL}/vehicles?skip=0&limit=10", headers=headers)
    print(f"Status: {resp.status_code}")


if __name__ == "__main__":
    test_flow()
