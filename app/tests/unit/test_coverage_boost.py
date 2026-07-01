"""
Unit tests targeting coverage gaps in errors.py, route_validator.py,
user_service.py, and maintenance_service.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import (
    BusinessException,
    DiagnosticHelper,
    create_error_response,
)
from app.core.services.route_validator import RouteValidator
from app.main import (
    business_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)

# ---------------------------------------------------------------------------
# DiagnosticHelper
# ---------------------------------------------------------------------------


class TestDiagnosticHelper:
    def test_get_suggestion_business_error(self):
        result = DiagnosticHelper.get_suggestion("BUSINESS_ERROR", "some message")
        assert result is not None
        assert (
            "iş kuralı" in result.lower()
            or "is kurali" in result.lower()
            or "kural" in result.lower()
        )

    def test_get_suggestion_validation_error(self):
        result = DiagnosticHelper.get_suggestion(
            "VALIDATION_ERROR", "validation failed"
        )
        assert result is not None

    def test_get_suggestion_db_error(self):
        result = DiagnosticHelper.get_suggestion("DB_ERROR", "connection failed")
        assert result is not None

    def test_get_suggestion_auth_error(self):
        result = DiagnosticHelper.get_suggestion("AUTH_ERROR", "token expired")
        assert result is not None

    def test_get_suggestion_empty_trip_with_load_via_message(self):
        result = DiagnosticHelper.get_suggestion(
            "BUSINESS_ERROR", "bos_sefer ile ton girisi"
        )
        assert result is not None
        assert "bos_sefer" in result.lower() or "bos" in result.lower()

    def test_get_suggestion_analysis_gap_via_message(self):
        result = DiagnosticHelper.get_suggestion(
            "BUSINESS_ERROR", "analiz gap bulunamadi"
        )
        assert result is not None

    def test_get_suggestion_periyot_via_message(self):
        result = DiagnosticHelper.get_suggestion("BUSINESS_ERROR", "periyot eksik")
        assert result is not None

    def test_get_suggestion_unknown_code(self):
        result = DiagnosticHelper.get_suggestion("UNKNOWN_CODE", "some message")
        assert result is None


# ---------------------------------------------------------------------------
# BusinessException
# ---------------------------------------------------------------------------


class TestBusinessException:
    def test_default_code(self):
        exc = BusinessException("test message")
        assert exc.message == "test message"
        assert exc.code == "BUSINESS_ERROR"
        assert exc.details is None
        assert str(exc) == "test message"

    def test_custom_code_and_details(self):
        exc = BusinessException("msg", code="CUSTOM", details={"key": "val"})
        assert exc.code == "CUSTOM"
        assert exc.details == {"key": "val"}

    def test_is_exception(self):
        exc = BusinessException("fail")
        assert isinstance(exc, Exception)


# ---------------------------------------------------------------------------
# create_error_response
# ---------------------------------------------------------------------------


class TestCreateErrorResponse:
    def test_returns_json_response(self):
        resp = create_error_response(400, "bad input", "VALIDATION_ERROR", "trace-123")
        assert resp.status_code == 400

    def test_response_body_structure(self):
        import json

        resp = create_error_response(
            404, "not found", "NOT_FOUND", "trace-456", details={"id": 1}
        )
        data = json.loads(resp.body)
        assert "success" not in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "not found"
        assert data["error"]["trace_id"] == "trace-456"
        assert data["error"]["details"] == {"id": 1}

    def test_no_details_omitted(self):
        import json

        resp = create_error_response(500, "server error", "INTERNAL_ERROR", "trace-789")
        data = json.loads(resp.body)
        assert "details" not in data["error"]
        assert "timestamp" not in data["error"]


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def _make_mock_request(path: str = "/api/v1/test") -> MagicMock:
    req = MagicMock(spec=Request)
    req.url.path = path
    req.method = "GET"
    return req


class TestUnhandledExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_500(self):
        req = _make_mock_request()
        exc = RuntimeError("unexpected crash")
        with patch("app.main.get_correlation_id", return_value="corr-001"):
            resp = await unhandled_exception_handler(req, exc)
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_response_body_has_error_code(self):
        import json

        req = _make_mock_request()
        exc = ValueError("boom")
        with patch("app.main.get_correlation_id", return_value="corr-002"):
            resp = await unhandled_exception_handler(req, exc)
        data = json.loads(resp.body)
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"


class TestBusinessExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_400(self):
        req = _make_mock_request()
        exc = BusinessException("rule violation", code="BUSINESS_ERROR")
        with patch("app.main.get_correlation_id", return_value="corr-003"):
            resp = await business_exception_handler(req, exc)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_response_body_has_message(self):
        import json

        req = _make_mock_request()
        exc = BusinessException("rule violation", code="BUSINESS_ERROR")
        with patch("app.main.get_correlation_id", return_value="corr-004"):
            resp = await business_exception_handler(req, exc)
        data = json.loads(resp.body)
        assert data["error"]["message"] == "rule violation"


class TestValidationExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_422(self):
        import json

        req = _make_mock_request()

        class FakeValidationError(RequestValidationError):
            def errors(self):
                return [
                    {"loc": ("body", "field1"), "msg": "required", "type": "missing"}
                ]

        exc = FakeValidationError(errors=[])
        with patch("app.main.get_correlation_id", return_value="corr-005"):
            resp = await validation_exception_handler(req, exc)
        assert resp.status_code == 422
        data = json.loads(resp.body)
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_empty_loc(self):
        import json

        req = _make_mock_request()

        class FakeValidationError(RequestValidationError):
            def errors(self):
                return [{"loc": (), "msg": "bad value", "type": "value_error"}]

        exc = FakeValidationError(errors=[])
        with patch("app.main.get_correlation_id", return_value="corr-006"):
            resp = await validation_exception_handler(req, exc)
        data = json.loads(resp.body)
        detail = data["error"]["details"][0]
        assert detail["loc"] == []
        assert detail["msg"] == "bad value"


class TestHttpExceptionHandler:
    @pytest.mark.asyncio
    async def test_returns_correct_status_code(self):
        req = _make_mock_request()
        exc = StarletteHTTPException(status_code=404, detail="Not found")
        with patch("app.main.get_correlation_id", return_value="corr-007"):
            resp = await http_exception_handler(req, exc)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_dict_detail_passthrough(self):
        import json

        req = _make_mock_request()
        exc = StarletteHTTPException(
            status_code=403,
            detail={"error": {"code": "FORBIDDEN", "message": "denied"}},
        )
        with patch("app.main.get_correlation_id", return_value="corr-008"):
            resp = await http_exception_handler(req, exc)
        assert resp.status_code == 403
        data = json.loads(resp.body)
        assert data["error"]["code"] == "HTTP_403"


# ---------------------------------------------------------------------------
# RouteValidator
# ---------------------------------------------------------------------------


class TestRouteValidatorGradeThresholds:
    def test_short_route(self):
        threshold, cap = RouteValidator._get_grade_thresholds(30)
        assert threshold == 0.025
        assert cap == pytest.approx(threshold * 1.5)

    def test_medium_short_route(self):
        threshold, cap = RouteValidator._get_grade_thresholds(100)
        assert threshold == 0.015

    def test_medium_route(self):
        threshold, cap = RouteValidator._get_grade_thresholds(200)
        assert threshold == 0.010

    def test_long_route(self):
        threshold, cap = RouteValidator._get_grade_thresholds(500)
        assert threshold == 0.007

    def test_boundary_at_50(self):
        threshold, _ = RouteValidator._get_grade_thresholds(50)
        assert threshold == 0.015

    def test_boundary_at_150(self):
        threshold, _ = RouteValidator._get_grade_thresholds(150)
        assert threshold == 0.010


class TestRouteValidatorValidateAndCorrect:
    def test_zero_distance_returns_unchanged(self):
        data = {"distance_km": 0, "ascent_m": 100, "descent_m": 50}
        result = RouteValidator.validate_and_correct(data)
        assert result["ascent_m"] == 100
        assert result.get("is_corrected") is None

    def test_normal_data_not_corrected(self):
        data = {"distance_km": 200, "ascent_m": 500, "descent_m": 400}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is False

    def test_high_incline_corrected(self):
        data = {"distance_km": 200, "ascent_m": 5000, "descent_m": 100}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is True
        assert "High Incline" in result["correction_reason"]

    def test_high_decline_corrected(self):
        data = {"distance_km": 200, "ascent_m": 100, "descent_m": 5000}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is True
        assert "High Decline" in result["correction_reason"]

    def test_both_corrected(self):
        data = {"distance_km": 100, "ascent_m": 3000, "descent_m": 3000}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is True
        assert "High Incline" in result["correction_reason"]
        assert "High Decline" in result["correction_reason"]

    def test_mesafe_km_key_used(self):
        data = {"mesafe_km": 100, "ascent_m": 100, "descent_m": 100}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is False

    def test_mesafe_key_used(self):
        data = {"mesafe": 100, "ascent_m": 100, "descent_m": 100}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is False

    def test_original_not_mutated(self):
        original = {"distance_km": 200, "ascent_m": 9000, "descent_m": 100}
        RouteValidator.validate_and_correct(original)
        assert original["ascent_m"] == 9000

    def test_missing_ascent_descent(self):
        data = {"distance_km": 200}
        result = RouteValidator.validate_and_correct(data)
        assert result["is_corrected"] is False


# ---------------------------------------------------------------------------
# UserService — real DB tests (db_session monkeypatches UnitOfWork)
# ---------------------------------------------------------------------------


class TestUserService:
    @pytest.fixture
    def svc(self):
        from app.core.services.user_service import UserService

        return UserService()

    @pytest.mark.asyncio
    async def test_list_users_returns_list(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        await seed_kullanici(db_session)
        await db_session.commit()
        result = await svc.list_users()
        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_get_user_raises_404_when_missing(self, svc, db_session):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_user(999999)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_returns_user(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        user = await seed_kullanici(db_session, email="getuser@test.local")
        await db_session.commit()
        result = await svc.get_user(user.id)
        assert result["id"] == user.id
        assert result["email"] == "getuser@test.local"

    @pytest.mark.asyncio
    async def test_create_user_raises_400_on_existing_email(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        await seed_kullanici(db_session, email="exists@test.local")
        await db_session.commit()
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.create_user(
                {
                    "email": "exists@test.local",
                    "ad_soyad": "Duplicate",
                    "rol_id": 1,
                    "sifre": "pw",
                },
                created_by_id=0,
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_user_returns_true(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        user = await seed_kullanici(db_session)
        await db_session.commit()
        result = await svc.delete_user(user.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_update_user_raises_404_when_missing(self, svc, db_session):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await svc.update_user(999999, {"ad_soyad": "New"})
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_user_success(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        user = await seed_kullanici(db_session, ad_soyad="Original Name")
        await db_session.commit()
        result = await svc.update_user(user.id, {"ad_soyad": "Updated Name"})
        assert result["ad_soyad"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_user_with_password(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        user = await seed_kullanici(db_session)
        await db_session.commit()
        result = await svc.update_user(user.id, {"sifre": "newsecret123"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_user_no_data_returns_existing(self, svc, db_session):
        from app.tests._helpers.seed import seed_kullanici

        # AUDIT-025: empty dict → no fields to update → early return of existing row.
        user = await seed_kullanici(db_session, ad_soyad="OriginalName")
        await db_session.commit()
        result = await svc.update_user(user.id, {})
        assert result["id"] == user.id

    @pytest.mark.asyncio
    async def test_create_user_success(self, svc, db_session):
        from app.database.models import Rol

        rol = Rol(ad="create-user-test-rol", yetkiler={})
        db_session.add(rol)
        await db_session.flush()
        await db_session.commit()
        result = await svc.create_user(
            {
                "email": "newuser@test.local",
                "ad_soyad": "New User",
                "rol_id": rol.id,
                "sifre": "testpw123",
            },
            created_by_id=0,
        )
        assert result is not None
        assert result["email"] == "newuser@test.local"

    @pytest.mark.asyncio
    async def test_delete_user_returns_false_when_not_found(self, svc, db_session):
        result = await svc.delete_user(999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_user_raises_500_when_update_fails(self, svc):
        # Documented boundary: `kullanici_repo.update` returning False while the
        # row exists is a TOCTOU race condition guard — unreachable in a
        # single-tenant real DB. Kept mocked to preserve the dead-code branch.
        from app.database.unit_of_work import UnitOfWork

        existing = {"id": 1, "email": "a@b.com"}
        mock_uow = MagicMock()
        mock_uow.kullanici_repo = MagicMock()
        mock_uow.kullanici_repo.get_by_id = AsyncMock(return_value=existing)
        mock_uow.kullanici_repo.update = AsyncMock(return_value=False)
        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await svc.update_user(1, {"ad_soyad": "Fail"})
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_create_user_raises_500_when_read_back_fails(self, svc):
        # Documented boundary: create succeeds but immediate get_by_id returns
        # None is physically impossible in a non-distributed DB — tested via
        # injection to cover the defensive guard branch.
        from app.database.unit_of_work import UnitOfWork

        mock_uow = MagicMock()
        mock_uow.kullanici_repo = MagicMock()
        mock_uow.kullanici_repo.get_by_email = AsyncMock(return_value=None)
        mock_uow.kullanici_repo.create = AsyncMock(return_value=5)
        mock_uow.kullanici_repo.get_by_id = AsyncMock(return_value=None)
        mock_uow.commit = AsyncMock(return_value=None)
        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=mock_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
            patch("app.core.services.user_service.get_password_hash", return_value="h"),
        ):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await svc.create_user(
                    {
                        "email": "x@x.com",
                        "ad_soyad": "X",
                        "rol_id": 1,
                        "sifre": "pw",
                    },
                    created_by_id=1,
                )
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# MaintenanceService — real DB tests (db_session monkeypatches UnitOfWork)
# ---------------------------------------------------------------------------


class TestMaintenanceService:
    @pytest.fixture
    def svc(self):
        from app.core.services.maintenance_service import MaintenanceService

        return MaintenanceService()

    @pytest.mark.asyncio
    async def test_create_record_raises_404_when_vehicle_missing(self, svc, db_session):
        from datetime import datetime

        from fastapi import HTTPException

        from app.database.models import BakimTipi

        with pytest.raises(HTTPException) as exc_info:
            await svc.create_maintenance_record(
                arac_id=999999,
                bakim_tipi=BakimTipi.PERIYODIK,
                km_bilgisi=100000,
                bakim_tarihi=datetime.now(),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_maintenance_history(self, svc, db_session):
        from app.tests._helpers.seed import seed_arac

        arac = await seed_arac(db_session, plaka="34MAINT01")
        await db_session.commit()
        result = await svc.get_vehicle_maintenance_history(arac.id)
        assert result == []

    @pytest.mark.asyncio
    async def test_mark_as_completed_true(self, svc, db_session):
        from datetime import datetime, timezone

        from app.database.models import AracBakim, BakimTipi
        from app.tests._helpers.seed import seed_arac

        arac = await seed_arac(db_session, plaka="34COMP01")
        await db_session.flush()
        bakim = AracBakim(
            arac_id=arac.id,
            bakim_tipi=BakimTipi.PERIYODIK,
            km_bilgisi=100000,
            bakim_tarihi=datetime.now(timezone.utc),
            maliyet=0,
            detaylar="",
            tamamlandi=False,
        )
        db_session.add(bakim)
        await db_session.flush()
        await db_session.commit()
        result = await svc.mark_as_completed(bakim.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_as_completed_false(self, svc, db_session):
        result = await svc.mark_as_completed(999999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_upcoming_alerts_empty(self, svc, db_session):
        result = await svc.get_upcoming_alerts()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_upcoming_alerts_with_items(self, svc, db_session):
        from datetime import datetime, timedelta, timezone

        from app.database.models import AracBakim, BakimTipi
        from app.tests._helpers.seed import seed_arac

        arac = await seed_arac(db_session, plaka="34ALT001")
        await db_session.flush()
        now = datetime.now(timezone.utc)
        # get_upcoming_maintenance filters bakim_tarihi >= now, so all returned
        # records are in the future → vade_durumu is always "UPCOMING".
        near = AracBakim(
            arac_id=arac.id,
            bakim_tipi=BakimTipi.PERIYODIK,
            km_bilgisi=80000,
            bakim_tarihi=now + timedelta(days=3),
            maliyet=0,
            detaylar="",
            tamamlandi=False,
        )
        far = AracBakim(
            arac_id=arac.id,
            bakim_tipi=BakimTipi.ARIZA,
            km_bilgisi=90000,
            bakim_tarihi=now + timedelta(days=14),
            maliyet=0,
            detaylar="",
            tamamlandi=False,
        )
        db_session.add_all([near, far])
        await db_session.flush()
        await db_session.commit()
        result = await svc.get_upcoming_alerts()
        assert len(result) == 2
        assert all(r["vade_durumu"] == "UPCOMING" for r in result)
        assert result[0]["plaka"] == "34ALT001"


# ---------------------------------------------------------------------------
# IdempotencyGuard
# ---------------------------------------------------------------------------


class TestIdempotencyGuard:
    @pytest.mark.asyncio
    async def test_no_key_passes_through(self):
        from app.infrastructure.resilience.idempotency import IdempotencyGuard

        guard = IdempotencyGuard()
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value=None)
        result = await guard(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_none_passes_through(self):
        from app.infrastructure.resilience.idempotency import IdempotencyGuard

        guard = IdempotencyGuard()
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value="test-key-123")
        req.state = MagicMock()
        req.state.user = None
        with patch(
            "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
            return_value=None,
        ):
            result = await guard(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_new_key_stored_in_redis(self):
        from app.infrastructure.resilience.idempotency import IdempotencyGuard

        guard = IdempotencyGuard()
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value="unique-key-456")
        req.state = MagicMock()
        req.state.user = None
        mock_redis = AsyncMock()
        # AUDIT-153: atomik set_nx (get-then-set TOCTOU yerine). True = yeni anahtar.
        mock_redis.set_nx = AsyncMock(return_value=True)
        with patch(
            "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
            return_value=mock_redis,
        ):
            result = await guard(req)
        assert result is None
        mock_redis.set_nx.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_key_raises_409(self):
        from fastapi import HTTPException

        from app.infrastructure.resilience.idempotency import IdempotencyGuard

        guard = IdempotencyGuard()
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value="dup-key-789")
        req.state = MagicMock()
        req.state.user = None
        mock_redis = AsyncMock()
        # AUDIT-153: set_nx False → anahtar zaten var (duplicate) → 409.
        mock_redis.set_nx = AsyncMock(return_value=False)
        with patch(
            "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
            return_value=mock_redis,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await guard(req)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_redis_exception_does_not_block(self):
        from app.infrastructure.resilience.idempotency import IdempotencyGuard

        guard = IdempotencyGuard()
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value="error-key")
        req.state = MagicMock()
        req.state.user = None
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        with patch(
            "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
            return_value=mock_redis,
        ):
            result = await guard(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_key_dependency_factory(self):
        from app.infrastructure.resilience.idempotency import IdempotencyKeyDependency

        dep = IdempotencyKeyDependency("create_trip")
        assert dep.operation_name == "create_trip"
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value=None)
        result = await dep(req)
        assert result is None

    @pytest.mark.asyncio
    async def test_idempotency_with_authenticated_user(self):
        from app.infrastructure.resilience.idempotency import IdempotencyGuard

        guard = IdempotencyGuard()
        req = MagicMock(spec=Request)
        req.headers.get = MagicMock(return_value="auth-key-001")
        mock_user = MagicMock()
        mock_user.id = 42
        req.state = MagicMock()
        req.state.user = mock_user
        mock_redis = AsyncMock()
        # AUDIT-153: atomik set_nx — user-scoped cache_key ilk argümandır.
        mock_redis.set_nx = AsyncMock(return_value=True)
        with patch(
            "app.infrastructure.cache.redis_pubsub.get_pubsub_manager",
            return_value=mock_redis,
        ):
            await guard(req)
        call_args = mock_redis.set_nx.call_args[0]
        assert "42" in call_args[0]


# ---------------------------------------------------------------------------
# PolylineDecoder
# ---------------------------------------------------------------------------


class TestPolylineDecoder:
    def test_empty_string(self):
        from app.core.utils.polyline import PolylineDecoder

        result = PolylineDecoder.decode("")
        assert result == []

    def test_known_polyline(self):
        from app.core.utils.polyline import PolylineDecoder

        # "_p~iF~ps|U_ulLnnqC_mqNvxq`@" encodes 3 known points
        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        points = PolylineDecoder.decode(encoded)
        assert len(points) == 3
        lat0, lng0 = points[0]
        assert abs(lat0 - 38.5) < 0.01
        assert abs(lng0 - (-120.2)) < 0.01

    def test_single_point(self):
        from app.core.utils.polyline import PolylineDecoder

        # Istanbul approx: 41.015, 28.979 → encode manually
        # Simple test: decode should return at least 1 point for non-empty valid input
        encoded = "_p~iF~ps|U"
        points = PolylineDecoder.decode(encoded)
        assert len(points) == 1

    def test_negative_coordinates(self):
        from app.core.utils.polyline import PolylineDecoder

        # Negative coordinates are properly decoded
        encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
        points = PolylineDecoder.decode(encoded)
        assert any(lng < 0 for _, lng in points)

    def test_returns_float_tuples(self):
        from app.core.utils.polyline import PolylineDecoder

        encoded = "_p~iF~ps|U"
        points = PolylineDecoder.decode(encoded)
        assert len(points) > 0
        lat, lng = points[0]
        assert isinstance(lat, float)
        assert isinstance(lng, float)


class TestParseDateParam:
    """Tests for app.api.v1.utils.parse_date_param."""

    def test_none_returns_none(self):
        from app.api.v1.utils import parse_date_param

        assert parse_date_param(None) is None

    def test_empty_string_returns_none(self):
        from app.api.v1.utils import parse_date_param

        assert parse_date_param("") is None

    def test_valid_date(self):
        from datetime import date

        from app.api.v1.utils import parse_date_param

        result = parse_date_param("2024-03-15")
        assert result == date(2024, 3, 15)

    def test_invalid_format_raises_400(self):
        from fastapi import HTTPException

        from app.api.v1.utils import parse_date_param

        with pytest.raises(HTTPException) as exc_info:
            parse_date_param("15-03-2024", field_name="tarih")
        assert exc_info.value.status_code == 400
        assert "tarih" in exc_info.value.detail


class TestRateLimiterModule:
    """Ensure rate_limiter module loads and exposes a limiter object."""

    def test_limiter_importable(self):
        from app.api.middleware.rate_limiter import limiter

        assert limiter is not None

    def test_limiter_has_limit_method(self):
        from app.api.middleware.rate_limiter import limiter

        assert callable(getattr(limiter, "limit", None))

    def test_noop_limiter_passthrough(self):
        from app.api.middleware.rate_limiter import _NoopLimiter

        noop = _NoopLimiter()
        decorator = noop.limit("10/minute")

        def dummy():
            return 42

        wrapped = decorator(dummy)
        assert wrapped is dummy

    def test_build_limiter_raises_in_prod_without_slowapi(self, monkeypatch):
        """2026-07-01 prod-grade denetimi P1: slowapi eksikse prod'da
        fail-closed — uygulama sessizce rate-limit'siz ayağa kalkmak yerine
        başlamayı reddetmeli."""
        import app.api.middleware.rate_limiter as rl_module

        monkeypatch.setattr(rl_module, "Limiter", None)
        with pytest.raises(RuntimeError, match="refusing to start in production"):
            rl_module._build_limiter("prod")

    def test_build_limiter_falls_back_in_dev_without_slowapi(self, monkeypatch):
        """Dev/test ortamında slowapi eksikliği eski fail-open (NoopLimiter +
        critical log) davranışını korur — yerel geliştirmeyi bloklamaz."""
        import app.api.middleware.rate_limiter as rl_module

        monkeypatch.setattr(rl_module, "Limiter", None)
        result = rl_module._build_limiter("dev")
        assert isinstance(result, rl_module._NoopLimiter)

    def test_build_limiter_uses_real_limiter_when_slowapi_available(self):
        """slowapi kuruluysa (bu test ortamında olduğu gibi) prod'da da
        sorunsuz gerçek Limiter döner — fail-closed dalı hiç tetiklenmez."""
        import app.api.middleware.rate_limiter as rl_module

        if rl_module.Limiter is None:
            pytest.skip("slowapi not installed in this environment")
        result = rl_module._build_limiter("prod", rate_limit_enabled=True)
        assert not isinstance(result, rl_module._NoopLimiter)


class TestOpenRouteServiceOffline:
    """Tests for OpenRouteService offline (no-API) code paths."""

    def test_instantiation(self):
        from app.core.services.openroute_service import OpenRouteService

        svc = OpenRouteService(api_key="")
        assert svc is not None

    def test_is_configured_false_without_key(self):
        from app.core.services.openroute_service import OpenRouteService

        with patch("app.core.services.openroute_service.settings") as mock_settings:
            mock_settings.OPENROUTESERVICE_API_KEY = ""
            svc = OpenRouteService(api_key="")
        svc.api_key = ""  # ensure key is cleared for the check
        assert svc.is_configured() is False

    def test_is_configured_true_with_key(self):
        from app.core.services.openroute_service import (
            HTTPX_AVAILABLE,
            OpenRouteService,
        )

        svc = OpenRouteService(api_key="test-key-123")
        assert svc.is_configured() == HTTPX_AVAILABLE

    def test_haversine_distance(self):
        from app.core.services.openroute_service import OpenRouteService

        svc = OpenRouteService(api_key="")
        # Istanbul (28.97, 41.01) → Ankara (32.86, 39.92) ≈ 352 km
        dist = svc._haversine_distance(28.97, 41.01, 32.86, 39.92)
        assert 300 < dist < 420

    def test_haversine_same_point(self):
        from app.core.services.openroute_service import OpenRouteService

        svc = OpenRouteService(api_key="")
        dist = svc._haversine_distance(28.97, 41.01, 28.97, 41.01)
        assert dist < 0.001

    def test_get_route_profile_offline(self):
        from app.core.services.openroute_service import OpenRouteService, RouteProfile

        svc = OpenRouteService(api_key="")
        profile = svc.get_route_profile_offline((28.97, 41.01), (32.86, 39.92))
        assert isinstance(profile, RouteProfile)
        assert profile.distance_km > 0
        assert profile.duration_hours > 0
        assert profile.ascent_m >= 0
        assert profile.descent_m >= 0

    @pytest.mark.asyncio
    async def test_get_route_profile_falls_back_offline_when_unconfigured(self):
        from app.core.services.openroute_service import OpenRouteService, RouteProfile

        svc = OpenRouteService(api_key="")
        profile = await svc.get_route_profile((28.97, 41.01), (32.86, 39.92))
        assert isinstance(profile, RouteProfile)
        assert profile.distance_km > 0


class TestCacheInvalidationSetup:
    """Tests for cache_invalidation.setup_cache_invalidation."""

    def test_setup_registers_event_handlers(self):
        from unittest.mock import MagicMock, patch

        mock_bus = MagicMock()
        mock_cache = MagicMock()
        with (
            patch(
                "app.infrastructure.cache.cache_invalidation.get_event_bus",
                return_value=mock_bus,
            ),
            patch(
                "app.infrastructure.cache.cache_invalidation.get_cache_manager",
                return_value=mock_cache,
            ),
        ):
            from app.infrastructure.cache.cache_invalidation import (
                setup_cache_invalidation,
            )

            setup_cache_invalidation()
            assert mock_bus.subscribe.call_count >= 3

    @pytest.mark.asyncio
    async def test_trigger_dashboard_update_ok(self):
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock(return_value=None)
        with patch(
            "app.infrastructure.cache.cache_invalidation.get_pubsub_manager",
            return_value=mock_pubsub,
        ):
            from app.infrastructure.cache.cache_invalidation import (
                trigger_dashboard_update,
            )

            await trigger_dashboard_update()
            mock_pubsub.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_dashboard_update_handles_error(self):
        mock_pubsub = MagicMock()
        mock_pubsub.publish = AsyncMock(side_effect=Exception("Redis down"))
        with patch(
            "app.infrastructure.cache.cache_invalidation.get_pubsub_manager",
            return_value=mock_pubsub,
        ):
            from app.infrastructure.cache.cache_invalidation import (
                trigger_dashboard_update,
            )

            await trigger_dashboard_update()  # must not raise


class TestInterfacesImport:
    """Ensure interface module-level code (imports + TypeVar) is counted as covered."""

    def test_interfaces_importable(self):
        # Confirm these are abstract (can't be instantiated)
        import inspect

        from app.core.interfaces import (
            IAracRepository,
            ILokasyonRepository,
            IPeriyotRepository,
            ISeferRepository,
            ISoforRepository,
            IYakitRepository,
        )

        for cls in (
            IAracRepository,
            ISoforRepository,
            IYakitRepository,
            ISeferRepository,
            ILokasyonRepository,
            IPeriyotRepository,
        ):
            assert inspect.isabstract(cls)

    def test_cache_invalidation_importable(self):
        from app.infrastructure.cache import cache_invalidation  # noqa: F401

        assert hasattr(cache_invalidation, "__name__")

    def test_init_db_importable(self):
        from app.database import init_db  # noqa: F401

        assert hasattr(init_db, "__name__")

    def test_openroute_service_importable(self):
        from app.core.services import openroute_service  # noqa: F401

        assert hasattr(openroute_service, "__name__")

    def test_rag_sync_service_importable(self):
        from app.core.ai import rag_sync_service  # noqa: F401

        assert hasattr(rag_sync_service, "__name__")


# ---------------------------------------------------------------------------
# System endpoint (error-report)
# ---------------------------------------------------------------------------


class TestSystemErrorReport:
    def test_frontend_error_report_schema(self):
        from app.api.v1.endpoints.system import FrontendErrorReport

        report = FrontendErrorReport(
            message="TypeError: Cannot read property 'x' of null",
            url="https://app.example.com/trips",
            userAgent="Mozilla/5.0",
            timestamp="2026-05-13T22:00:00Z",
            severity="error",
        )
        assert report.message.startswith("TypeError")
        assert report.severity == "error"
        assert report.stack is None

    def test_frontend_error_report_default_severity(self):
        from app.api.v1.endpoints.system import FrontendErrorReport

        report = FrontendErrorReport(
            message="Something broke",
            url="https://app.example.com/fuel",
            userAgent="Chrome",
            timestamp="2026-05-13T22:00:00Z",
        )
        assert report.severity == "error"

    @pytest.mark.asyncio
    async def test_receive_frontend_error_logs(self):
        from unittest.mock import MagicMock, patch

        from starlette.requests import Request as StarletteRequest

        from app.api.v1.endpoints.system import (
            FrontendErrorReport,
            receive_frontend_error,
        )

        report = FrontendErrorReport(
            message="Unhandled rejection",
            url="https://app.example.com/",
            userAgent="Firefox",
            timestamp="2026-05-13T22:00:00Z",
            severity="warning",
        )
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/system/error-report",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "query_string": b"",
        }
        real_request = StarletteRequest(scope)

        mock_user = MagicMock()
        mock_user.id = 1

        with patch(
            "app.infrastructure.monitoring.event_bus.ErrorEventBus.emit",
            new_callable=AsyncMock,
        ):
            result = await receive_frontend_error(report, real_request, mock_user)
            assert result is None
