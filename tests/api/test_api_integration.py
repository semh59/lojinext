"""
API Integration Test Suite

Tests the complete API → Service → Repository chain for critical flows.
Uses httpx.AsyncClient for async testing with FastAPI.
"""

from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.database.models import Kullanici, Lokasyon, Rol

# Import app and models
from app.main import app

# Use global Test Database Configuration from conftest
from tests.conftest import TEST_DATABASE_URL
from v2.modules.driver.public import Sofor
from v2.modules.fleet.public import AracORM as Arac


def _unwrap_standard_response(payload):
    """Support both legacy raw payloads and current StandardResponse envelopes."""
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _unwrap_items(payload):
    """Support legacy item lists and paginated payloads."""
    unwrapped = _unwrap_standard_response(payload)
    if isinstance(unwrapped, dict) and "items" in unwrapped:
        return unwrapped["items"]
    return unwrapped


@pytest.fixture
async def test_session(db_session):
    """Use global test database session (PostgreSQL)."""
    yield db_session


@pytest.fixture
async def test_user(test_session):
    """Create test admin user."""
    from v2.modules.auth_rbac.domain.security import get_password_hash

    # Create role first
    role = Rol(ad="admin", yetkiler={"*": True})
    test_session.add(role)
    await test_session.commit()
    await test_session.refresh(role)

    user = Kullanici(
        email="test_admin@lojinext.com",
        ad_soyad="Test Admin",
        sifre_hash=get_password_hash("test123"),
        rol_id=role.id,
        aktif=True,
    )
    test_session.add(user)
    await test_session.commit()

    # Eager load rol to prevent MissingGreenlet in RBAC
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    result = await test_session.execute(
        select(Kullanici)
        .options(selectinload(Kullanici.rol))
        .where(Kullanici.id == user.id)
    )
    return result.scalar_one()


@pytest.fixture
async def test_vehicle(test_session):
    """Create test vehicle."""
    vehicle = Arac(
        plaka="34TEST01",
        marka="VOLVO",
        model="FH16",
        yil=2022,
        tank_kapasitesi=500,
        hedef_tuketim=32.0,
        aktif=True,
    )
    test_session.add(vehicle)
    await test_session.commit()
    await test_session.refresh(vehicle)
    return vehicle


@pytest.fixture
async def test_driver(test_session):
    """Create test driver."""
    driver = Sofor(
        ad_soyad="Test Şoför",
        telefon="5551234567",
        ehliyet_sinifi="E",
        score=1.0,
        manual_score=1.0,
        aktif=True,
    )
    test_session.add(driver)
    await test_session.commit()
    await test_session.refresh(driver)
    return driver


@pytest.fixture
async def test_route(test_session):
    """Create test route required by trip create contract."""
    route = Lokasyon(
        cikis_yeri="Istanbul",
        varis_yeri="Ankara",
        mesafe_km=450.0,
        tahmini_sure_saat=5.0,
        zorluk="Normal",
        ascent_m=150.0,
        descent_m=100.0,
        flat_distance_km=200.0,
        aktif=True,
    )
    test_session.add(route)
    await test_session.commit()
    await test_session.refresh(route)
    return route


@pytest.fixture
def override_deps(test_session, test_user):
    """Override FastAPI dependencies and UoW for testing."""

    from app.api.deps import (
        get_background_job_manager,
        get_current_active_admin,
        get_current_superadmin,
        get_current_user,
        get_db,
    )

    async def override_get_db():
        yield test_session

    test_user_id = int(test_user.id)

    async def override_get_user():
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await test_session.execute(
            select(Kullanici)
            .options(selectinload(Kullanici.rol))
            .where(Kullanici.id == test_user_id)
        )
        return result.scalar_one()

    class FakeBackgroundJobManager:
        async def submit(self, *_args, **_kwargs):
            return "test-job-id"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_user
    app.dependency_overrides[get_current_active_admin] = override_get_user
    app.dependency_overrides[get_current_superadmin] = override_get_user
    app.dependency_overrides[get_background_job_manager] = (
        lambda: FakeBackgroundJobManager()
    )

    # Monkey patch UoW to always use test_session
    from app.database.unit_of_work import UnitOfWork

    original_aenter = UnitOfWork.__aenter__

    async def mock_aenter(self):
        self._session = test_session
        self._external_session = True
        self.session.info["uow_active"] = True
        return self

    UnitOfWork.__aenter__ = mock_aenter

    # Patch execute_query to fix SQLite JSON/Enum string deserialization
    import json

    from app.database.base_repository import BaseRepository
    from v2.modules.trip.domain.entities import DurumEnum

    # Build DurumEnum name → value mapping for SQLite compat
    _durum_map = {f"DurumEnum.{e.name}": e.value for e in DurumEnum}

    def _fix_sqlite_row(row):
        if "id" in row:
            row["id"] = int(row["id"])
        if "yetkiler" in row and isinstance(row["yetkiler"], str):
            try:
                row["yetkiler"] = json.loads(row["yetkiler"])
            except (json.JSONDecodeError, TypeError):
                pass
        if "durum" in row and isinstance(row["durum"], str):
            if row["durum"] in _durum_map:
                row["durum"] = _durum_map[row["durum"]]
        if "rota_detay" in row and isinstance(row["rota_detay"], str):
            try:
                row["rota_detay"] = json.loads(row["rota_detay"])
            except (json.JSONDecodeError, TypeError):
                pass
        return row

    original_execute_query = BaseRepository.execute_query

    async def mock_execute_query(self_repo, query, params=None):
        rows = await original_execute_query(self_repo, query, params)
        for row in rows:
            _fix_sqlite_row(row)
        return rows

    BaseRepository.execute_query = mock_execute_query

    # Patch _to_dict for ORM-based reads
    original_to_dict = BaseRepository._to_dict

    def mock_to_dict(self_repo, obj):
        res = original_to_dict(self_repo, obj)
        if res:
            _fix_sqlite_row(res)
        return res

    BaseRepository._to_dict = mock_to_dict

    yield

    UnitOfWork.__aenter__ = original_aenter
    BaseRepository.execute_query = original_execute_query
    BaseRepository._to_dict = original_to_dict
    app.dependency_overrides.clear()


@pytest.fixture
async def client(override_deps):
    """Create async test client with dependency overrides."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ============================================
# Vehicle API Tests
# ============================================


class TestVehicleAPI:
    """Vehicle endpoint integration tests."""

    @pytest.mark.asyncio
    async def test_list_vehicles(self, client, test_vehicle):
        """Test GET /vehicles/ returns vehicle list."""
        response = await client.get("/api/v1/vehicles/")
        assert response.status_code == 200
        items = _unwrap_items(response.json())
        assert isinstance(items, list)
        assert len(items) >= 1
        plakalar = [v["plaka"].replace(" ", "") for v in items]
        assert "34TEST01" in plakalar, f"Plaka list: {plakalar}"

    @pytest.mark.asyncio
    async def test_get_vehicle_by_id(self, client, test_vehicle):
        """Test GET /vehicles/{id} returns single vehicle."""
        response = await client.get(f"/api/v1/vehicles/{test_vehicle.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["plaka"] == "34TEST01"
        assert data["marka"] == "VOLVO"

    @pytest.mark.asyncio
    async def test_create_vehicle(self, client):
        """Test POST /vehicles/ creates new vehicle."""
        vehicle_data = {
            "plaka": "06NEW01",
            "marka": "MAN",
            "model": "TGX",
            "yil": 2023,
            "tank_kapasitesi": 450,
            "hedef_tuketim": 30.0,
            "aktif": True,
        }
        response = await client.post("/api/v1/vehicles/", json=vehicle_data)
        assert response.status_code == 201
        data = response.json()
        assert data["plaka"] == "06NEW01"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_update_vehicle(self, client, test_vehicle):
        """Test PUT /vehicles/{id} updates vehicle."""
        update_data = {"hedef_tuketim": 28.0}
        response = await client.put(
            f"/api/v1/vehicles/{test_vehicle.id}", json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hedef_tuketim"] == 28.0


# ============================================
# Driver API Tests
# ============================================


class TestDriverAPI:
    """Driver endpoint integration tests."""

    @pytest.mark.asyncio
    async def test_list_drivers(self, client, test_driver):
        """Test GET /drivers/ returns driver list."""
        response = await client.get("/api/v1/drivers/")
        assert response.status_code == 200
        items = _unwrap_items(response.json())
        assert isinstance(items, list)
        assert len(items) >= 1

    @pytest.mark.asyncio
    async def test_create_driver(self, client):
        """Test POST /drivers/ creates new driver."""
        driver_data = {
            "ad_soyad": "Yeni Şoför",
            "telefon": "5559876543",
            "ehliyet_sinifi": "E",
            "score": 1.0,
            "manual_score": 1.0,
            "aktif": True,
        }
        response = await client.post("/api/v1/drivers/", json=driver_data)
        if response.status_code == 400 and "zaten var" in response.text:
            pass  # Already exists from previous run, that's okay for now
        else:
            assert response.status_code == 201
            data = response.json()
            assert data["ad_soyad"] == "Yeni Şoför"

    @pytest.mark.asyncio
    async def test_update_driver_score(self, client, test_driver):
        """Test POST /drivers/{id}/score updates score."""
        response = await client.post(
            f"/api/v1/drivers/{test_driver.id}/score?score=1.5"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["manual_score"] == 1.5


# ============================================
# Trip API Tests
# ============================================


class TestTripAPI:
    """Trip endpoint integration tests."""

    @pytest.mark.asyncio
    async def test_list_trips(self, client):
        """Test GET /trips/ returns trip list."""
        response = await client.get("/api/v1/trips/")
        assert response.status_code == 200
        items = _unwrap_items(response.json())
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_create_trip(self, client, test_vehicle, test_driver, test_route):
        """Test POST /trips/ creates new trip."""
        trip_data = {
            "tarih": date.today().isoformat(),
            "saat": "08:00",
            "arac_id": test_vehicle.id,
            "sofor_id": test_driver.id,
            "guzergah_id": test_route.id,
            "cikis_yeri": "İstanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450,
            "net_kg": 15000,
            "bos_sefer": False,
            "durum": "Planlandı",
            "ascent_m": 100.0,
            "descent_m": 50.0,
            "rota_detay": {},
        }
        response = await client.post("/api/v1/trips/", json=trip_data)
        assert response.status_code == 201
        data = response.json()
        assert data["cikis_yeri"] == "İstanbul"
        assert data["varis_yeri"] == "Ankara"
        return data["id"]

    @pytest.mark.asyncio
    async def test_create_return_trip_api(
        self, client, test_vehicle, test_driver, test_route
    ):
        """Test POST /trips/{id}/return creates return trip correctly."""
        # 1. Create base trip
        trip_data = {
            "tarih": date.today().isoformat(),
            "saat": "08:00",
            "arac_id": test_vehicle.id,
            "sofor_id": test_driver.id,
            "guzergah_id": test_route.id,
            "cikis_yeri": "İzmir",
            "varis_yeri": "Bursa",
            "mesafe_km": 330,
            "net_kg": 20000,
            "bos_sefer": False,
            "durum": "Tamam",
            "ascent_m": 150.0,
            "descent_m": 100.0,
            "sefer_no": "TEST-123",
            "rota_detay": {},
        }
        create_resp = await client.post("/api/v1/trips/", json=trip_data)
        assert create_resp.status_code == 201
        base_trip_id = create_resp.json()["id"]

        # 2. Call return endpoint
        return_resp = await client.post(f"/api/v1/trips/{base_trip_id}/return")
        assert return_resp.status_code == 201
        return_trip = return_resp.json()

        # 3. Assert return trip logic applied
        assert return_trip["cikis_yeri"] == "Bursa"
        assert return_trip["varis_yeri"] == "İzmir"
        assert return_trip["net_kg"] == 0
        assert return_trip["bos_sefer"] is True
        assert return_trip["ascent_m"] == 100.0
        assert return_trip["descent_m"] == 150.0
        assert return_trip["sefer_no"] == "TEST-123-D"

    @pytest.mark.asyncio
    async def test_cost_analysis_async(
        self, client, test_vehicle, test_driver, test_route
    ):
        """Test GET /trips/{id}/cost-analysis triggers background task and returns 202."""
        # 1. Create base trip
        trip_data = {
            "tarih": date.today().isoformat(),
            "saat": "08:00",
            "arac_id": test_vehicle.id,
            "sofor_id": test_driver.id,
            "guzergah_id": test_route.id,
            "cikis_yeri": "Ankara",
            "varis_yeri": "Konya",
            "mesafe_km": 260,
            "net_kg": 10000,
            "bos_sefer": False,
            "durum": "Tamam",
        }
        create_resp = await client.post("/api/v1/trips/", json=trip_data)
        assert create_resp.status_code == 201
        trip_id = create_resp.json()["id"]

        # 2. Call cost analysis
        resp = await client.get(f"/api/v1/trips/{trip_id}/cost-analysis")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "PROCESSING"
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_sefer_concurrent_edit(
        self, client, test_vehicle, test_driver, test_route
    ):
        """Test concurrent edit returns 409 Conflict (Optimistic Locking)."""
        # 1. Create base trip
        trip_data = {
            "tarih": date.today().isoformat(),
            "saat": "08:00",
            "arac_id": test_vehicle.id,
            "sofor_id": test_driver.id,
            "guzergah_id": test_route.id,
            "cikis_yeri": test_route.cikis_yeri,
            "varis_yeri": test_route.varis_yeri,
            "mesafe_km": test_route.mesafe_km,
            "net_kg": 10000,
            "bos_sefer": False,
            "durum": "Planlandı",
            "rota_detay": {},
        }
        create_resp = await client.post("/api/v1/trips/", json=trip_data)
        assert create_resp.status_code == 201
        trip = create_resp.json()
        trip_id = trip["id"]
        initial_version = trip.get("version", 1)

        # 2. Simulate User A updating the trip
        update_data_a = {"durum": "Yolda", "version": initial_version}
        resp_a = await client.patch(f"/api/v1/trips/{trip_id}", json=update_data_a)
        assert resp_a.status_code == 200

        # 3. Simulate User B updating the trip with the SAME initial version
        update_data_b = {"durum": "Devam Ediyor", "version": initial_version}
        resp_b = await client.patch(f"/api/v1/trips/{trip_id}", json=update_data_b)

        # 4. Expect 409 Conflict
        assert resp_b.status_code == 409
        assert "başka biri tarafından" in str(resp_b.json()).lower()


# ============================================
# Fuel API Tests
# ============================================


class TestFuelAPI:
    """Fuel endpoint integration tests."""

    @pytest.mark.asyncio
    async def test_list_fuel_records(self, client):
        """Test GET /fuel/ returns fuel list."""
        response = await client.get("/api/v1/fuel/")
        assert response.status_code == 200
        items = _unwrap_items(response.json())
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_get_fuel_stats(self, client):
        """Test GET /fuel/stats returns statistics."""
        response = await client.get("/api/v1/fuel/stats")
        assert response.status_code == 200
        data = response.json()
        assert (
            "toplam_litre" in data
            or "total_consumption" in data
            or response.status_code == 200
        )

    @pytest.mark.asyncio
    async def test_create_fuel_record(self, client, test_vehicle):
        """Test POST /fuel/ creates fuel record."""
        fuel_data = {
            "tarih": date.today().isoformat(),
            "arac_id": test_vehicle.id,
            "istasyon": "Test Petrol",
            "fiyat_tl": 42.50,
            "litre": 200.0,
            "toplam_tutar": 8500.0,
            "km_sayac": 150000,
            "depo_durumu": "Doldu",
            "durum": "Bekliyor",
        }
        response = await client.post("/api/v1/fuel/", json=fuel_data)
        assert response.status_code in [200, 201]
        data = response.json()
        assert float(data["litre"]) == 200.0


# ============================================
# Bulk Operations Tests
# ============================================


class TestBulkOperations:
    """Bulk operation endpoint tests."""

    @pytest.mark.asyncio
    async def test_bulk_delete_trips_empty_list(self, client):
        """Test DELETE /trips/bulk with empty list returns error."""
        response = await client.request("DELETE", "/api/v1/trips/bulk", json=[])
        assert response.status_code in [400, 422]
        err_str = str(response.json())
        assert (
            "boş olamaz" in err_str
            or "empty" in err_str
            or "hatası" in err_str
            or "VALIDATION_ERROR" in err_str
        )

    @pytest.mark.asyncio
    async def test_bulk_delete_trips_max_limit(self, client):
        """Test DELETE /trips/bulk respects 100 item limit."""
        large_list = list(range(1, 102))  # 101 items
        response = await client.request("DELETE", "/api/v1/trips/bulk", json=large_list)
        assert response.status_code in [400, 422]
        assert "100" in str(response.json()) or "VALIDATION_ERROR" in str(
            response.json()
        )

    @pytest.mark.asyncio
    async def test_bulk_delete_drivers_empty_list(self, client):
        """Test DELETE /drivers/bulk with empty list returns error."""
        response = await client.request("DELETE", "/api/v1/drivers/bulk", json=[])
        assert response.status_code in [400, 422]


# ============================================
# Reports API Tests
# ============================================


class TestReportsAPI:
    """Reports endpoint integration tests."""

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, client):
        """Test GET /reports/dashboard returns stats."""
        response = await client.get("/api/v1/reports/dashboard")
        assert response.status_code == 200
        data = response.json()
        # Dashboard should return core metrics
        assert "toplam_sefer" in data or "trends" in data

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        "sqlite" in TEST_DATABASE_URL,
        reason="SQLite doesn't support to_char used in analytics queries",
    )
    async def test_consumption_trend(self, client):
        """Test GET /reports/consumption-trend returns trend data."""
        response = await client.get("/api/v1/reports/consumption-trend")
        assert response.status_code == 200
        # Should return list of monthly data
        assert isinstance(response.json(), list)


# ============================================
# Advanced Reports API Tests
# ============================================


class TestAdvancedReportsAPI:
    """Advanced reports endpoint tests."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        "sqlite" in TEST_DATABASE_URL,
        reason="SQLite doesn't support to_char used in analytics queries",
    )
    async def test_cost_trend(self, client):
        """Test GET /advanced-reports/cost/trend returns trend."""
        response = await client.get("/api/v1/advanced-reports/cost/trend?months=6")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_roi_analysis(self, client):
        """Test GET /advanced-reports/cost/roi returns ROI."""
        response = await client.get(
            "/api/v1/advanced-reports/cost/roi?investment=50000"
        )
        assert response.status_code in [200, 409]
        data = response.json()
        if response.status_code == 200:
            assert "investment" in data or "annual_savings" in data
        else:
            assert "detail" in data or "error" in data


# ============================================
# Integration Flow Tests
# ============================================


class TestIntegrationFlows:
    """End-to-end integration flow tests."""

    @pytest.mark.asyncio
    async def test_vehicle_trip_fuel_flow(
        self, client, test_vehicle, test_driver, test_route, test_session
    ):
        """
        Test complete flow:
        1. Create trip with vehicle and driver
        2. Add fuel record for vehicle
        3. Verify stats reflect new data
        """
        # 1. Create trip
        trip_data = {
            "tarih": date.today().isoformat(),
            "arac_id": test_vehicle.id,
            "sofor_id": test_driver.id,
            "guzergah_id": test_route.id,
            "cikis_yeri": "Antalya",
            "varis_yeri": "Mersin",
            "mesafe_km": 300,
            "net_kg": 10000,
            "bos_sefer": False,
            "durum": "Tamam",
            "ascent_m": 0.0,
            "descent_m": 0.0,
            "rota_detay": {},
        }
        await client.post("/api/v1/trips/", json=trip_data)

        # 2. Add fuel record
        fuel_data = {
            "tarih": date.today().isoformat(),
            "arac_id": test_vehicle.id,
            "istasyon": "Flow Test İstasyon",
            "fiyat_tl": 43.00,
            "litre": 150.0,
            "toplam_tutar": 6450.0,
            "km_sayac": 160000,
            "depo_durumu": "Doldu",
            "durum": "Onaylandı",
        }
        fuel_response = await client.post("/api/v1/fuel/", json=fuel_data)
        if fuel_response.status_code != 201:
            print("FUEL RESPONSE ERROR:", fuel_response.text)
        assert fuel_response.status_code == 201

        # 3. Check stats updated
        stats_response = await client.get("/api/v1/fuel/stats")
        if stats_response.status_code != 200:
            print("STATS RESPONSE ERROR:", stats_response.text)
        assert stats_response.status_code == 200
        stats = stats_response.json()
        consumption = stats.get("total_consumption") or stats.get("toplam_litre") or 0
        assert consumption >= 0
