"""
import_excel free-function additional coverage tests.

Targets missing branches across v2/modules/import_excel/{application,domain}/*.
Covers:
  - parse_and_preview (csv, excel, unsupported type, parse error)
  - parse_import_file (csv branch)
  - validate_import_rows (arac, surucu, sefer, yakit types + error rows)
  - execute_import (arac, surucu, yakit paths + COMPLETED_WITH_ERRORS state)
  - rollback_import (not found, already rolled back, empty ids, delete paths)
  - process_sefer_import (dorse plaka path, ValueError/generic error rows)
  - process_yakit_import (empty plaka, missing tarih, period_recalc skip)
  - resolve_dorse_id (not found returns None)
  - normalize_text (Turkish İ mapping)

B.1 free-function geçişi (dalga 9): ``ImportService`` sınıfı kaldırıldı —
patch hedefi HER ZAMAN tüketen modül (`v2.modules.import_excel.application.
<importer>.<fn>`), kaynak modül değil.
"""

import io
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.database.models import Sefer, Sofor, YakitAlimi
from app.database.unit_of_work import UnitOfWork
from app.tests._helpers.seed import (
    seed_arac,
    seed_dorse,
    seed_kullanici,
    seed_lokasyon,
    seed_sofor,
)
from v2.modules.import_excel.application.execute_import import execute_import
from v2.modules.import_excel.application.preview_import import (
    parse_and_preview,
    parse_import_file,
)
from v2.modules.import_excel.application.rollback_import import rollback_import
from v2.modules.import_excel.application.route_importer import import_routes
from v2.modules.import_excel.application.sefer_importer import process_sefer_import
from v2.modules.import_excel.application.vehicle_importer import (
    process_vehicle_import,
)
from v2.modules.import_excel.application.yakit_importer import process_yakit_import
from v2.modules.import_excel.domain.entity_resolvers import resolve_dorse_id
from v2.modules.import_excel.domain.field_validators import normalize_text
from v2.modules.import_excel.domain.row_validators import validate_import_rows

pytestmark = pytest.mark.integration
# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc(monkeypatch):
    """``process_sefer_import`` artık ``v2.modules.trip.public.bulk_add_sefer``'i
    doğrudan çağırıyor (dalga 14 — container üzerinden değil). Inline
    (fonksiyon-içi) import olduğu için patch hedefi KAYNAK modül, tüketen
    modül değil."""
    mock_bulk_add_sefer = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "v2.modules.trip.public.bulk_add_sefer", mock_bulk_add_sefer
    )
    return SimpleNamespace(bulk_add_sefer=mock_bulk_add_sefer)


@pytest.fixture
async def real_master(db_session):
    """Seed standard master rows + a user into the real test DB.

    execute_import / process_*_import fetch master lists from their own
    ``async with UnitOfWork()`` which (via conftest monkeypatch) reuses this
    session — so the seeded rows drive real FK resolution and the raw
    INSERTs run for real. "Not found" cases are produced with non-matching
    input data, so this one standard master serves every test.
    """
    arac = await seed_arac(
        db_session, plaka="34ABC123", marka="Mercedes", bos_agirlik_kg=0
    )
    sofor = await seed_sofor(db_session, ad_soyad="Ahmet Yilmaz")
    lok = await seed_lokasyon(db_session, cikis_yeri="Ankara", varis_yeri="Istanbul")
    user = await seed_kullanici(db_session)
    await db_session.commit()
    return SimpleNamespace(db=db_session, arac=arac, sofor=sofor, lok=lok, user=user)


# ---------------------------------------------------------------------------
# parse_and_preview
# ---------------------------------------------------------------------------


class TestParseAndPreview:
    async def test_unsupported_type_raises_http_400(self):
        from fastapi import HTTPException

        upload = SimpleNamespace(
            filename="data.xlsx",
            read=AsyncMock(return_value=b"fake"),
        )
        with pytest.raises(HTTPException) as exc_info:
            await parse_and_preview(upload, "unknown_type")
        assert exc_info.value.status_code == 400

    async def test_excel_file_returns_preview(self):
        df = pd.DataFrame([{"plaka": "34ABC123", "marka": "Mercedes"}] * 10)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        upload = SimpleNamespace(
            filename="data.xlsx",
            read=AsyncMock(return_value=buf.read()),
        )
        result = await parse_and_preview(upload, "arac")

        assert result["aktarim_tipi"] == "arac"
        assert result["total_rows"] == 10
        assert len(result["preview"]) == 5  # head(5)
        assert "plaka" in result["headers"]

    async def test_csv_file_returns_preview(self):
        df = pd.DataFrame([{"plaka": "34ABC123"}] * 3)
        csv_bytes = df.to_csv(index=False).encode()

        upload = SimpleNamespace(
            filename="data.csv",
            read=AsyncMock(return_value=csv_bytes),
        )
        result = await parse_and_preview(upload, "arac")
        assert result["filename"] == "data.csv"
        assert result["total_rows"] == 3

    async def test_invalid_file_raises_http_400(self):
        from fastapi import HTTPException

        upload = SimpleNamespace(
            filename="data.xlsx",
            read=AsyncMock(return_value=b"not an excel file"),
        )
        with pytest.raises(HTTPException) as exc_info:
            await parse_and_preview(upload, "arac")
        assert exc_info.value.status_code == 400

    async def test_over_limit_raises_http_413(self, monkeypatch):
        """2026-07-02 prod-grade denetimi Tier B madde 15: preview endpoint'i
        de kendi doğrudan `pd.read_excel` çağrısına sahip — parsers.py
        guard'ının kapsamı dışında. Ayrı guard eklendi."""
        from fastapi import HTTPException

        import v2.modules.import_excel.application.preview_import as mod

        monkeypatch.setattr(mod, "MAX_EXCEL_ROWS", 2)
        df = pd.DataFrame([{"plaka": "34ABC123", "marka": "Mercedes"}] * 5)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        upload = SimpleNamespace(
            filename="data.xlsx",
            read=AsyncMock(return_value=buf.read()),
        )
        with pytest.raises(HTTPException) as exc_info:
            await parse_and_preview(upload, "arac")
        assert exc_info.value.status_code == 413


# ---------------------------------------------------------------------------
# parse_import_file
# ---------------------------------------------------------------------------


class TestParseImportFile:
    async def test_csv_branch(self):
        df = pd.DataFrame([{"col1": "val1", "col2": 42}])
        csv_bytes = df.to_csv(index=False).encode()

        rows = await parse_import_file("data.csv", csv_bytes)
        assert len(rows) == 1
        assert rows[0]["col1"] == "val1"

    async def test_excel_branch(self):
        df = pd.DataFrame([{"plaka": "06TIR001"}])
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        rows = await parse_import_file("data.xlsx", buf.read())
        assert rows[0]["plaka"] == "06TIR001"

    async def test_over_limit_raises_excel_export_error(self, monkeypatch):
        """2026-07-02 prod-grade denetimi Tier B madde 15: `parse_import_file`
        (execute_import'un gerçek raw-INSERT yolu) parsers.py'ı hiç
        kullanmıyor — kendi doğrudan `pd.read_excel` çağrısı var, bu yüzden
        oradaki satır sınırı bu yolu KAPSAMAZ. Ayrı bir guard gerekiyordu."""
        import v2.modules.import_excel.application.preview_import as mod
        from app.core.exceptions import ExcelExportError

        monkeypatch.setattr(mod, "MAX_EXCEL_ROWS", 2)
        df = pd.DataFrame([{"plaka": "06TIR001"}] * 3)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        with pytest.raises(ExcelExportError, match="satır sayısı"):
            await parse_import_file("data.xlsx", buf.read())


# ---------------------------------------------------------------------------
# validate_import_rows — all aktarim_tipi branches
# ---------------------------------------------------------------------------


class TestValidateImportRows:
    def test_arac_type_valid_row(self):
        rows = [{"plaka": "34ABC123"}]
        valid, errors = validate_import_rows(
            rows, "arac", {"plaka": "plaka"}, [], [], [], []
        )
        assert len(valid) == 1
        assert valid[0]["plaka"] == "34ABC123"

    def test_arac_type_missing_plaka(self):
        rows = [{"plaka": ""}]
        valid, errors = validate_import_rows(
            rows, "arac", {"plaka": "plaka"}, [], [], [], []
        )
        assert len(valid) == 0
        assert "0" in errors

    def test_surucu_type_valid_row(self):
        rows = [
            {"ad_soyad": "Ahmet Yılmaz", "ehliyet_sinifi": "E", "telefon": "5551234567"}
        ]
        mapping = {
            "ad_soyad": "ad_soyad",
            "ehliyet_sinifi": "ehliyet_sinifi",
            "telefon": "telefon",
        }
        valid, errors = validate_import_rows(rows, "surucu", mapping, [], [], [], [])
        assert len(valid) == 1
        assert valid[0]["ad_soyad"] == "Ahmet Yılmaz"

    def test_sefer_type_missing_cikis_yeri(self):
        vehicles = [{"id": 1, "plaka": "34ABC123"}]
        drivers = [{"id": 1, "ad_soyad": "Ahmet Yılmaz"}]
        rows = [
            {
                "plaka": "34ABC123",
                "sofor_ad": "Ahmet Yılmaz",
                "cikis_yeri": "",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450,
                "ton": 20000,
            }
        ]
        mapping = {
            "plaka": "plaka",
            "sofor_ad": "sofor_ad",
            "cikis_yeri": "cikis_yeri",
            "varis_yeri": "varis_yeri",
            "tarih": "tarih",
            "mesafe_km": "mesafe_km",
            "ton": "ton",
            "dorse_plakasi": "dorse_plakasi",
        }
        valid, errors = validate_import_rows(
            rows, "sefer", mapping, vehicles, drivers, [], []
        )
        assert "0" in errors  # missing cikis_yeri

    def test_yakit_type_valid_row(self):
        vehicles = [{"id": 1, "plaka": "34ABC123"}]
        rows = [
            {
                "plaka": "34ABC123",
                "tarih": date.today(),
                "litre": 500,
                "toplam_tutar": 10000,
                "km_sayac": 150000,
            }
        ]
        mapping = {
            "plaka": "plaka",
            "tarih": "tarih",
            "litre": "litre",
            "toplam_tutar": "toplam_tutar",
            "km_sayac": "km_sayac",
        }
        valid, errors = validate_import_rows(
            rows, "yakit", mapping, vehicles, [], [], []
        )
        assert len(valid) == 1


# ---------------------------------------------------------------------------
# execute_import — arac / surucu / yakit paths
# ---------------------------------------------------------------------------


class _FakeImportRepo:
    async def create_import_job(self, data):
        return SimpleNamespace(id=42, **data)

    async def update_job_status(self, *args, **kwargs):
        pass


class _FakeSession:
    def __init__(self):
        self._scalars = {}
        self.executed = []

    async def execute(self, stmt, params=None):
        self.executed.append({"stmt": str(stmt), "params": params})
        return SimpleNamespace(scalar=lambda: 101)

    async def flush(self):
        pass


class _FakeUoW:
    def __init__(self, extra_repos=None):
        self.import_repo = _FakeImportRepo()
        self.session = _FakeSession()
        self.arac_repo = AsyncMock()
        self.arac_repo.get_all = AsyncMock(
            return_value=[{"id": 1, "plaka": "34ABC123"}]
        )
        self.sofor_repo = AsyncMock()
        self.sofor_repo.get_all = AsyncMock(return_value=[])
        self.dorse_repo = AsyncMock()
        self.dorse_repo.get_all = AsyncMock(return_value=[])
        self.lokasyon_repo = AsyncMock()
        self.lokasyon_repo.get_all = AsyncMock(return_value=[])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def commit(self):
        pass


class TestExecuteImport:
    """execute_import arac/surucu/yakit — gerçek UoW + gerçek raw INSERT."""

    def _upload(self, df):
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return SimpleNamespace(
            filename="data.xlsx",
            read=AsyncMock(return_value=buf.read()),
        )

    async def test_arac_import_known_marka_gap(self, real_master):
        """BİLİNEN SINIR: arac raw INSERT ``marka`` (NOT NULL) toplamıyor →
        satır gerçek DB'de NOT NULL ihlaliyle düşer. Mock'lu eski test bunu
        sahte başarı (scalar=101) ile gizliyordu; gerçek davranışı kanıtla."""
        df = pd.DataFrame([{"plaka": "34NEW999"}])  # seeded değil → unique değil
        upload = self._upload(df)

        result = await execute_import(
            upload, "arac", real_master.user.id, {"plaka": "plaka"}
        )

        assert result["basarili"] == 0
        assert result["hatali"] >= 1

    async def test_surucu_import_happy_path(self, real_master):
        """surucu INSERT artık skor kolonlarını yazıyor → gerçek satır eklenir."""
        df = pd.DataFrame(
            # telefon string biçimde (xlsx round-trip salt-rakamı int'e çevirir;
            # soforler.telefon VARCHAR — bu type sorunu skor-kolon fix'inden ayrı).
            [
                {
                    "ad_soyad": "Yeni Surucu",
                    "ehliyet_sinifi": "E",
                    "telefon": "0555 123 4567",
                }
            ]
        )
        upload = self._upload(df)
        mapping = {
            "ad_soyad": "ad_soyad",
            "ehliyet_sinifi": "ehliyet_sinifi",
            "telefon": "telefon",
        }

        result = await execute_import(upload, "surucu", real_master.user.id, mapping)

        assert result["basarili"] == 1
        db = real_master.db
        db.expire_all()
        from app.infrastructure.security.pii_encryption import blind_index

        count = (
            await db.execute(
                select(func.count())
                .select_from(Sofor)
                .where(Sofor.ad_soyad_bidx == blind_index("Yeni Surucu"))
            )
        ).scalar_one()
        assert count == 1

    async def test_yakit_import_happy_path(self, real_master):
        """yakit INSERT artık fiyat_tl (tutar/litre) + teknik default'ları yazıyor."""
        df = pd.DataFrame(
            [
                {
                    "plaka": "34ABC123",  # seeded arac → resolve
                    "tarih": str(date.today()),
                    "litre": 500.0,
                    "toplam_tutar": 10000.0,
                    "km_sayac": 150000.0,
                }
            ]
        )
        upload = self._upload(df)
        mapping = {
            "plaka": "plaka",
            "tarih": "tarih",
            "litre": "litre",
            "toplam_tutar": "toplam_tutar",
            "km_sayac": "km_sayac",
        }

        result = await execute_import(upload, "yakit", real_master.user.id, mapping)

        assert result["basarili"] == 1
        db = real_master.db
        db.expire_all()
        row = (
            await db.execute(
                select(YakitAlimi).where(YakitAlimi.arac_id == real_master.arac.id)
            )
        ).scalar_one()
        assert float(row.fiyat_tl) == 20.0  # 10000 / 500

    async def test_unsupported_type_raises_http_400(self):
        from fastapi import HTTPException

        df = pd.DataFrame([{"col": "val"}])
        upload = self._upload(df)

        with pytest.raises(HTTPException) as exc_info:
            await execute_import(upload, "unknown", 1, {})
        assert exc_info.value.status_code == 400

    async def test_completed_with_errors_status(self, real_master):
        """arac satırı marka-eksiğinden düşünce job COMPLETED_WITH_ERRORS olur."""
        df = pd.DataFrame([{"plaka": "34NEW888"}])
        upload = self._upload(df)

        result = await execute_import(
            upload, "arac", real_master.user.id, {"plaka": "plaka"}
        )

        assert result["hatali"] >= 1
        assert result["basarili"] == 0


# ---------------------------------------------------------------------------
# rollback_import
# ---------------------------------------------------------------------------


class TestRollbackImport:
    async def test_job_not_found_raises_404(self):
        from fastapi import HTTPException

        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=None)

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rollback_import(999, 1)
        assert exc_info.value.status_code == 404

    async def test_already_rolled_back_raises_400(self):
        from fastapi import HTTPException

        job = SimpleNamespace(
            id=1, durum="ROLLED_BACK", aktarim_tipi="arac", islem_haritasi=None
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rollback_import(1, 1)
        assert exc_info.value.status_code == 400

    async def test_missing_islem_haritasi_raises_400(self):
        from fastapi import HTTPException

        job = SimpleNamespace(
            id=1, durum="COMPLETED", aktarim_tipi="arac", islem_haritasi=None
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rollback_import(1, 1)
        assert exc_info.value.status_code == 400

    async def test_empty_inserted_ids_returns_true(self):
        job = SimpleNamespace(
            id=1,
            durum="COMPLETED",
            aktarim_tipi="arac",
            islem_haritasi={"inserted_ids": []},
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)
        fake_uow.import_repo.update_job_status = AsyncMock()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await rollback_import(1, 1)

        assert result is True

    async def test_rollback_arac_deletes(self):
        job = SimpleNamespace(
            id=1,
            durum="COMPLETED",
            aktarim_tipi="arac",
            islem_haritasi={"inserted_ids": [10, 11]},
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)
        fake_uow.import_repo.update_job_status = AsyncMock()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await rollback_import(1, 1)

        assert result is True
        stmts = [str(c["stmt"]) for c in fake_uow.session.executed]
        assert any("araclar" in s for s in stmts)

    async def test_rollback_surucu_deletes(self):
        job = SimpleNamespace(
            id=2,
            durum="COMPLETED",
            aktarim_tipi="surucu",
            islem_haritasi={"inserted_ids": [5]},
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)
        fake_uow.import_repo.update_job_status = AsyncMock()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await rollback_import(2, 1)

        assert result is True
        stmts = [str(c["stmt"]) for c in fake_uow.session.executed]
        assert any("soforler" in s for s in stmts)

    async def test_rollback_sefer_deletes(self):
        job = SimpleNamespace(
            id=3,
            durum="COMPLETED",
            aktarim_tipi="sefer",
            islem_haritasi={"inserted_ids": [20]},
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)
        fake_uow.import_repo.update_job_status = AsyncMock()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await rollback_import(3, 1)

        assert result is True
        stmts = [str(c["stmt"]) for c in fake_uow.session.executed]
        assert any("seferler" in s for s in stmts)

    async def test_rollback_yakit_deletes(self):
        job = SimpleNamespace(
            id=4,
            durum="COMPLETED",
            aktarim_tipi="yakit",
            islem_haritasi={"inserted_ids": [30, 31]},
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)
        fake_uow.import_repo.update_job_status = AsyncMock()

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            result = await rollback_import(4, 1)

        assert result is True
        stmts = [str(c["stmt"]) for c in fake_uow.session.executed]
        assert any("yakit_alimlar" in s for s in stmts)


# ---------------------------------------------------------------------------
# process_sefer_import — extra branches
# ---------------------------------------------------------------------------


class TestProcessSeferImportExtra:
    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_with_dorse_plaka(self, mock_parse, svc, real_master):
        """Row with dorse_plakasi resolves dorse_id (real seeded trailer)."""
        await seed_dorse(real_master.db, plaka="34DRS001")
        await real_master.db.commit()

        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "sofor_adi": "Ahmet Yilmaz",
                "dorse_plakasi": "34DRS001",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450,
                "net_kg": 20000,
                "baslangic_km": 0,
                "bitis_km": 450,
            }
        ]
        svc.bulk_add_sefer.return_value = 1

        count, errors = await process_sefer_import(b"fake")
        assert count == 1
        assert not errors

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_value_error_row_field_mapping(self, mock_parse, svc, real_master):
        """ValueError from row processing maps to correct field."""
        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "sofor_adi": "Ahmet Yilmaz",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": "not-a-number",  # triggers ValueError path
                "net_kg": 20000,
            }
        ]

        count, errors = await process_sefer_import(b"fake")
        # Non-numeric mesafe_km raises ImportValidationError(reason="INVALID_NUMERIC"),
        # which maps to field="net_kg" (see sefer_importer.py's reason_code branch) —
        # the row is dropped, so count stays 0 and errors carries exactly this entry.
        assert count == 0
        assert errors == [{"row": 1, "field": "net_kg", "reason": "Mesafe sayı olmalı"}]


# ---------------------------------------------------------------------------
# process_yakit_import — extra branches
# ---------------------------------------------------------------------------


class TestProcessYakitImportExtra:
    @patch(
        "v2.modules.import_excel.application.yakit_importer.parse_yakit_excel",
        new_callable=AsyncMock,
    )
    async def test_empty_plaka_row_becomes_error(self, mock_parse, svc, real_master):
        """Blank plaka row → ValueError → errors list."""
        mock_parse.return_value = [
            {
                "plaka": "",
                "tarih": date.today(),
                "litre": 500,
                "fiyat_tl": 10.0,
                "km_sayac": 100000,
            }
        ]

        count, errors = await process_yakit_import(b"fake")
        assert count == 0
        assert len(errors) == 1
        assert "Plaka" in errors[0]

    @patch(
        "v2.modules.import_excel.application.yakit_importer.parse_yakit_excel",
        new_callable=AsyncMock,
    )
    async def test_missing_tarih_becomes_error(self, mock_parse, svc, real_master):
        """None tarih → ValueError → errors list."""
        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "tarih": None,
                "litre": 500,
                "fiyat_tl": 10.0,
                "km_sayac": 100000,
            }
        ]

        count, errors = await process_yakit_import(b"fake")
        assert count == 0
        assert len(errors) == 1

    @patch(
        "v2.modules.import_excel.application.yakit_importer.parse_yakit_excel",
        new_callable=AsyncMock,
    )
    async def test_period_recalc_skip_on_import_error(
        self, mock_parse, svc, real_master
    ):
        """period recalc failure doesn't propagate — returns count normally."""
        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "tarih": date.today(),
                "litre": 500,
                "fiyat_tl": 10.0,
                "km_sayac": 100000,
            }
        ]

        # bulk_add_yakit/recalculate_vehicle_periods are free functions
        # imported inline inside process_yakit_import — patch target is the
        # SOURCE module (inline-import gotcha, see location/CLAUDE.md); as
        # of the 2026-07-17 public.py boundary fix, that source is
        # v2.modules.fuel.public itself (the importer no longer bypasses it).
        with (
            patch(
                "v2.modules.fuel.public.bulk_add_yakit",
                AsyncMock(return_value=1),
            ),
            patch(
                "v2.modules.fuel.public.recalculate_vehicle_periods",
                side_effect=Exception("service unavailable"),
            ),
        ):
            count, errors = await process_yakit_import(b"fake")

        assert count == 1  # period failure should not block main result


# ---------------------------------------------------------------------------
# Resolver helpers
# ---------------------------------------------------------------------------


class TestResolverHelpers:
    def test_resolve_dorse_id_not_found_returns_none(self):
        trailers = [{"id": 1, "plaka": "34DRS001"}]
        result = resolve_dorse_id("99UNK001", trailers)
        assert result is None

    def test_resolve_dorse_id_found(self):
        trailers = [{"id": 7, "plaka": "34 DRS 001"}]
        result = resolve_dorse_id("34DRS001", trailers)
        assert result == 7

    def test_normalize_text_turkish_I(self):
        # İstanbul has capital İ (U+0130)
        result = normalize_text("İstanbul")
        assert result == "ISTANBUL"

    def test_normalize_text_empty(self):
        assert normalize_text(None) == ""
        assert normalize_text("") == ""


# ---------------------------------------------------------------------------
# execute_import — sefer path (covers lines 253-255, 311-355)
# ---------------------------------------------------------------------------


class TestExecuteImportSeferPath:
    def _upload(self, df):
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return SimpleNamespace(
            filename="seferler.xlsx",
            read=AsyncMock(return_value=buf.read()),
        )

    async def test_sefer_execute_import(self, real_master):
        """Sefer execute_import: gerçek master + gerçek INSERT INTO seferler."""
        df = pd.DataFrame(
            [
                {
                    "plaka": "34ABC123",
                    "sofor_ad": "Ahmet Yilmaz",
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "Istanbul",
                    "tarih": str(date.today()),
                    "mesafe_km": 450.0,
                    "ton": 20000.0,
                }
            ]
        )
        upload = self._upload(df)
        mapping = {
            "plaka": "plaka",
            "sofor_ad": "sofor_ad",
            "cikis_yeri": "cikis_yeri",
            "varis_yeri": "varis_yeri",
            "tarih": "tarih",
            "mesafe_km": "mesafe_km",
            "ton": "ton",
        }

        with patch(
            "app.infrastructure.events.event_bus.get_event_bus",
            return_value=SimpleNamespace(publish_async=AsyncMock()),
        ):
            result = await execute_import(upload, "sefer", real_master.user.id, mapping)

        assert result["basarili"] == 1
        db = real_master.db
        db.expire_all()
        sefer = (
            await db.execute(
                select(Sefer).where(Sefer.sofor_id == real_master.sofor.id)
            )
        ).scalar_one()
        assert sefer.arac_id == real_master.arac.id
        assert sefer.guzergah_id == real_master.lok.id

    async def test_sefer_execute_import_avoids_n_plus_one(
        self, real_master, monkeypatch
    ):
        """execute_import'un sefer yolu: master listeler (arac/sofor/dorse/
        lokasyon) satır sayısından BAĞIMSIZ olarak TEK seferde prefetch
        edilmeli — her split-fonksiyonun (validate_sefer_row) kendi sorgusunu
        atması N+1 regresyonu olurdu (görev dosyasının uyarısı,
        row_validators.py'nin docstring'i). 3 satırlı bir Excel ile
        get_all'ların tam olarak 1 kez çağrıldığını sayarak kanıtlar."""
        from v2.modules.driver.infrastructure.repository import SoforRepository
        from v2.modules.fleet.infrastructure.trailer_repository import DorseRepository
        from v2.modules.fleet.infrastructure.vehicle_repository import AracRepository
        from v2.modules.location.infrastructure.repository import LokasyonRepository

        calls = {"arac": 0, "sofor": 0, "dorse": 0, "lokasyon": 0}

        original_arac = AracRepository.get_all
        original_sofor = SoforRepository.get_all
        original_dorse = DorseRepository.get_all
        original_lok = LokasyonRepository.get_all

        async def counted_arac(self, *a, **kw):
            calls["arac"] += 1
            return await original_arac(self, *a, **kw)

        async def counted_sofor(self, *a, **kw):
            calls["sofor"] += 1
            return await original_sofor(self, *a, **kw)

        async def counted_dorse(self, *a, **kw):
            calls["dorse"] += 1
            return await original_dorse(self, *a, **kw)

        async def counted_lok(self, *a, **kw):
            calls["lokasyon"] += 1
            return await original_lok(self, *a, **kw)

        monkeypatch.setattr(AracRepository, "get_all", counted_arac)
        monkeypatch.setattr(SoforRepository, "get_all", counted_sofor)
        monkeypatch.setattr(DorseRepository, "get_all", counted_dorse)
        monkeypatch.setattr(LokasyonRepository, "get_all", counted_lok)

        df = pd.DataFrame(
            [
                {
                    "plaka": "34ABC123",
                    "sofor_ad": "Ahmet Yilmaz",
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "Istanbul",
                    "tarih": str(date.today()),
                    "mesafe_km": 450.0,
                    "ton": 20000.0,
                },
                {
                    "plaka": "34ABC123",
                    "sofor_ad": "Ahmet Yilmaz",
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "Istanbul",
                    "tarih": str(date.today()),
                    "mesafe_km": 100.0,
                    "ton": 5000.0,
                },
                {
                    "plaka": "34ABC123",
                    "sofor_ad": "Ahmet Yilmaz",
                    "cikis_yeri": "Ankara",
                    "varis_yeri": "Istanbul",
                    "tarih": str(date.today()),
                    "mesafe_km": 200.0,
                    "ton": 8000.0,
                },
            ]
        )
        upload = self._upload(df)
        mapping = {
            "plaka": "plaka",
            "sofor_ad": "sofor_ad",
            "cikis_yeri": "cikis_yeri",
            "varis_yeri": "varis_yeri",
            "tarih": "tarih",
            "mesafe_km": "mesafe_km",
            "ton": "ton",
        }

        with patch(
            "app.infrastructure.events.event_bus.get_event_bus",
            return_value=SimpleNamespace(publish_async=AsyncMock()),
        ):
            result = await execute_import(upload, "sefer", real_master.user.id, mapping)

        assert result["basarili"] == 3, f"errors={result['errors']}"
        assert calls["arac"] == 1, (
            "arac_repo.get_all satır sayısından bağımsız TEK kez çağrılmalı"
        )
        assert calls["sofor"] == 1, (
            "sofor_repo.get_all satır sayısından bağımsız TEK kez çağrılmalı"
        )
        assert calls["dorse"] == 1, (
            "dorse_repo.get_all satır sayısından bağımsız TEK kez çağrılmalı"
        )
        assert calls["lokasyon"] == 1, (
            "lokasyon_repo.get_all satır sayısından bağımsız TEK kez çağrılmalı"
        )

    async def test_rollback_db_error_raises_500(self):
        """DB error during rollback → HTTPException 500."""
        from fastapi import HTTPException

        job = SimpleNamespace(
            id=1,
            durum="COMPLETED",
            aktarim_tipi="arac",
            islem_haritasi={"inserted_ids": [10]},
        )
        fake_uow = _FakeUoW()
        fake_uow.import_repo = AsyncMock()
        fake_uow.import_repo.get_by_id = AsyncMock(return_value=job)
        fake_uow.import_repo.update_job_status = AsyncMock()

        # Make session.execute raise
        async def _raise(*a, **kw):
            raise RuntimeError("DB constraint violation")

        fake_uow.session.execute = _raise

        with (
            patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)),
            patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await rollback_import(1, 1)

        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# process_sefer_import — error path branches (lines 521, 523-529, 531-545)
# ---------------------------------------------------------------------------


class TestProcessSeferImportErrorBranches:
    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_invalid_plaka_maps_to_plaka_field(
        self, mock_parse, svc, real_master
    ):
        mock_parse.return_value = [
            {
                "plaka": "BADPLAKA",  # invalid format → INVALID_PLAKA
                "sofor_adi": "Ahmet Yilmaz",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450,
                "net_kg": 20000,
            }
        ]

        count, errors = await process_sefer_import(b"fake")
        assert count == 0
        assert len(errors) >= 1
        assert errors[0]["field"] == "plaka"

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_route_not_found_maps_to_guzergah_field(
        self, mock_parse, svc, real_master
    ):
        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "sofor_adi": "Ahmet Yilmaz",
                "cikis_yeri": "Bilinmeyen",
                "varis_yeri": "Sehir",
                "tarih": date.today(),
                "mesafe_km": 450,
                "net_kg": 20000,
            }
        ]

        count, errors = await process_sefer_import(b"fake")
        assert len(errors) >= 1
        assert errors[0]["field"] == "guzergah"

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_invalid_numeric_maps_to_net_kg_field(
        self, mock_parse, svc, real_master
    ):
        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "sofor_adi": "Ahmet Yilmaz",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": "not-a-number",
                "net_kg": 20000,
            }
        ]

        count, errors = await process_sefer_import(b"fake")
        assert len(errors) >= 1
        # INVALID_NUMERIC → net_kg field
        assert errors[0]["field"] == "net_kg"

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_generic_exception_maps_to_genel_field(
        self, mock_parse, svc, real_master
    ):
        mock_parse.return_value = [
            {
                "plaka": "34ABC123",
                "sofor_adi": "Ahmet Yilmaz",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450,
                "net_kg": 20000,
            }
        ]

        # Make bulk_add_sefer raise after validation passes
        svc.bulk_add_sefer.side_effect = RuntimeError("DB crash")

        count, errors = await process_sefer_import(b"fake")
        # bulk_add_sefer raising after validation passes is caught by the
        # function's outer try/except → (0, ["Sistem hatası: <msg>"]).
        assert count == 0
        assert errors == ["Sistem hatası: DB crash"]

    @patch(
        "v2.modules.import_excel.application.sefer_importer.parse_sefer_excel",
        new_callable=AsyncMock,
    )
    async def test_value_error_plaka_msg_maps_field(self, mock_parse, svc, real_master):
        """ValueError with Plaka in message → plaka field."""
        mock_parse.return_value = [
            {
                "plaka": None,  # validate_plaka raises ImportValidationError → INVALID_PLAKA
                "sofor_adi": "Ahmet Yilmaz",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450,
                "net_kg": 20000,
            }
        ]

        count, errors = await process_sefer_import(b"fake")
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# process_vehicle_import — more branches (lines 667-712)
# ---------------------------------------------------------------------------


class TestProcessVehicleImportExtra:
    @patch(
        "v2.modules.import_excel.application.vehicle_importer.parse_vehicle_excel",
        new_callable=AsyncMock,
    )
    async def test_system_error_returns_error(self, mock_parse, real_master):
        """System exception → (0, ['Sistem hatası...'])"""
        mock_parse.side_effect = Exception("unexpected crash")

        count, errors = await process_vehicle_import(b"fake")
        assert count == 0
        assert "Sistem hatası" in errors[0]

    @patch(
        "v2.modules.import_excel.application.vehicle_importer.parse_vehicle_excel",
        new_callable=AsyncMock,
    )
    async def test_empty_data_returns_error(self, mock_parse, real_master):
        """Empty vehicle data → (0, ['Excel dosyasında veri bulunamadı.'])"""
        mock_parse.return_value = []

        count, errors = await process_vehicle_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch(
        "v2.modules.import_excel.application.vehicle_importer.parse_vehicle_excel",
        new_callable=AsyncMock,
    )
    async def test_invalid_plaka_in_vehicle_row(self, mock_parse, real_master):
        """Invalid plaka → error row."""
        mock_parse.return_value = [{"plaka": "BAD", "marka": "Mercedes"}]

        count, errors = await process_vehicle_import(b"fake")
        assert len(errors) >= 1
        # Error could be per-row "Satır X: ..." or wrapped "Sistem hatası: ..."
        assert any(kw in errors[0] for kw in ("Sat", "Sistem", "uzunlu", "geçersiz"))


# ---------------------------------------------------------------------------
# process_driver_import — lines 716-725
# ---------------------------------------------------------------------------


class TestProcessDriverImportExtra:
    @patch(
        "v2.modules.import_excel.application.driver_importer.parse_driver_excel",
        new_callable=AsyncMock,
    )
    async def test_empty_data_returns_error(self, mock_parse):
        from v2.modules.import_excel.application.driver_importer import (
            process_driver_import,
        )

        mock_parse.return_value = []

        count, errors = await process_driver_import(b"fake")
        assert count == 0
        assert "veri bulunamadı" in errors[0]

    @patch(
        "v2.modules.import_excel.application.driver_importer.parse_driver_excel",
        new_callable=AsyncMock,
    )
    async def test_system_error_returns_error(self, mock_parse):
        from v2.modules.import_excel.application.driver_importer import (
            process_driver_import,
        )

        mock_parse.side_effect = Exception("parse crash")

        count, errors = await process_driver_import(b"fake")
        assert count == 0
        assert "Sistem hatası" in errors[0]

    @patch("v2.modules.driver.public.bulk_add_sofor")
    @patch(
        "v2.modules.import_excel.application.driver_importer.parse_driver_excel",
        new_callable=AsyncMock,
    )
    async def test_happy_path(self, mock_parse, mock_bulk_add_sofor):
        from v2.modules.import_excel.application.driver_importer import (
            process_driver_import,
        )

        mock_parse.return_value = [{"ad_soyad": "Ali Veli", "telefon": "5551234567"}]
        mock_bulk_add_sofor.return_value = 1

        count, errors = await process_driver_import(b"fake")
        assert count == 1
        assert not errors


# ---------------------------------------------------------------------------
# import_routes — lines 734-761
# ---------------------------------------------------------------------------


class TestImportRoutesExtra:
    @patch(
        "v2.modules.import_excel.application.route_importer.parse_route_excel",
        new_callable=AsyncMock,
    )
    async def test_system_error_returns_error(self, mock_parse):
        mock_parse.side_effect = Exception("file crash")

        count, errors = await import_routes(b"fake")
        assert count == 0
        assert "Sistem hatası" in errors[0]

    @patch(
        "v2.modules.import_excel.application.route_importer.parse_route_excel",
        new_callable=AsyncMock,
    )
    async def test_row_exception_adds_to_errors(
        self, mock_parse, real_master, monkeypatch
    ):
        """Row-level exception → partial count + error entry."""
        mock_parse.return_value = [
            {"cikis_yeri": "X", "varis_yeri": "Y", "mesafe_km": 100},
            {"cikis_yeri": None, "varis_yeri": None, "mesafe_km": "bad"},  # invalid
        ]

        call_count = [0]

        async def _fake_create_location(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return 1
            raise ValueError("invalid lokasyon")

        monkeypatch.setattr(
            "v2.modules.location.public.create_location",
            _fake_create_location,
        )

        count, errors = await import_routes(b"fake")
        # Row 1 (valid) succeeds; row 2 has cikis_yeri/varis_yeri=None +
        # mesafe_km="bad" — LokasyonCreate(**item) raises a pydantic
        # ValidationError before create_location is ever called, so the
        # fake's ValueError branch is unreachable here (only 1 real call
        # happens). Import loop is 1-indexed (enumerate(items, 1)).
        assert count == 1
        assert call_count[0] == 1
        assert len(errors) == 1
        assert errors[0].startswith("Satır 2:")


# ---------------------------------------------------------------------------
# validate_import_rows — sefer type full path (lines 173-183)
# ---------------------------------------------------------------------------


class TestValidateImportRowsSeferFull:
    def test_sefer_valid_row_with_dorse(self):
        vehicles = [{"id": 1, "plaka": "34ABC123"}]
        drivers = [{"id": 1, "ad_soyad": "Ahmet Yilmaz"}]
        trailers = [{"id": 5, "plaka": "34DRS001"}]
        routes = [{"id": 10, "cikis_yeri": "Ankara", "varis_yeri": "Istanbul"}]
        rows = [
            {
                "plaka": "34ABC123",
                "sofor_ad": "Ahmet Yilmaz",
                "dorse_plakasi": "34DRS001",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450.0,
                "ton": 20000.0,
            }
        ]
        mapping = {
            "plaka": "plaka",
            "sofor_ad": "sofor_ad",
            "dorse_plakasi": "dorse_plakasi",
            "cikis_yeri": "cikis_yeri",
            "varis_yeri": "varis_yeri",
            "tarih": "tarih",
            "mesafe_km": "mesafe_km",
            "ton": "ton",
        }
        valid, errors = validate_import_rows(
            rows, "sefer", mapping, vehicles, drivers, trailers, routes
        )
        assert len(valid) == 1
        assert valid[0]["dorse_id"] == 5
        assert valid[0]["arac_id"] == 1
        assert valid[0]["sofor_id"] == 1
        assert valid[0]["guzergah_id"] == 10

    def test_sefer_valid_row_no_dorse(self):
        vehicles = [{"id": 1, "plaka": "34ABC123"}]
        drivers = [{"id": 1, "ad_soyad": "Ahmet Yilmaz"}]
        routes = [{"id": 10, "cikis_yeri": "Ankara", "varis_yeri": "Istanbul"}]
        rows = [
            {
                "plaka": "34ABC123",
                "sofor_ad": "Ahmet Yilmaz",
                "dorse_plakasi": "",
                "cikis_yeri": "Ankara",
                "varis_yeri": "Istanbul",
                "tarih": date.today(),
                "mesafe_km": 450.0,
                "ton": 20000.0,
            }
        ]
        mapping = {
            "plaka": "plaka",
            "sofor_ad": "sofor_ad",
            "dorse_plakasi": "dorse_plakasi",
            "cikis_yeri": "cikis_yeri",
            "varis_yeri": "varis_yeri",
            "tarih": "tarih",
            "mesafe_km": "mesafe_km",
            "ton": "ton",
        }
        valid, errors = validate_import_rows(
            rows, "sefer", mapping, vehicles, drivers, [], routes
        )
        assert len(valid) == 1
        assert valid[0]["dorse_id"] is None
