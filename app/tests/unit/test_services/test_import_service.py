"""
Unit Tests - ImportService
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.core.services.import_service import ImportService


class TestResolveIds:
    """ID resolution tests for ImportService (Plaka and Name matching)"""

    @pytest.fixture
    def service(self):
        return ImportService(
            arac_repo=MagicMock(),
            sofor_repo=MagicMock(),
            sefer_service=MagicMock(),
            yakit_service=MagicMock(),
            arac_service=MagicMock(),
            sofor_service=MagicMock(),
        )

    @pytest.fixture
    def sample_data(self):
        return {
            "vehicles": [
                {"id": 1, "plaka": "34 ABC 123", "marka": "Mercedes"},
                {"id": 2, "plaka": "06 XYZ 456", "marka": "Volvo"},
                {"id": 3, "plaka": "16TIR789", "marka": "Scania"},
            ],
            "drivers": [
                {"id": 1, "ad_soyad": "Ahmet Yılmaz"},
                {"id": 2, "ad_soyad": "Mehmet Kara"},
            ],
        }

    def test_resolve_arac_id_variants(self, service, sample_data):
        vehicles = sample_data["vehicles"]
        assert service._resolve_arac_id("34 ABC 123", vehicles) == 1
        assert service._resolve_arac_id("34ABC123", vehicles) == 1
        assert service._resolve_arac_id("34  abc   123", vehicles) == 1
        assert service._resolve_arac_id("16 TIR 789", vehicles) == 3

    def test_resolve_arac_id_not_found(self, service, sample_data):
        from app.core.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            service._resolve_arac_id("00 ZZZ 000", sample_data["vehicles"])

    def test_resolve_sofor_id_variants(self, service, sample_data):
        drivers = sample_data["drivers"]
        assert service._resolve_sofor_id("Ahmet Yılmaz", drivers) == 1
        assert service._resolve_sofor_id("ahmet yılmaz", drivers) == 1

    def test_resolve_sofor_id_not_found(self, service, sample_data):
        from app.core.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            service._resolve_sofor_id("Bilinmeyen", sample_data["drivers"])

    def test_resolve_route_id_variants(self, service):
        from app.core.exceptions import ImportValidationError

        routes = [
            {"id": 9, "cikis_yeri": "Ankara", "varis_yeri": "Istanbul"},
            {"id": 10, "cikis_yeri": "Izmir", "varis_yeri": "Bursa"},
        ]

        assert service._resolve_route_id("ankara", "ISTANBUL", routes) == 9
        with pytest.raises(ImportValidationError):
            service._resolve_route_id("Ankara", "Antalya", routes)


class TestProcessImports:
    """Import flow tests for ImportService (Async)"""

    @pytest.fixture
    def service(self, monkeypatch):
        """ImportService + UoW patch'i (master listeleri artık uow.<repo>'dan)."""
        from app.tests._helpers.uow_mock import patch_unit_of_work

        mock_arac_repo = MagicMock()
        mock_sofor_repo = MagicMock()
        mock_sefer_service = MagicMock()
        mock_yakit_service = MagicMock()
        mock_arac_service = MagicMock()
        mock_sofor_service = MagicMock()
        mock_dorse_repo = MagicMock()
        mock_lokasyon_repo = MagicMock()

        # Singleton repo'lar artık master fetch için kullanılmıyor; bazı
        # process_*_import yolları (process_vehicle_import.update / reactivate)
        # hâlâ self.arac_repo'ya gidiyor — eski mock'ları orada koru.
        mock_arac_repo.get_all = AsyncMock(
            return_value=[
                {"id": 1, "plaka": "34 ABC 123", "marka": "Mercedes", "aktif": True}
            ]
        )
        mock_sofor_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "ad_soyad": "Ahmet Yilmaz"}]
        )
        mock_lokasyon_repo.get_all = AsyncMock(
            return_value=[{"id": 10, "cikis_yeri": "Ankara", "varis_yeri": "Istanbul"}]
        )
        mock_dorse_repo.get_all = AsyncMock(return_value=[])

        mock_sefer_service.bulk_add_sefer = AsyncMock(return_value=1)
        mock_yakit_service.bulk_add_yakit = AsyncMock(return_value=1)
        mock_arac_service.bulk_add_arac = AsyncMock(return_value=1)
        mock_sofor_service.bulk_add_sofor = AsyncMock(return_value=1)

        # UoW patch — master fetch artık `async with UnitOfWork() as uow:`
        # içinden uow.arac_repo / sofor_repo / dorse_repo / lokasyon_repo
        patch_unit_of_work(
            monkeypatch,
            "app.core.services.import_service",
            arac_repo_get_all=[
                {"id": 1, "plaka": "34 ABC 123", "marka": "Mercedes", "aktif": True}
            ],
            sofor_repo_get_all=[{"id": 1, "ad_soyad": "Ahmet Yilmaz"}],
            dorse_repo_get_all=[],
            lokasyon_repo_get_all=[
                {"id": 10, "cikis_yeri": "Ankara", "varis_yeri": "Istanbul"}
            ],
        )

        return ImportService(
            arac_repo=mock_arac_repo,
            sofor_repo=mock_sofor_repo,
            sefer_service=mock_sefer_service,
            yakit_service=mock_yakit_service,
            arac_service=mock_arac_service,
            sofor_service=mock_sofor_service,
            dorse_repo=mock_dorse_repo,
            lokasyon_repo=mock_lokasyon_repo,
        )

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_sefer_import_valid(self, MockExcelService, service):
        MockExcelService.parse_sefer_excel = AsyncMock(
            return_value=[
                {
                    "plaka": "34 ABC 123",
                    "sofor_adi": "Ahmet Yılmaz",
                    "tarih": date.today(),
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "İstanbul",
                    "mesafe_km": 450,
                    "net_kg": 20000,
                }
            ]
        )
        count, errors = await service.process_sefer_import(b"fake")
        assert count == 1
        assert len(errors) == 0
        payload = service.sefer_service.bulk_add_sefer.await_args.args[0][0]
        assert payload["sofor_id"] == 1
        assert payload["guzergah_id"] == 10
        assert payload["net_kg"] == 20000

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_yakit_import_valid(self, MockExcelService, service):
        MockExcelService.parse_yakit_excel = AsyncMock(
            return_value=[
                {
                    "plaka": "34 ABC 123",
                    "tarih": date.today(),
                    "istasyon": "Shell",
                    "litre": 500,
                    "fiyat_tl": 45.0,
                    "km_sayac": 150000,
                }
            ]
        )
        count, errors = await service.process_yakit_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_vehicle_import_valid(self, MockExcelService, service):
        MockExcelService.parse_vehicle_data = AsyncMock(
            return_value=[
                {
                    "plaka": "34 ADM 001",
                    "marka": "Mercedes",
                    "model": "Actros",
                    "yil": 2022,
                }
            ]
        )
        # Non-existing in DB
        service.arac_repo.get_all = AsyncMock(return_value=[])
        service.arac_service.bulk_add_arac = AsyncMock(return_value=1)

        count, errors = await service.process_vehicle_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_vehicle_import_reactivate(
        self, MockExcelService, service, monkeypatch
    ):
        """Pasif araç + Excel'de plaka → reactivate path.

        process_vehicle_import master listeyi UoW'tan çekiyor; reactivate
        çağrısı uow.arac_repo.update üzerinde olmalı. Test fixture'ın master
        listesini override etmek için UoW'u yeniden patch'le.
        """
        from app.tests._helpers.uow_mock import (
            _make_repo_mock,
            patch_unit_of_work,
        )

        MockExcelService.parse_vehicle_data = AsyncMock(
            return_value=[
                {"plaka": "34 ABC 123", "marka": "Mercedes", "model": "Actros"}
            ]
        )
        # Pasif araç içeren özel arac_repo mock — update'i de izle
        arac_repo_mock = _make_repo_mock(
            get_all=[{"id": 1, "plaka": "34 ABC 123", "aktif": False}]
        )
        arac_repo_mock.update = AsyncMock()
        patch_unit_of_work(
            monkeypatch,
            "app.core.services.import_service",
            arac_repo=arac_repo_mock,
        )
        service._arac_service = AsyncMock()
        service._arac_service.bulk_add_arac = AsyncMock(return_value=0)

        count, errors = await service.process_vehicle_import(b"fake")
        assert any("aktifleştirildi" in error for error in errors)
        arac_repo_mock.update.assert_called_once()
        assert count == 0

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_driver_import_valid(self, MockExcelService, service):
        MockExcelService.parse_driver_data = AsyncMock(
            return_value=[{"ad_soyad": "Yeni Sofor", "telefon": "5551112233"}]
        )
        service.sofor_repo.get_all = AsyncMock(return_value=[])
        service.sofor_service.bulk_add_sofor = AsyncMock(return_value=1)

        count, errors = await service.process_driver_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_import_routes_valid(self, MockExcelService, service, monkeypatch):
        """import_routes artık LokasyonService.add_lokasyon kullanıyor
        (eski RouteService.create_guzergah yoktu, runtime AttributeError'a
        yol açıyordu). Test buna göre patch'lenir."""
        MockExcelService.parse_route_excel = AsyncMock(
            return_value=[
                {"cikis_yeri": "Istanbul", "varis_yeri": "Ankara", "mesafe_km": 450.0}
            ]
        )
        fake_service = AsyncMock()
        fake_service.add_lokasyon = AsyncMock(return_value=1)

        # import_routes içinde "from app.core.services.lokasyon_service
        # import LokasyonService" lazy yapılıyor; patch'in module-of-record'i
        # tanımlı olduğu yerdir.
        monkeypatch.setattr(
            "app.core.services.lokasyon_service.LokasyonService",
            lambda **_: fake_service,
        )

        count, errors = await service.import_routes(b"fake")
        assert count == 1, f"errors={errors}"
        assert len(errors) == 0
        fake_service.add_lokasyon.assert_called_once()

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_import_routes_empty(self, MockExcelService, service):
        """Test with empty route excel"""
        MockExcelService.parse_route_excel = AsyncMock(return_value=[])
        count, errors = await service.import_routes(b"fake")
        assert count == 0
        assert "boş" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_sefer_import_empty(self, MockExcelService, service):
        """Test with empty trip excel"""
        MockExcelService.parse_sefer_excel = AsyncMock(return_value=[])
        count, errors = await service.process_sefer_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_yakit_import_empty(self, MockExcelService, service):
        """Test with empty fuel excel"""
        MockExcelService.parse_yakit_excel = AsyncMock(return_value=[])
        count, errors = await service.process_yakit_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_sefer_import_error(self, MockExcelService, service):
        """Test system error during import"""
        MockExcelService.parse_sefer_excel.side_effect = Exception("Excel error")
        count, errors = await service.process_sefer_import(b"fake")
        assert count == 0
        assert "Sistem hatası" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    @pytest.mark.asyncio
    async def test_process_sefer_import_requires_driver_resolution(
        self, MockExcelService, service
    ):
        MockExcelService.parse_sefer_excel = AsyncMock(
            return_value=[
                {
                    "plaka": "34 ABC 123",
                    "sofor_adi": "Eksik Sofor",
                    "tarih": date.today(),
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "İstanbul",
                    "mesafe_km": 450,
                    "net_kg": 20000,
                }
            ]
        )
        service.sofor_repo.get_all = AsyncMock(return_value=[])

        count, errors = await service.process_sefer_import(b"fake")

        assert count == 0
        assert errors
        assert errors[0]["field"] == "sofor_adi"
        service.sefer_service.bulk_add_sefer.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_import_sefer_resolves_driver_and_route_ids(self, service):
        upload = SimpleNamespace(
            filename="trips.xlsx",
            read=AsyncMock(return_value=b"fake-excel"),
        )
        df = pd.DataFrame(
            [
                {
                    "plaka": "34 ABC 123",
                    "sofor_ad": "Ahmet Yılmaz",
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "İstanbul",
                    "tarih": date.today(),
                    "mesafe_km": 450,
                    "ton": 20000,
                }
            ]
        )
        executed = []

        class FakeImportRepo:
            async def create_import_job(self, job_data):
                return SimpleNamespace(id=99, **job_data)

            async def update_job_status(self, *args, **kwargs):
                return None

        class FakeSession:
            async def execute(self, stmt, params=None):
                executed.append({"stmt": str(stmt), "params": params})
                return SimpleNamespace(scalar=lambda: 321)

            async def flush(self):
                """Flush pending changes to database."""
                return None

        class FakeUoW:
            def __init__(self):
                self.import_repo = FakeImportRepo()
                self.session = FakeSession()
                # Master listeleri pre-fetch artık UoW içinde — execute_import
                # `aktarim_tipi=="sefer"` branch'inde uow.<repo>.get_all() çağırır.
                # Master listeler test'in dataframe'i ile uyumlu olmalı.
                self.arac_repo = AsyncMock()
                self.arac_repo.get_all = AsyncMock(
                    return_value=[{"id": 1, "plaka": "34 ABC 123"}]
                )
                self.sofor_repo = AsyncMock()
                self.sofor_repo.get_all = AsyncMock(
                    return_value=[{"id": 1, "ad_soyad": "Ahmet Yılmaz"}]
                )
                self.dorse_repo = AsyncMock()
                self.dorse_repo.get_all = AsyncMock(return_value=[])
                self.lokasyon_repo = AsyncMock()
                self.lokasyon_repo.get_all = AsyncMock(
                    return_value=[
                        {"id": 10, "cikis_yeri": "Ankara", "varis_yeri": "İstanbul"}
                    ]
                )

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def commit(self):
                return None

        with (
            patch("app.core.services.import_service.pd.read_excel", return_value=df),
            patch(
                "app.core.services.import_service.UnitOfWork", return_value=FakeUoW()
            ),
            patch(
                "app.infrastructure.events.event_bus.get_event_bus",
                return_value=SimpleNamespace(publish_async=AsyncMock()),
            ),
        ):
            result = await service.execute_import(
                upload,
                "sefer",
                7,
                {
                    "plaka": "plaka",
                    "sofor_ad": "sofor_ad",
                    "cikis_yeri": "cikis_yeri",
                    "varis_yeri": "varis_yeri",
                    "tarih": "tarih",
                    "mesafe_km": "mesafe_km",
                    "ton": "ton",
                },
            )

        assert result["basarili"] == 1
        insert_call = next(
            call for call in executed if "INSERT INTO seferler" in call["stmt"]
        )
        params = insert_call["params"]
        assert params["sofor_id"] == 1
        assert params["guzergah_id"] == 10
        assert params["net_kg"] == 20000
        assert params["bos_agirlik_kg"] == 0
        assert params["dolu_agirlik_kg"] == 20000
        assert params["cikis_yeri"] == "Ankara"
        assert params["varis_yeri"] == "İstanbul"


class TestImportValidation:
    @pytest.fixture
    def service(self):
        return ImportService(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
        )

    def test_validate_plaka(self, service):
        from app.core.exceptions import ImportValidationError

        assert service._validate_plaka("34 abc 123") == "34ABC123"
        with pytest.raises(ImportValidationError, match="boş olamaz"):
            service._validate_plaka("")
        with pytest.raises(ImportValidationError, match="uzunluğu"):
            service._validate_plaka("A")
        with pytest.raises(ImportValidationError, match="formatı"):
            service._validate_plaka("ABCDEFG")

    def test_validate_name(self, service):
        from app.core.exceptions import ImportValidationError

        assert service._validate_name("ahmet yılmaz") == "Ahmet Yılmaz"
        with pytest.raises(ImportValidationError, match="en az 2"):
            service._validate_name("A")

    def test_validate_location(self, service):
        assert service._validate_location("İstanbul") == "İstanbul"

    def test_validate_numeric(self, service):
        from app.core.exceptions import ImportValidationError

        assert service._validate_numeric("123.4", "Test") == 123.4
        with pytest.raises(ImportValidationError, match="sayı olmalı"):
            service._validate_numeric("abc", "Test")


def test_get_import_service_singleton():
    from app.core.services.import_service import get_import_service

    with patch("app.core.container.get_container") as mock_cont:
        mock_instance = MagicMock()
        mock_cont.return_value.import_service = mock_instance
        svc = get_import_service()
        assert svc == mock_instance
