"""InternalService unit tests — app/core/services/internal_service.py — real DB.

Previously these built the service via ``InternalService.__new__`` and injected
``AsyncMock()`` repos, asserting on inner calls
(``_sefer_repo.get_by_sofor_id.assert_called_once_with(...)``) — i.e. *that a
repo method was called* rather than *the persisted result*. Here the service is
the real one: ``InternalService()`` wires the real singleton repos, whose
``_get_session()`` falls through to ``app.database.connection.AsyncSessionLocal``
which the ``db_session`` fixture monkeypatches to the shared test session — so
the repos read/write the real test DB. We seed real Sofor/Sefer rows and assert
real results (returned dicts, persisted SeferBelge rows, real PDF bytes).

The only retained stub is the driver-coaching *engine*, which wraps the Groq
LLM (external, non-deterministic) — a legitimate Category-B boundary. The Sofor
lookup around it is real, so the DB seam (where a hidden contract bug would
hide) is exercised for real.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.services.internal_service import InternalService
from app.database.models import SeferBelge
from app.tests._helpers.seed import seed_arac, seed_sefer, seed_sofor

pytestmark = pytest.mark.integration
# ---------------------------------------------------------------------------
# get_sofor_by_telegram_id
# ---------------------------------------------------------------------------


class TestGetSoforByTelegramId:
    async def test_found_returns_dict(self, db_session):
        """Returns sofor dict when found."""
        await seed_sofor(db_session, ad_soyad="Ali", telegram_id="tg123")
        await db_session.commit()

        result = await InternalService().get_sofor_by_telegram_id("tg123")
        assert result is not None
        assert result["ad_soyad"] == "Ali"
        assert result["telegram_id"] == "tg123"

    async def test_not_found_returns_none(self, db_session):
        """Returns None when sofor does not exist."""
        result = await InternalService().get_sofor_by_telegram_id("unknown")
        assert result is None

    async def test_inactive_sofor_not_returned(self, db_session):
        """Soft-deleted/inactive sofor is filtered out (aktif + is_deleted guard)."""
        await seed_sofor(
            db_session, ad_soyad="Pasif", telegram_id="tgpasif", aktif=False
        )
        await db_session.commit()

        result = await InternalService().get_sofor_by_telegram_id("tgpasif")
        assert result is None


# ---------------------------------------------------------------------------
# kaydet_belge
# ---------------------------------------------------------------------------


class TestKaydetBelge:
    async def test_unknown_telegram_id_raises_value_error(self, db_session):
        """Raises ValueError when telegram_id not registered."""
        with pytest.raises(ValueError, match="Yetkisiz"):
            await InternalService().kaydet_belge(
                telegram_id="unknown",
                belge_tipi="yakit_fisi",
                image_bytes=b"img",
                content_type="image/jpeg",
            )

    async def test_happy_path_persists_belge(self, db_session, tmp_path, monkeypatch):
        """Writes the file to disk and persists a SeferBelge row."""
        monkeypatch.setenv("BELGELER_UPLOAD_DIR", str(tmp_path))
        sofor = await seed_sofor(db_session, ad_soyad="Veli", telegram_id="tg1")
        await db_session.commit()

        result = await InternalService().kaydet_belge(
            telegram_id="tg1",
            belge_tipi="yakit_fisi",
            image_bytes=b"fake image",
            content_type="image/jpeg",
            telegram_mesaj_id=42,
        )

        assert result["sofor_id"] == sofor.id
        # Real DB row was created with the returned belge_id.
        row = (
            await db_session.execute(
                select(SeferBelge).where(SeferBelge.id == result["belge_id"])
            )
        ).scalar_one()
        assert row.sofor_id == sofor.id
        assert row.belge_tipi == "yakit_fisi"
        assert row.telegram_mesaj_id == 42
        assert row.ocr_durumu == "bekliyor"
        # File written to disk with .jpg extension.
        assert row.dosya_yolu.endswith(".jpg")
        with open(row.dosya_yolu, "rb") as fh:
            assert fh.read() == b"fake image"

    async def test_png_extension_used_for_non_jpeg(
        self, db_session, tmp_path, monkeypatch
    ):
        """Uses .png extension for non-jpeg content_type."""
        monkeypatch.setenv("BELGELER_UPLOAD_DIR", str(tmp_path))
        await seed_sofor(db_session, ad_soyad="Png User", telegram_id="tg1")
        await db_session.commit()

        result = await InternalService().kaydet_belge(
            telegram_id="tg1",
            belge_tipi="sefer_fisi",
            image_bytes=b"png data",
            content_type="image/png",
        )

        row = (
            await db_session.execute(
                select(SeferBelge).where(SeferBelge.id == result["belge_id"])
            )
        ).scalar_one()
        assert row.dosya_yolu.endswith(".png")

    async def test_invalid_belge_tipi_raises(self, db_session, tmp_path, monkeypatch):
        """Rejects belge_tipi outside the allowed set."""
        monkeypatch.setenv("BELGELER_UPLOAD_DIR", str(tmp_path))
        await seed_sofor(db_session, ad_soyad="Geçersiz", telegram_id="tg1")
        await db_session.commit()

        with pytest.raises(ValueError, match="Geçersiz belge_tipi"):
            await InternalService().kaydet_belge(
                telegram_id="tg1",
                belge_tipi="bilinmeyen",
                image_bytes=b"img",
                content_type="image/jpeg",
            )


# ---------------------------------------------------------------------------
# get_seferler
# ---------------------------------------------------------------------------


class TestGetSeferler:
    async def test_sofor_not_found_returns_none(self, db_session):
        """Returns None when sofor does not exist."""
        result = await InternalService().get_seferler("unknown")
        assert result is None

    async def test_sofor_found_returns_trips(self, db_session):
        """Returns list of trips for found sofor."""
        sofor = await seed_sofor(db_session, ad_soyad="Fatih", telegram_id="tg7")
        arac = await seed_arac(db_session, plaka="34SEF001")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            cikis_yeri="İstanbul",
            varis_yeri="Bursa",
        )
        await db_session.commit()

        result = await InternalService().get_seferler("tg7", limit=5)
        assert result is not None
        assert len(result) == 1
        assert result[0]["cikis_yeri"] == "İstanbul"
        assert result[0]["sofor_id"] == sofor.id

    async def test_default_limit_caps_results(self, db_session):
        """Default limit (10) caps the number of returned trips."""
        sofor = await seed_sofor(db_session, ad_soyad="Limit User", telegram_id="tg8")
        arac = await seed_arac(db_session, plaka="34LIM001")
        for _ in range(11):
            await seed_sefer(db_session, arac_id=arac.id, sofor_id=sofor.id)
        await db_session.commit()

        result = await InternalService().get_seferler("tg8")
        assert result is not None
        assert len(result) == 10


# ---------------------------------------------------------------------------
# get_sofor_id
# ---------------------------------------------------------------------------


class TestGetSoforId:
    async def test_found_returns_id(self, db_session):
        """Returns integer sofor ID when found."""
        sofor = await seed_sofor(db_session, ad_soyad="Kadir", telegram_id="tg42")
        await db_session.commit()

        result = await InternalService().get_sofor_id("tg42")
        assert result == sofor.id

    async def test_not_found_returns_none(self, db_session):
        """Returns None when sofor not found."""
        result = await InternalService().get_sofor_id("unknown")
        assert result is None


# ---------------------------------------------------------------------------
# olustur_pdf
# ---------------------------------------------------------------------------


class TestOlusturPdf:
    async def test_sofor_not_found_returns_none(self, db_session):
        """Returns None when sofor not found."""
        result = await InternalService().olustur_pdf(
            "unknown", date(2026, 1, 1), date(2026, 1, 31)
        )
        assert result is None

    async def test_found_generates_real_pdf(self, db_session):
        """Delegates to the real SoforSeferPDFService and returns PDF bytes."""
        sofor = await seed_sofor(db_session, ad_soyad="Hasan", telegram_id="tg15")
        arac = await seed_arac(db_session, plaka="34PDF001")
        await seed_sefer(
            db_session,
            arac_id=arac.id,
            sofor_id=sofor.id,
            tarih=date(2026, 5, 10),
            durum="Completed",
            tuketim=30.0,
            onay_durumu="onaylandi",
        )
        await db_session.commit()

        result = await InternalService().olustur_pdf(
            "tg15", date(2026, 5, 1), date(2026, 5, 31)
        )

        assert isinstance(result, (bytes, bytearray))
        assert bytes(result).startswith(b"%PDF")


# ---------------------------------------------------------------------------
# get_coaching_snapshot
#
# The coaching *engine* wraps the Groq LLM (external, non-deterministic) — a
# legitimate Category-B boundary, so it stays stubbed. The Sofor lookup around
# it is real (seeded row + real repo), which is the seam this test guards.
# ---------------------------------------------------------------------------


class TestGetCoachingSnapshot:
    async def test_sofor_not_found_returns_none(self, db_session):
        """Returns None when sofor not found."""
        result = await InternalService().get_coaching_snapshot("unknown")
        assert result is None

    async def test_engine_success_returns_snapshot(self, db_session):
        """Returns populated snapshot when engine succeeds (real sofor lookup)."""
        await seed_sofor(db_session, ad_soyad="Musa", telegram_id="tg3")
        await db_session.commit()

        mock_insight = MagicMock()
        mock_insight.suggestion = "Yakıt tasarrufu yapın"

        mock_insights = MagicMock()
        mock_insights.ad_soyad = "Musa"
        mock_insights.headline = "Performans iyi"
        mock_insights.priority = "low"
        mock_insights.source = "llm"
        mock_insights.insights = [mock_insight]

        mock_engine = MagicMock()
        mock_engine.generate_coaching = AsyncMock(return_value=mock_insights)

        with patch(
            "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
            return_value=mock_engine,
        ):
            result = await InternalService().get_coaching_snapshot("tg3")

        assert result["ad_soyad"] == "Musa"
        assert result["top_suggestion"] == "Yakıt tasarrufu yapın"
        assert result["insights_count"] == 1
        assert result["source"] == "llm"

    async def test_engine_failure_returns_fallback(self, db_session):
        """Returns fallback dict when engine raises (real sofor lookup)."""
        await seed_sofor(db_session, ad_soyad="Ömer", telegram_id="tg4")
        await db_session.commit()

        mock_engine = MagicMock()
        mock_engine.generate_coaching = AsyncMock(
            side_effect=RuntimeError("Engine failed")
        )

        with patch(
            "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
            return_value=mock_engine,
        ):
            result = await InternalService().get_coaching_snapshot("tg4")

        assert result is not None
        assert result["source"] == "fallback"
        assert result["insights_count"] == 0
        assert result["top_suggestion"] is None
        assert result["ad_soyad"] == "Ömer"

    async def test_no_insights_returns_none_top_suggestion(self, db_session):
        """Returns None top_suggestion when no insights available."""
        await seed_sofor(db_session, ad_soyad="Yusuf", telegram_id="tg5")
        await db_session.commit()

        mock_insights = MagicMock()
        mock_insights.ad_soyad = "Yusuf"
        mock_insights.headline = "Yeni şoför"
        mock_insights.priority = "medium"
        mock_insights.source = "llm"
        mock_insights.insights = []  # no insights

        mock_engine = MagicMock()
        mock_engine.generate_coaching = AsyncMock(return_value=mock_insights)

        with patch(
            "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
            return_value=mock_engine,
        ):
            result = await InternalService().get_coaching_snapshot("tg5")

        assert result["top_suggestion"] is None
        assert result["insights_count"] == 0


# ---------------------------------------------------------------------------
# get_internal_service factory
# ---------------------------------------------------------------------------


class TestGetInternalService:
    def test_returns_internal_service_from_container(self):
        """get_internal_service returns the container's real InternalService."""
        from app.core.container import get_container
        from app.core.services.internal_service import get_internal_service

        result = get_internal_service()
        assert isinstance(result, InternalService)
        # Same singleton the container hands out.
        assert result is get_container().internal_service
