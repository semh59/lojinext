"""Unit Tests - import_excel modülü (execute_import/process_*_import free function'ları)

De-mock (0-mock epic son halka): master listeleri (arac/sofor/dorse/lokasyon)
artık GERÇEK DB'den çekiliyor. ``execute_import`` / ``process_*_import``
kendi ``async with UnitOfWork()`` içinde ``uow.<repo>.get_all(...)`` çağırır;
testler gerçek satır seed eder, gerçek repo sorgusu + raw INSERT koşar.

Sınırlar (dürüstçe mock kalan): ``bulk_add_*`` (ayrı domain modüllerinin
free function'ları — kendi testleri var; burada forward edilen payload
yakalanır), Excel parse (``infrastructure/parsers.py`` — xlsx ayrıştırma
ayrı birim) ve ``execute_import`` içindeki event bus publish (Redis pub/sub
dış sınır).

B.1 free-function geçişi (dalga 9): ``ImportService`` sınıfı kaldırıldı —
her use-case bağımsız fonksiyon. Patch hedefi HER ZAMAN tüketen modül
(`v2.modules.import_excel.application.<importer>.<fn>`) — kaynak modül
değil (location/fleet/driver/fuel'deki aynı gotcha).
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import select

from app.database.models import Arac, Sefer
from app.tests._helpers.seed import (
    seed_arac,
    seed_kullanici,
    seed_lokasyon,
    seed_sofor,
)
from v2.modules.import_excel.application.execute_import import execute_import
from v2.modules.import_excel.application.route_importer import import_routes
from v2.modules.import_excel.application.sefer_importer import process_sefer_import
from v2.modules.import_excel.application.vehicle_importer import (
    process_vehicle_import,
)
from v2.modules.import_excel.application.yakit_importer import process_yakit_import
from v2.modules.import_excel.domain.entity_resolvers import (
    resolve_arac_id,
    resolve_route_id,
    resolve_sofor_id,
)
from v2.modules.import_excel.domain.field_validators import (
    validate_name,
    validate_numeric,
    validate_plaka,
)

pytestmark = pytest.mark.integration


class TestResolveIds:
    """ID resolution tests (Plaka and Name matching) — free functions."""

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

    def test_resolve_arac_id_variants(self, sample_data):
        vehicles = sample_data["vehicles"]
        assert resolve_arac_id("34 ABC 123", vehicles) == 1
        assert resolve_arac_id("34ABC123", vehicles) == 1
        assert resolve_arac_id("34  abc   123", vehicles) == 1
        assert resolve_arac_id("16 TIR 789", vehicles) == 3

    def test_resolve_arac_id_not_found(self, sample_data):
        from app.core.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            resolve_arac_id("00 ZZZ 000", sample_data["vehicles"])

    def test_resolve_sofor_id_variants(self, sample_data):
        drivers = sample_data["drivers"]
        assert resolve_sofor_id("Ahmet Yılmaz", drivers) == 1
        assert resolve_sofor_id("ahmet yılmaz", drivers) == 1

    def test_resolve_sofor_id_not_found(self, sample_data):
        from app.core.exceptions import ImportValidationError

        with pytest.raises(ImportValidationError):
            resolve_sofor_id("Bilinmeyen", sample_data["drivers"])

    def test_resolve_route_id_variants(self):
        from app.core.exceptions import ImportValidationError

        routes = [
            {"id": 9, "cikis_yeri": "Ankara", "varis_yeri": "Istanbul"},
            {"id": 10, "cikis_yeri": "Izmir", "varis_yeri": "Bursa"},
        ]

        assert resolve_route_id("ankara", "ISTANBUL", routes) == 9
        with pytest.raises(ImportValidationError):
            resolve_route_id("Ankara", "Antalya", routes)


class TestProcessImports:
    """Import flow tests (Async) — real DB master data."""

    @pytest.fixture
    async def seeded(self, db_session, monkeypatch):
        """GERÇEK master satırları (arac/sofor/lokasyon) + mock'lanan
        bulk_add_* / container.sefer_service.

        ``bulk_add_vehicles``/``bulk_add_yakit``/``bulk_add_sofor`` birer
        free function — ilgili importer bunları inline import ile çağırır,
        bu yüzden patch hedefi KAYNAK modül (location/CLAUDE.md inline-import
        gotcha'sı) — ``bulk_add_vehicles`` için hâlâ
        ``v2.modules.fleet.application.bulk_add_vehicles`` (fleet henüz bu
        importer'ı public.py'ye yönlendirmedi); ``bulk_add_yakit``/
        ``bulk_add_sofor`` için artık "kaynak" `public.py`'nin kendisi
        (2026-07-17 dedektif denetimi düzeltmesi — importer'lar artık
        `fuel.public`/`driver.public` üzerinden geçiyor). ``sefer_service.
        bulk_add_sefer`` container üzerinden çağrılıyor (trip henüz
        taşınmadı) — container.sefer_service patch'lenir.
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

        mock_sefer_service = AsyncMock()
        mock_sefer_service.bulk_add_sefer = AsyncMock(return_value=1)
        mock_container = MagicMock()
        mock_container.sefer_service = mock_sefer_service
        monkeypatch.setattr("app.core.container.get_container", lambda: mock_container)
        monkeypatch.setattr(
            "v2.modules.fleet.application.bulk_add_vehicles.bulk_add_vehicles",
            AsyncMock(return_value=1),
        )
        monkeypatch.setattr(
            "v2.modules.fuel.public.bulk_add_yakit",
            AsyncMock(return_value=1),
        )
        monkeypatch.setattr(
            "v2.modules.driver.public.bulk_add_sofor",
            AsyncMock(return_value=1),
        )
        return SimpleNamespace(
            arac=arac,
            sofor=sofor,
            lok=lok,
            user=user,
            db=db_session,
            sefer_service=mock_sefer_service,
        )

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_process_sefer_import_valid(self, mock_parse, seeded):
        mock_parse.return_value = [
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
        count, errors = await process_sefer_import(b"fake")
        assert count == 1
        assert len(errors) == 0
        payload = seeded.sefer_service.bulk_add_sefer.await_args.args[0][0]
        assert payload["sofor_id"] == seeded.sofor.id
        assert payload["guzergah_id"] == seeded.lok.id
        assert payload["net_kg"] == 20000

    @patch(
        "v2.modules.import_excel.application.yakit_importer.parse_yakit_excel",
        new_callable=AsyncMock,
    )
    async def test_process_yakit_import_valid(self, mock_parse, seeded):
        mock_parse.return_value = [
            {
                "plaka": "34 ABC 123",
                "tarih": date.today(),
                "istasyon": "Shell",
                "litre": 500,
                "fiyat_tl": 45.0,
                "km_sayac": 150000,
            }
        ]
        count, errors = await process_yakit_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch(
        "v2.modules.import_excel.application.vehicle_importer.parse_vehicle_excel",
        new_callable=AsyncMock,
    )
    async def test_process_vehicle_import_valid(self, mock_parse, seeded):
        mock_parse.return_value = [
            {
                "plaka": "34 ADM 001",  # seeded değil → yeni araç
                "marka": "Mercedes",
                "model": "Actros",
                "yil": 2022,
            }
        ]
        count, errors = await process_vehicle_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch(
        "v2.modules.import_excel.application.vehicle_importer.parse_vehicle_excel",
        new_callable=AsyncMock,
    )
    async def test_process_vehicle_import_reactivate(self, mock_parse, seeded):
        """Pasif araç + Excel'de plaka → reactivate path (gerçek DB update)."""
        db = seeded.db
        passive = await seed_arac(db, plaka="34RCT001", marka="Mercedes", aktif=False)
        await db.commit()

        mock_parse.return_value = [
            {"plaka": "34 RCT 001", "marka": "Mercedes", "model": "Actros"}
        ]

        count, errors = await process_vehicle_import(b"fake")

        assert any("aktifleştirildi" in error for error in errors)
        assert count == 0
        # Gerçek DB'de araç yeniden aktifleşti.
        db.expire_all()
        refreshed = (
            await db.execute(select(Arac.aktif).where(Arac.id == passive.id))
        ).scalar_one()
        assert refreshed is True

    @patch(
        "v2.modules.import_excel.application.driver_importer.parse_driver_excel",
        new_callable=AsyncMock,
    )
    async def test_process_driver_import_valid(self, mock_parse, seeded):
        mock_parse.return_value = [{"ad_soyad": "Yeni Sofor", "telefon": "5551112233"}]
        from v2.modules.import_excel.application.driver_importer import (
            process_driver_import,
        )

        count, errors = await process_driver_import(b"fake")
        assert count == 1
        assert len(errors) == 0

    @patch(
        "v2.modules.import_excel.application.route_importer.parse_route_excel",
        new_callable=AsyncMock,
    )
    async def test_import_routes_valid(self, mock_parse, seeded, monkeypatch):
        """import_routes → v2 create_location (ayrı use-case sınırı)."""
        mock_parse.return_value = [
            {"cikis_yeri": "Istanbul", "varis_yeri": "Ankara", "mesafe_km": 450.0}
        ]
        fake_create_location = AsyncMock(return_value=1)
        monkeypatch.setattr(
            "v2.modules.location.public.create_location",
            fake_create_location,
        )

        count, errors = await import_routes(b"fake")
        assert count == 1, f"errors={errors}"
        assert len(errors) == 0
        fake_create_location.assert_called_once()

    @patch(
        "v2.modules.import_excel.application.route_importer.parse_route_excel",
        new_callable=AsyncMock,
    )
    async def test_import_routes_avoids_n_plus_one(
        self, mock_parse, seeded, monkeypatch
    ):
        """Sentry LOJINEXT-17A: bulk import must not issue one get_by_route
        SELECT per row. get_all_route_keys is called exactly once regardless
        of row count, and the per-row get_by_route path is never hit."""
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        mock_parse.return_value = [
            {"cikis_yeri": "Izmir", "varis_yeri": "Bursa", "mesafe_km": 320.0},
            {"cikis_yeri": "Adana", "varis_yeri": "Mersin", "mesafe_km": 70.0},
            {
                "cikis_yeri": "Ankara",
                "varis_yeri": "İstanbul",
                "mesafe_km": 450.0,
            },  # duplicate of the seeded (active) route
        ]

        original_get_all = LokasyonRepository.get_all_route_keys
        original_get_by_route = LokasyonRepository.get_by_route
        calls = {"get_all_route_keys": 0, "get_by_route": 0}

        async def counted_get_all(self):
            calls["get_all_route_keys"] += 1
            return await original_get_all(self)

        async def counted_get_by_route(self, *args, **kwargs):
            calls["get_by_route"] += 1
            return await original_get_by_route(self, *args, **kwargs)

        monkeypatch.setattr(LokasyonRepository, "get_all_route_keys", counted_get_all)
        monkeypatch.setattr(LokasyonRepository, "get_by_route", counted_get_by_route)

        count, errors = await import_routes(b"fake")

        assert calls["get_all_route_keys"] == 1, (
            "route index must be preloaded once, not skipped/repeated"
        )
        assert calls["get_by_route"] == 0, (
            "bulk import must use the in-memory index, not a per-row SELECT"
        )
        assert count == 2, f"errors={errors}"
        assert len(errors) == 1
        assert "zaten" in errors[0] or "already" in errors[0].lower()

    @patch(
        "v2.modules.import_excel.application.route_importer.parse_route_excel",
        new_callable=AsyncMock,
    )
    async def test_import_routes_empty(self, mock_parse, seeded):
        """Test with empty route excel"""
        mock_parse.return_value = []
        count, errors = await import_routes(b"fake")
        assert count == 0
        assert "boş" in errors[0]

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_process_sefer_import_empty(self, mock_parse, seeded):
        """Test with empty trip excel"""
        mock_parse.return_value = []
        count, errors = await process_sefer_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch(
        "v2.modules.import_excel.application.yakit_importer.parse_yakit_excel",
        new_callable=AsyncMock,
    )
    async def test_process_yakit_import_empty(self, mock_parse, seeded):
        """Test with empty fuel excel"""
        mock_parse.return_value = []
        count, errors = await process_yakit_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_process_sefer_import_error(self, mock_parse, seeded):
        """Test system error during import"""
        mock_parse.side_effect = Exception("Excel error")
        count, errors = await process_sefer_import(b"fake")
        assert count == 0
        assert "Sistem hatası" in errors[0]

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_process_sefer_import_infra_error_emits_monitoring_alarm(
        self, mock_parse, seeded
    ):
        """2026-07-02 prod-grade denetimi Tier B madde 13: dış (üst-seviye)
        catch, satır hatalarından farklı olarak DB-down gibi altyapı
        arızalarını sessizce "Sistem hatası" string'ine çeviriyordu ve hiçbir
        monitoring alarmı tetiklemiyordu (`aemit` hiç çağrılmıyordu). Artık
        `ErrorLayer.SERVICE` + `ErrorSeverity.CRITICAL` ile alarm emit
        ediliyor — dönüş sözleşmesi (count, errors) değişmedi."""
        mock_parse.side_effect = RuntimeError("DB down")

        with patch(
            "app.infrastructure.monitoring.aemit", new=AsyncMock()
        ) as mock_aemit:
            count, errors = await process_sefer_import(b"fake")

        assert count == 0
        assert "Sistem hatası" in errors[0]
        mock_aemit.assert_awaited_once()
        emitted_event = mock_aemit.await_args.args[0]
        assert emitted_event.layer.value == "service"
        assert emitted_event.severity.value == "critical"
        assert emitted_event.category == "import_unexpected_error"
        assert "process_sefer_import" in emitted_event.message

    @patch(
        "v2.modules.import_excel.application.yakit_importer.parse_yakit_excel",
        new_callable=AsyncMock,
    )
    async def test_process_yakit_import_infra_error_emits_monitoring_alarm(
        self, mock_parse, seeded
    ):
        """Aynı alarm kablolaması `process_yakit_import` için de geçerli
        olmalı — canlıda gerçekten çağrılan yol (fuel.py import endpoint)."""
        mock_parse.side_effect = RuntimeError("DB down")

        with patch(
            "app.infrastructure.monitoring.aemit", new=AsyncMock()
        ) as mock_aemit:
            count, errors = await process_yakit_import(b"fake")

        assert count == 0
        assert "Sistem hatası" in errors[0]
        mock_aemit.assert_awaited_once()
        emitted_event = mock_aemit.await_args.args[0]
        assert emitted_event.category == "import_unexpected_error"
        assert "process_yakit_import" in emitted_event.message

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_process_sefer_import_requires_driver_resolution(
        self, mock_parse, seeded
    ):
        """Çözülemeyen şoför → satır hatası, bulk_add çağrılmaz."""
        mock_parse.return_value = [
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

        count, errors = await process_sefer_import(b"fake")

        assert count == 0
        assert errors
        assert errors[0]["field"] == "sofor_adi"
        seeded.sefer_service.bulk_add_sefer.assert_not_called()

    async def test_execute_import_sefer_resolves_driver_and_route_ids(self, seeded):
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
            patch(
                "v2.modules.import_excel.application.preview_import.pd.read_excel",
                return_value=df,
            ),
            patch(
                "app.infrastructure.events.event_bus.get_event_bus",
                return_value=SimpleNamespace(publish_async=AsyncMock()),
            ),
        ):
            result = await execute_import(
                upload,
                "sefer",
                seeded.user.id,
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
        db = seeded.db
        db.expire_all()
        sefer = (
            await db.execute(select(Sefer).where(Sefer.sofor_id == seeded.sofor.id))
        ).scalar_one()
        assert sefer.arac_id == seeded.arac.id
        assert sefer.guzergah_id == seeded.lok.id
        assert sefer.net_kg == 20000
        assert sefer.bos_agirlik_kg == 0
        assert sefer.dolu_agirlik_kg == 20000
        assert sefer.cikis_yeri == "Ankara"
        assert sefer.varis_yeri == "İstanbul"


class TestImportValidation:
    def test_validate_plaka(self):
        from app.core.exceptions import ImportValidationError

        assert validate_plaka("34 abc 123") == "34ABC123"
        with pytest.raises(ImportValidationError, match="boş olamaz"):
            validate_plaka("")
        with pytest.raises(ImportValidationError, match="uzunluğu"):
            validate_plaka("A")
        with pytest.raises(ImportValidationError, match="formatı"):
            validate_plaka("ABCDEFG")

    def test_validate_plaka_matches_live_api_permissive_pattern(self):
        """2026-07-02 prod-grade denetimi P2 (Tier B madde 7): eskiden
        `_validate_plaka` (azami 3 harf, Türkçe karakter yok)
        `schemas/arac.py`'nin (azami 5 harf, Türkçe karakter var) canlı
        API'de zaten kabul ettiği plakaları reddediyordu — aynı plaka doğrudan
        POST /vehicles/ ile eklenebilirken Excel import'ta reddediliyordu.
        Artık ikisi de aynı paylaşılan pattern'i (`schemas.validators.PLAKA_PATTERN`)
        kullanıyor."""
        from app.core.exceptions import ImportValidationError

        # 4-5 harfli plaka — schemas/arac.py hep kabul ediyordu, import
        # eskiden reddediyordu (azami 3 harf sınırı).
        result = validate_plaka("34 ABCDE 12")  # pragma: allowlist secret
        assert result == "34ABCDE12"  # pragma: allowlist secret
        # Türkçe karakter içeren plaka — schemas/arac.py hep kabul ediyordu.
        assert validate_plaka("34 ÇAA 123") == "34ÇAA123"
        # Genuinely invalid (0 harf) hâlâ reddedilmeli.
        with pytest.raises(ImportValidationError, match="formatı"):
            validate_plaka("3400123")

    def test_validate_name(self):
        from app.core.exceptions import ImportValidationError

        assert validate_name("ahmet yılmaz") == "Ahmet Yılmaz"
        with pytest.raises(ImportValidationError, match="en az 2"):
            validate_name("A")

    def test_validate_numeric(self):
        from app.core.exceptions import ImportValidationError

        assert validate_numeric("123.4", "Test") == 123.4
        with pytest.raises(ImportValidationError, match="sayı olmalı"):
            validate_numeric("abc", "Test")
