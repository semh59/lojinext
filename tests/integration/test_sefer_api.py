import pytest

from app.database.models import Arac, Lokasyon, Sofor

# Mark all tests in this module as asyncio with session loop scope
pytestmark = pytest.mark.asyncio


class TestSeferAPI:
    @pytest.fixture
    async def seed_data(self, db_session):
        # Create Arac with required fields (min_length=7 for plaka)
        arac = Arac(
            plaka="34TEST99",
            marka="Mercedes",
            model="Actros",
            yil=2023,
            tank_kapasitesi=600,
            hedef_tuketim=30.0,
            aktif=True,
        )
        db_session.add(arac)

        # Create Sofor
        sofor = Sofor(ad_soyad="Integration Test Sofor", aktif=True)
        db_session.add(sofor)

        # Create Lokasyon (Guzergah)
        # Fixed: Removed 'ad' field which does not exist in Lokasyon model
        lokasyon = Lokasyon(
            cikis_yeri="Istanbul Depo", varis_yeri="Ankara Lojistik", mesafe_km=450.5
        )
        db_session.add(lokasyon)

        await db_session.commit()
        await db_session.refresh(arac)
        await db_session.refresh(sofor)
        await db_session.refresh(lokasyon)

        return {"arac": arac, "sofor": sofor, "guzergah": lokasyon}

    async def test_create_sefer_happy_path(
        self, async_client, async_normal_user_token_headers, seed_data
    ):
        """
        Test full creation flow.
        """
        payload = {
            "tarih": "2023-05-20",
            "arac_id": seed_data["arac"].id,
            "sofor_id": seed_data["sofor"].id,
            "guzergah_id": seed_data["guzergah"].id,
            "cikis_yeri": "Istanbul Depo",
            "varis_yeri": "Ankara Lojistik",
            "mesafe_km": 450.5,
            "net_kg": 24000,
            "durum": "Planlandı",
            "bos_sefer": False,
            "notlar": "E2E Test Entry",
        }

        response = await async_client.post(
            "/api/v1/trips/", json=payload, headers=async_normal_user_token_headers
        )

        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        if "data" in data:
            data = data["data"]

        assert "id" in data
        assert data["cikis_yeri"] == "Istanbul Depo"

        # Verify persistence
        sefer_id = data["id"]
        get_response = await async_client.get(
            f"/api/v1/trips/{sefer_id}", headers=async_normal_user_token_headers
        )
        assert get_response.status_code == 200

    async def test_create_sefer_unauthorized(self, async_client):
        """Attempting to create a trip without token should fail"""
        payload = {
            "tarih": "2023-05-20",
            "arac_id": 1,
            "sofor_id": 1,
        }
        response = await async_client.post("/api/v1/trips/", json=payload)
        assert response.status_code == 401

    async def test_create_sefer_validation_error(
        self, async_client, async_normal_user_token_headers, seed_data
    ):
        """Sending invalid data should return 422"""
        payload = {
            "tarih": "2023-05-20",
            "arac_id": seed_data["arac"].id,
        }
        response = await async_client.post(
            "/api/v1/trips/", json=payload, headers=async_normal_user_token_headers
        )
        assert response.status_code == 422

    async def test_create_sefer_duplicate_sefer_no(
        self, async_client, async_normal_user_token_headers, seed_data
    ):
        """Creating a trip with a duplicate sefer_no should fail with 422.

        Create-path business validations raise RouteProcessingError
        (reason="DUPLICATE_SEFER_NO"), which the DomainError handler maps to
        422 (see app/main.py:_DOMAIN_ERROR_STATUS). Aligned with the typed
        DomainError propagation refactor (e4c0d93a) and the unit test
        test_add_sefer_raises_on_duplicate_sefer_no.
        """
        sefer_no = "DUPE-INT-123"
        payload = {
            "tarih": "2023-05-20",
            "arac_id": seed_data["arac"].id,
            "sofor_id": seed_data["sofor"].id,
            "guzergah_id": seed_data["guzergah"].id,
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.5,
            "net_kg": 24000,
            "sefer_no": sefer_no,
        }

        response1 = await async_client.post(
            "/api/v1/trips/", json=payload, headers=async_normal_user_token_headers
        )
        assert response1.status_code == 201

        response2 = await async_client.post(
            "/api/v1/trips/", json=payload, headers=async_normal_user_token_headers
        )
        assert response2.status_code == 422
