import asyncio
import uuid

import pytest

from app.database.models import Lokasyon
from v2.modules.driver.public import Sofor
from v2.modules.fleet.public import AracORM as Arac

pytestmark = pytest.mark.asyncio


class TestSeferLoadAPI:
    @pytest.fixture
    async def seed_data(self, db_session):
        # Create Arac
        arac = Arac(
            plaka=f"LOAD{uuid.uuid4().hex[:4].upper()}",
            marka="Mercedes",
            model="Actros",
            yil=2023,
            tank_kapasitesi=600,
            hedef_tuketim=30.0,
            aktif=True,
        )
        db_session.add(arac)

        # Create Sofor
        sofor = Sofor(ad_soyad=f"Load Test Sofor {uuid.uuid4().hex[:4]}", aktif=True)
        db_session.add(sofor)

        # Create Lokasyon
        lokasyon = Lokasyon(cikis_yeri="Istanbul", varis_yeri="Izmir", mesafe_km=480.5)
        db_session.add(lokasyon)

        await db_session.commit()
        await db_session.refresh(arac)
        await db_session.refresh(sofor)
        await db_session.refresh(lokasyon)

        return {"arac": arac, "sofor": sofor, "guzergah": lokasyon}

    async def test_concurrent_trip_creation(
        self, async_client, async_normal_user_token_headers, seed_data, monkeypatch
    ):
        """
        Test that creating multiple trips concurrently works without database locks or integrity errors.
        """

        from app.main import app

        # 1. Disable slowapi limiter
        if hasattr(app.state, "limiter"):
            app.state.limiter.enabled = False

        # 2. Bypass custom RateLimitMiddleware using monkeypatch (for safety)
        from app.infrastructure.middleware.rate_limit_middleware import (
            RateLimitMiddleware,
        )

        async def mock_dispatch(self, request, call_next):
            return await call_next(request)

        monkeypatch.setattr(RateLimitMiddleware, "dispatch", mock_dispatch)

        # 3. Bypass low-level AsyncRateLimiter for external services (OpenRoute etc.)
        from app.infrastructure.resilience.rate_limiter import AsyncRateLimiter

        async def mock_acquire(self):
            pass

        monkeypatch.setattr(AsyncRateLimiter, "acquire", mock_acquire)

        num_concurrent_requests = 20

        async def create_trip(index: int):
            payload = {
                "tarih": "2023-05-20",
                "arac_id": seed_data["arac"].id,
                "sofor_id": seed_data["sofor"].id,
                "guzergah_id": seed_data["guzergah"].id,
                "cikis_yeri": "Istanbul",
                "varis_yeri": "Izmir",
                "mesafe_km": 480.5,
                "net_kg": 20000,
                "durum": "Tamam",
                "notlar": f"Concurrent {index}",
            }
            response = await async_client.post(
                "/api/v1/trips/", json=payload, headers=async_normal_user_token_headers
            )
            return response

        # Run requests concurrently
        tasks = [create_trip(i) for i in range(num_concurrent_requests)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        successful_creations = 0
        failed_creations = 0

        for idx, response in enumerate(responses):
            if isinstance(response, Exception):
                failed_creations += 1
                print(f"Request {idx} failed with Exception: {response}")
            elif response.status_code == 201:
                successful_creations += 1
            else:
                failed_creations += 1
                print(
                    f"Request {idx} failed with status {response.status_code}: {response.text}"
                )

        assert successful_creations == num_concurrent_requests, (
            f"Only {successful_creations}/{num_concurrent_requests} succeeded."
        )
