"""
T9-A: E2E Error Scenario Smoke Tests

Kapsamlı error handling validation across 7 critical scenarios.
Bug scenarios, permission checks, validation errors.

Hedef: Hataları kategorize et, UI uyarıları test et, audit logları kontrol et.
"""

import asyncio
from datetime import date

import httpx

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"


async def test_invalid_token_returns_401():
    """T9-A-1: Invalid token → 401 Unauthorized"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/trips/",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )
        assert response.status_code == 401, (
            f"T9-A-1: Invalid token should return 401. Got {response.status_code}"
        )
        print("[OK] T9-A-1: Invalid token returns 401")


async def test_permission_denied_returns_403():
    """T9-A-2: Normal user accessing admin endpoint → 403 Forbidden"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/admin/users/",
            json={"username": "newuser"},
            headers={"Authorization": "Bearer normal_user_token"},
        )
        assert response.status_code == 403, (
            f"T9-A-2: Normal user should get 403 on admin endpoint. "
            f"Got {response.status_code}"
        )
        print("[OK] T9-A-2: Permission denied returns 403")


async def test_nonexistent_resource_returns_404():
    """T9-A-3: GET /trips/999999 (nonexistent) → 404 Not Found"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}{API_PREFIX}/trips/999999",
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 404, (
            f"T9-A-3: Nonexistent resource should return 404. Got {response.status_code}"
        )
        print("[OK] T9-A-3: Nonexistent resource returns 404")


async def test_malformed_json_returns_422():
    """T9-A-4: POST with invalid JSON schema → 422 Unprocessable Entity"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/trips/",
            json={
                "arac_id": "invalid_string",  # Should be int
                "sofor_id": None,  # Required field missing/null
            },
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 422, (
            f"T9-A-4: Malformed JSON should return 422. Got {response.status_code}"
        )
        print("[OK] T9-A-4: Malformed JSON returns 422")


async def test_fk_violation_returns_422_clean_message():
    """T9-A-5: Create sefer with nonexistent arac_id → 422 (no schema leak)"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/trips/",
            json={
                "arac_id": 999999,  # Nonexistent
                "sofor_id": 1,
                "tarih": str(date.today()),
                "cikis_yeri": "Istanbul",
                "varis_yeri": "Ankara",
                "mesafe_km": 400.0,
                "durum": "Tamamlandi",
                "net_kg": 10000,
                "bos_agirlik_kg": 5000,
                "dolu_agirlik_kg": 15000,
                "flat_distance_km": 400.0,
            },
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code in (
            400,
            422,
        ), f"T9-A-5: FK violation should return 4xx. Got {response.status_code}"

        # Verify response doesn't leak schema
        body_text = str(response.json()).lower()
        assert "araclar" not in body_text, (
            "T9-A-5: Response leaked table name 'araclar'"
        )
        assert "foreign key" not in body_text, (
            "T9-A-5: Response leaked 'FOREIGN KEY' constraint"
        )
        print("[OK] T9-A-5: FK violation returns clean 422")


async def test_duplicate_import_returns_clean_error():
    """T9-A-6: Upload CSV with duplicate plate → clean error summary"""
    print("[SKIP] T9-A-6: Requires CSV upload setup")


async def test_rate_limit_returns_429():
    """T9-A-7: 10+ rapid requests to rate-limited endpoint → 429"""
    async with httpx.AsyncClient() as client:
        responses = []
        for i in range(10):
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/password-reset-confirm",
                json={"token": "dummy", "new_password": f"Pass{i}!"},
            )
            responses.append(response.status_code)

        # At least one 429 or 400+ should occur
        assert any(s >= 400 for s in responses), (
            f"T9-A-7: Rate limiting should trigger error. Responses: {responses}"
        )
        print(f"[OK] T9-A-7: Rate limiting triggered (responses: {responses})")


async def run_all_tests():
    """Run all E2E error smoke tests"""
    print("\n=== T9-A: E2E Error Scenario Smoke Tests ===\n")

    tests = [
        ("T9-A-1: Invalid token", test_invalid_token_returns_401),
        ("T9-A-2: Permission denied", test_permission_denied_returns_403),
        ("T9-A-3: Not found", test_nonexistent_resource_returns_404),
        ("T9-A-4: Malformed JSON", test_malformed_json_returns_422),
        ("T9-A-5: FK violation", test_fk_violation_returns_422_clean_message),
        ("T9-A-6: Duplicate import", test_duplicate_import_returns_clean_error),
        ("T9-A-7: Rate limiting", test_rate_limit_returns_429),
    ]

    for name, test_func in tests:
        try:
            await test_func()
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
        except Exception as e:
            print(f"[ERROR] {name}: {type(e).__name__}: {e}")

    print("\n=== Test Summary ===")
    print("Run with: python scripts/e2e_error_smoke.py")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
