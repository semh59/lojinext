"""
Domain exception path testleri.

Bu testler hata yollarının doğru exception fırlattığını doğrular.
Puan 1 (exception hiyerarşisi) değişikliklerinin regresyon güvencesi.
"""

import pytest

from v2.modules.shared_kernel.exceptions import ImportValidationError


class TestImportValidationError:
    def test_carries_error_list(self):
        errors = ["Plaka boş olamaz", "Tarih geçersiz"]
        exc = ImportValidationError(errors)
        assert exc.errors == errors

    def test_str_representation_contains_errors(self):
        exc = ImportValidationError(["alan hata"])
        assert "alan hata" in str(exc)

    def test_empty_error_list(self):
        exc = ImportValidationError([])
        assert exc.errors == []

    def test_is_domain_error(self):
        from v2.modules.shared_kernel.exceptions import DomainError

        exc = ImportValidationError(["test"])
        assert isinstance(exc, DomainError)


class TestImportServiceValidation:
    """domain/field_validators.py::validate_plaka doğru hata fırlatmalı."""

    def test_validate_plaka_empty_raises(self):
        from v2.modules.import_excel.domain.field_validators import validate_plaka
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError, match="[Pp]laka"):
            validate_plaka(None)

    def test_validate_plaka_too_short_raises(self):
        from v2.modules.import_excel.domain.field_validators import validate_plaka
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            validate_plaka("AB")

    def test_validate_plaka_invalid_format_raises(self):
        from v2.modules.import_excel.domain.field_validators import validate_plaka
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError, match="[Ff]ormat"):
            validate_plaka("INVALID###")

    def test_validate_plaka_valid_returns_normalized(self):
        from v2.modules.import_excel.domain.field_validators import validate_plaka

        result = validate_plaka("34 abc 123")
        assert result == "34ABC123"

    def test_validate_name_too_short_raises(self):
        from v2.modules.import_excel.domain.field_validators import validate_name
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            validate_name("A")

    def test_validate_name_empty_raises(self):
        from v2.modules.import_excel.domain.field_validators import validate_name
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            validate_name("")

    def test_validate_name_valid_returns_titled(self):
        from v2.modules.import_excel.domain.field_validators import validate_name

        result = validate_name("ahmet çelik")
        assert result == "Ahmet Çelik"

    def test_validate_numeric_invalid_raises(self):
        from v2.modules.import_excel.domain.field_validators import validate_numeric
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            validate_numeric("abc", "mesafe")

    def test_validate_numeric_valid_returns_float(self):
        from v2.modules.import_excel.domain.field_validators import validate_numeric

        result = validate_numeric("42.5", "mesafe")
        assert result == 42.5

    def test_resolve_arac_id_not_found_raises(self):
        from v2.modules.import_excel.domain.entity_resolvers import resolve_arac_id
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        vehicles = [{"plaka": "34ABC123", "id": 1}]
        with pytest.raises(ImportValidationError):
            resolve_arac_id("99XYZ999", vehicles)

    def test_resolve_arac_id_none_returns_none(self):
        from v2.modules.import_excel.domain.entity_resolvers import resolve_arac_id

        result = resolve_arac_id(None, [])
        assert result is None

    def test_resolve_arac_id_found_returns_id(self):
        from v2.modules.import_excel.domain.entity_resolvers import resolve_arac_id

        vehicles = [{"plaka": "34ABC123", "id": 42}]
        result = resolve_arac_id("34 abc 123", vehicles)
        assert result == 42

    def test_normalize_text_handles_turkish_i(self):
        from v2.modules.import_excel.domain.field_validators import normalize_text

        result = normalize_text("İSTANBUL")
        assert result == "ISTANBUL"


class TestDomainExceptionHierarchy:
    """Exception sınıf hiyerarşisi doğru kurulmuş olmalı."""

    def test_all_exceptions_inherit_domain_error(self):
        from v2.modules.shared_kernel.exceptions import (
            AnomalyDetectionError,
            AuditLogError,
            DomainError,
            ExcelExportError,
            FuelCalculationError,
            MLPredictionError,
            RouteProcessingError,
        )

        subclasses = [
            FuelCalculationError,
            ExcelExportError,
            RouteProcessingError,
            MLPredictionError,
            AnomalyDetectionError,
            AuditLogError,
            ImportValidationError,
        ]
        for cls in subclasses:
            assert issubclass(cls, DomainError), (
                f"{cls.__name__} DomainError'dan türemeli"
            )

    def test_fuel_calculation_error_is_catchable_as_domain_error(self):
        from v2.modules.shared_kernel.exceptions import (
            DomainError,
            FuelCalculationError,
        )

        with pytest.raises(DomainError):
            raise FuelCalculationError("test")


class TestBaseRepositorySafety:
    def test_instantiation_without_model_raises_type_error(self):
        from v2.modules.shared_kernel.infrastructure.base_repository import (
            BaseRepository,
        )

        class ModellessRepo(BaseRepository):
            model = None

        with pytest.raises(TypeError, match="model tanımlanmamış"):
            ModellessRepo(session=None)

    def test_session_property_raises_runtime_error_without_session(self):
        from v2.modules.fleet.infrastructure.vehicle_repository import AracRepository

        repo = AracRepository(session=None)
        with pytest.raises(RuntimeError):
            _ = repo.session

    def test_instantiation_with_valid_model_and_no_session_succeeds(self):
        from v2.modules.fleet.infrastructure.vehicle_repository import AracRepository

        repo = AracRepository(session=None)
        assert repo._session is None


class TestDomainErrorHTTPMapping:
    def test_http_mapping_table_contains_expected_codes(self):
        from app.main import _DOMAIN_ERROR_STATUS
        from v2.modules.shared_kernel.exceptions import (
            AnomalyDetectionError,
            AuditLogError,
            ExcelExportError,
            FuelCalculationError,
            ImportValidationError,
            MLPredictionError,
            RouteProcessingError,
        )

        assert _DOMAIN_ERROR_STATUS[FuelCalculationError] == 422
        assert _DOMAIN_ERROR_STATUS[ImportValidationError] == 422
        assert _DOMAIN_ERROR_STATUS[ExcelExportError] == 422
        assert _DOMAIN_ERROR_STATUS[RouteProcessingError] == 422
        assert _DOMAIN_ERROR_STATUS[MLPredictionError] == 503
        assert _DOMAIN_ERROR_STATUS[AnomalyDetectionError] == 503
        assert _DOMAIN_ERROR_STATUS[AuditLogError] == 500

    @pytest.mark.asyncio
    async def test_domain_error_handler_ml_returns_503(self):
        import json
        from unittest.mock import MagicMock

        from fastapi import Request

        from app.main import domain_error_handler
        from v2.modules.shared_kernel.exceptions import MLPredictionError

        exc = MLPredictionError("Model yüklenemedi", reason="MODEL_NOT_FOUND")
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/predict"

        response = await domain_error_handler(request, exc)
        body = json.loads(response.body)
        assert response.status_code == 503
        assert "MLPREDICTION" in body["error"]["code"]
        assert "trace_id" in body["error"]

    @pytest.mark.asyncio
    async def test_import_validation_handler_includes_errors_list(self):
        import json
        from unittest.mock import MagicMock

        from fastapi import Request

        from app.main import domain_error_handler
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        exc = ImportValidationError(["Plaka boş", "Tarih geçersiz"], row=3)
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/import"

        response = await domain_error_handler(request, exc)
        body = json.loads(response.body)
        assert response.status_code == 422
        assert body["error"]["details"]["errors"] == ["Plaka boş", "Tarih geçersiz"]
        assert body["error"]["details"]["row"] == 3


class TestDomainErrorContextFields:
    def test_fuel_calculation_error_carries_context(self):
        from v2.modules.shared_kernel.exceptions import FuelCalculationError

        exc = FuelCalculationError(
            "Depo aşımı",
            field_name="yakit_miktari",
            entity_id=42,
            reason="CAPACITY_EXCEEDED",
        )
        assert exc.field_name == "yakit_miktari"
        assert exc.entity_id == 42
        assert exc.reason == "CAPACITY_EXCEEDED"
        d = exc.to_dict()
        assert d["field"] == "yakit_miktari"
        assert d["entity_id"] == 42
        assert d["message"] == "Depo aşımı"

    def test_import_validation_error_carries_row_and_errors(self):
        from v2.modules.shared_kernel.exceptions import ImportValidationError

        exc = ImportValidationError(["Plaka boş", "Tarih geçersiz"], row=5)
        assert exc.row == 5
        assert exc.errors == ["Plaka boş", "Tarih geçersiz"]
        d = exc.to_dict()
        assert d["row"] == 5
        assert d["errors"] == ["Plaka boş", "Tarih geçersiz"]

    def test_domain_error_to_dict_without_optionals(self):
        from v2.modules.shared_kernel.exceptions import RouteProcessingError

        exc = RouteProcessingError("test")
        d = exc.to_dict()
        assert "field" not in d
        assert "entity_id" not in d
        assert d["message"] == "test"

    def test_all_subclasses_accept_context_kwargs(self):
        from v2.modules.shared_kernel.exceptions import (
            AnomalyDetectionError,
            AuditLogError,
            DomainError,
            ExcelExportError,
            FuelCalculationError,
            MLPredictionError,
            RouteProcessingError,
        )

        for cls in [
            FuelCalculationError,
            ExcelExportError,
            RouteProcessingError,
            MLPredictionError,
            AnomalyDetectionError,
            AuditLogError,
        ]:
            exc = cls("test", field_name="x", entity_id=1, reason="R")
            assert isinstance(exc, DomainError)
            d = exc.to_dict()
            assert d["field"] == "x"
            assert d["entity_id"] == 1
