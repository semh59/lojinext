"""Unit Tests - ImportService

De-mock (0-mock epic son halka): master listeleri (arac/sofor/dorse/lokasyon)
artık GERÇEK DB'den çekiliyor. ``execute_import`` / ``process_*_import``
kendi ``async with UnitOfWork()`` içinde ``uow.<repo>.get_all(...)`` çağırır;
testler gerçek satır seed eder, gerçek repo sorgusu + raw INSERT koşar.

Sınırlar (dürüstçe mock kalan): ``bulk_add_*`` (ayrı domain service'leri —
kendi testleri var; burada forward edilen payload yakalanır), Excel parse
(``ExcelService`` / ``pd.read_excel`` — xlsx ayrıştırma ayrı birim) ve
``execute_import`` içindeki event bus publish (Redis pub/sub dış sınır).
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import select

from app.core.services.import_service import ImportService
from app.database.models import Arac, Sefer
from app.tests._helpers.seed import (
    seed_arac,
    seed_kullanici,
    seed_lokasyon,
    seed_sofor,
)


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
    """Import flow tests for ImportService (Async) — real DB master data."""

    @pytest.fixture
    async def service(self, db_session):
        """ImportService + GERÇEK master satırları (arac/sofor/lokasyon).

        bulk_add_* domain service'leri AsyncMock olarak kalır (ayrı sınır;
        await_args ile forward edilen payload yakalanır). Master listeleri
        ``process_*`` / ``execute_import`` içindeki gerçek UoW'tan gelir.
        """
        arac = await seed_arac(
            db_session, plaka="34ABC123", marka="Mercedes", bos_agirlik_kg=0
        )
        sofor = await seed_sofor(db_session, ad_soyad="Ahmet Yılmaz")
        lok = await seed_lokasyon(
            db_session, cikis_yeri="Ankara", varis_yeri="İstanbul"
        )
        user = await seed_kullanici(db_session)
        await db_session.commit()

        svc = ImportService(
            arac_repo=AsyncMock(),
            sofor_repo=AsyncMock(),
            sefer_service=AsyncMock(),
            yakit_service=AsyncMock(),
            arac_service=AsyncMock(),
            sofor_service=AsyncMock(),
            dorse_repo=AsyncMock(),
            lokasyon_repo=AsyncMock(),
        )
        svc.sefer_service.bulk_add_sefer = AsyncMock(return_value=1)
        svc.yakit_service.bulk_add_yakit = AsyncMock(return_value=1)
        svc.arac_service.bulk_add_arac = AsyncMock(return_value=1)
        svc.sofor_service.bulk_add_sofor = AsyncMock(return_value=1)
        # Expose seeded rows + session for assertions.
        svc._seeded = SimpleNamespace(
            arac=arac, sofor=sofor, lok=lok, user=user, db=db_session
        )
        return svc

    @patch("app.core.services.import_service.ExcelService")
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
        assert payload["sofor_id"] == service._seeded.sofor.id
        assert payload["guzergah_id"] == service._seeded.lok.id
        assert payload["net_kg"] == 20000

    @patch("app.core.services.import_service.ExcelService")
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
    async def test_process_vehicle_import_valid(self, MockExcelService, service):
        MockExcelService.parse_vehicle_data = AsyncMock(
            return_value=[
                {
                    "plaka": "34 ADM 001",  # seeded değil → yeni araç
                    "marka": "Mercedes",
                    "model": "Actros",
                    "yil": 2022,
                }
            ]
        )
        count, errors = await service.process_vehicle_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch("app.core.services.import_service.ExcelService")
    async def test_process_vehicle_import_reactivate(self, MockExcelService, service):
        """Pasif araç + Excel'de plaka → reactivate path (gerçek DB update)."""
        db = service._seeded.db
        passive = await seed_arac(db, plaka="34RCT001", marka="Mercedes", aktif=False)
        await db.commit()

        MockExcelService.parse_vehicle_data = AsyncMock(
            return_value=[
                {"plaka": "34 RCT 001", "marka": "Mercedes", "model": "Actros"}
            ]
        )

        count, errors = await service.process_vehicle_import(b"fake")

        assert any("aktifleştirildi" in error for error in errors)
        assert count == 0
        # Gerçek DB'de araç yeniden aktifleşti.
        db.expire_all()
        refreshed = (
            await db.execute(select(Arac.aktif).where(Arac.id == passive.id))
        ).scalar_one()
        assert refreshed is True

    @patch("app.core.services.import_service.ExcelService")
    async def test_process_driver_import_valid(self, MockExcelService, service):
        MockExcelService.parse_driver_data = AsyncMock(
            return_value=[{"ad_soyad": "Yeni Sofor", "telefon": "5551112233"}]
        )
        count, errors = await service.process_driver_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch("app.core.services.import_service.ExcelService")
    async def test_import_routes_valid(self, MockExcelService, service, monkeypatch):
        """import_routes → LokasyonService.add_lokasyon (ayrı service sınırı)."""
        MockExcelService.parse_route_excel = AsyncMock(
            return_value=[
                {"cikis_yeri": "Istanbul", "varis_yeri": "Ankara", "mesafe_km": 450.0}
            ]
        )
        fake_service = AsyncMock()
        fake_service.add_lokasyon = AsyncMock(return_value=1)
        monkeypatch.setattr(
            "app.core.services.lokasyon_service.LokasyonService",
            lambda **_: fake_service,
        )

        count, errors = await service.import_routes(b"fake")
        assert count == 1, f"errors={errors}"
        assert len(errors) == 0
        fake_service.add_lokasyon.assert_called_once()

    @patch("app.core.services.import_service.ExcelService")
    async def test_import_routes_empty(self, MockExcelService, service):
        """Test with empty route excel"""
        MockExcelService.parse_route_excel = AsyncMock(return_value=[])
        count, errors = await service.import_routes(b"fake")
        assert count == 0
        assert "boş" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    async def test_process_sefer_import_empty(self, MockExcelService, service):
        """Test with empty trip excel"""
        MockExcelService.parse_sefer_excel = AsyncMock(return_value=[])
        count, errors = await service.process_sefer_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    async def test_process_yakit_import_empty(self, MockExcelService, service):
        """Test with empty fuel excel"""
        MockExcelService.parse_yakit_excel = AsyncMock(return_value=[])
        count, errors = await service.process_yakit_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    async def test_process_sefer_import_error(self, MockExcelService, service):
        """Test system error during import"""
        MockExcelService.parse_sefer_excel.side_effect = Exception("Excel error")
        count, errors = await service.process_sefer_import(b"fake")
        assert count == 0
        assert "Sistem hatası" in errors[0]

    @patch("app.core.services.import_service.ExcelService")
    async def test_process_sefer_import_requires_driver_resolution(
        self, MockExcelService, service
    ):
        """Çözülemeyen şoför → satır hatası, bulk_add çağrılmaz."""
        MockExcelService.parse_sefer_excel = AsyncMock(
            return_value=[
                {
                    "plaka": "34 ABC 123",
                    "sofor_adi": "Eksik Sofor",  # seeded değil
                    "tarih": date.today(),
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "İstanbul",
                    "mesafe_km": 450,
                    "net_kg": 20000,
                }
            ]
        )

        count, errors = await service.process_sefer_import(b"fake")

        assert count == 0
        assert errors
        assert errors[0]["field"] == "sofor_adi"
        service.sefer_service.bulk_add_sefer.assert_not_called()

    async def test_execute_import_sefer_resolves_driver_and_route_ids(self, service):
        """execute_import sefer yolu: gerçek master + gerçek INSERT INTO seferler."""
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

        with (
            patch("app.core.services.import_service.pd.read_excel", return_value=df),
            patch(
                "app.infrastructure.events.event_bus.get_event_bus",
                return_value=SimpleNamespace(publish_async=AsyncMock()),
            ),
        ):
            result = await service.execute_import(
                upload,
                "sefer",
                service._seeded.user.id,
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
        # Gerçek seferler satırı yazıldı — çözülen FK'lar gerçek master id'leri.
        db = service._seeded.db
        db.expire_all()
        sefer = (
            await db.execute(
                select(Sefer).where(Sefer.sofor_id == service._seeded.sofor.id)
            )
        ).scalar_one()
        assert sefer.arac_id == service._seeded.arac.id
        assert sefer.guzergah_id == service._seeded.lok.id
        assert sefer.net_kg == 20000
        assert sefer.bos_agirlik_kg == 0
        assert sefer.dolu_agirlik_kg == 20000
        assert sefer.cikis_yeri == "Ankara"
        assert sefer.varis_yeri == "İstanbul"


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
