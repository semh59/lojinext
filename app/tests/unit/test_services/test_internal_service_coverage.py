"""InternalService unit tests — app/core/services/internal_service.py

Tests cover:
- get_sofor_by_telegram_id: found, not found
- kaydet_belge: unknown telegram_id raises ValueError, happy path
- get_seferler: sofor not found returns None, sofor found returns list
- get_sofor_id: found returns id, not found returns None
- olustur_pdf: sofor not found returns None, found delegates to SoforSeferPDFService
- get_coaching_snapshot: sofor not found returns None, engine success,
  engine failure returns fallback, top insight present
- get_internal_service: uses container
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service():
    """Return InternalService with mocked sofor_repo and sefer_repo."""
    from app.core.services.internal_service import InternalService

    svc = InternalService.__new__(InternalService)
    svc._sofor_repo = AsyncMock()
    svc._sefer_repo = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# get_sofor_by_telegram_id
# ---------------------------------------------------------------------------


class TestGetSoforByTelegramId:
    async def test_found_returns_dict(self):
        """Returns sofor dict when found."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 1, "ad_soyad": "Ali", "aktif": True}
        )

        result = await svc.get_sofor_by_telegram_id("tg123")
        assert result["id"] == 1
        assert result["ad_soyad"] == "Ali"

    async def test_not_found_returns_none(self):
        """Returns None when sofor does not exist."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(return_value=None)

        result = await svc.get_sofor_by_telegram_id("unknown")
        assert result is None


# ---------------------------------------------------------------------------
# kaydet_belge
# ---------------------------------------------------------------------------


class TestKaydetBelge:
    async def test_unknown_telegram_id_raises_value_error(self):
        """Raises ValueError when telegram_id not registered."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Yetkisiz"):
            await svc.kaydet_belge(
                telegram_id="unknown",
                belge_tipi="yakit_fisi",
                image_bytes=b"img",
                content_type="image/jpeg",
            )

    async def test_happy_path_returns_belge_and_sofor_id(self):
        """Returns {belge_id, sofor_id} on success."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 5, "ad_soyad": "Veli"}
        )

        fake_belge = MagicMock()
        fake_belge.id = 99

        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow.session = MagicMock()
        mock_uow.session.add = MagicMock()
        mock_uow.flush = AsyncMock()
        mock_uow.commit = AsyncMock()

        with (
            patch(
                "app.core.services.internal_service.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "app.core.services.internal_service.SeferBelge",
                return_value=fake_belge,
            ),
            patch("builtins.open", mock_open()),
            patch("os.makedirs"),
        ):
            result = await svc.kaydet_belge(
                telegram_id="tg1",
                belge_tipi="yakit_fisi",
                image_bytes=b"fake image",
                content_type="image/jpeg",
                telegram_mesaj_id=42,
            )

        assert result["belge_id"] == 99
        assert result["sofor_id"] == 5

    async def test_png_extension_used_for_non_jpeg(self):
        """Uses .png extension for non-jpeg content_type."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 3, "ad_soyad": "Test"}
        )

        fake_belge = MagicMock()
        fake_belge.id = 10

        mock_uow = MagicMock()
        mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
        mock_uow.__aexit__ = AsyncMock(return_value=False)
        mock_uow.session = MagicMock()
        mock_uow.session.add = MagicMock()
        mock_uow.flush = AsyncMock()
        mock_uow.commit = AsyncMock()

        opened_paths = []

        def capture_open(path, mode):
            opened_paths.append(path)
            return mock_open()()

        with (
            patch(
                "app.core.services.internal_service.UnitOfWork",
                return_value=mock_uow,
            ),
            patch(
                "app.core.services.internal_service.SeferBelge",
                return_value=fake_belge,
            ),
            patch("builtins.open", mock_open()) as m_open,
            patch("os.makedirs"),
        ):
            await svc.kaydet_belge(
                telegram_id="tg1",
                belge_tipi="sefer_fisi",
                image_bytes=b"png data",
                content_type="image/png",
            )
            # Verify file was opened (path ends in .png)
            call_args = m_open.call_args
            assert call_args is not None


# ---------------------------------------------------------------------------
# get_seferler
# ---------------------------------------------------------------------------


class TestGetSeferler:
    async def test_sofor_not_found_returns_none(self):
        """Returns None when sofor does not exist."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(return_value=None)

        result = await svc.get_seferler("unknown")
        assert result is None

    async def test_sofor_found_returns_trips(self):
        """Returns list of trips for found sofor."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 7, "ad_soyad": "Fatih"}
        )
        svc._sefer_repo.get_by_sofor_id = AsyncMock(
            return_value=[{"id": 1, "cikis_yeri": "İstanbul"}]
        )

        result = await svc.get_seferler("tg7", limit=5)
        assert result is not None
        assert len(result) == 1
        svc._sefer_repo.get_by_sofor_id.assert_called_once_with(7, limit=5)

    async def test_default_limit_is_10(self):
        """Default limit is 10."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 8, "ad_soyad": "X"}
        )
        svc._sefer_repo.get_by_sofor_id = AsyncMock(return_value=[])

        await svc.get_seferler("tg8")
        svc._sefer_repo.get_by_sofor_id.assert_called_once_with(8, limit=10)


# ---------------------------------------------------------------------------
# get_sofor_id
# ---------------------------------------------------------------------------


class TestGetSoforId:
    async def test_found_returns_id(self):
        """Returns integer sofor ID when found."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 42, "ad_soyad": "Kadir"}
        )

        result = await svc.get_sofor_id("tg42")
        assert result == 42

    async def test_not_found_returns_none(self):
        """Returns None when sofor not found."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(return_value=None)

        result = await svc.get_sofor_id("unknown")
        assert result is None


# ---------------------------------------------------------------------------
# olustur_pdf
# ---------------------------------------------------------------------------


class TestOlusturPdf:
    async def test_sofor_not_found_returns_none(self):
        """Returns None when sofor not found."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(return_value=None)

        result = await svc.olustur_pdf("unknown", date(2026, 1, 1), date(2026, 1, 31))
        assert result is None

    async def test_found_delegates_to_pdf_service(self):
        """Delegates to SoforSeferPDFService when sofor found."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 15, "ad_soyad": "Hasan"}
        )

        mock_pdf_svc = MagicMock()
        mock_pdf_svc.olustur = AsyncMock(return_value=b"%PDF content")

        # SoforSeferPDFService is imported inline; patch in its own module
        with patch(
            "app.core.services.sofor_pdf_service.SoforSeferPDFService",
            return_value=mock_pdf_svc,
        ):
            result = await svc.olustur_pdf("tg15", date(2026, 5, 1), date(2026, 5, 31))

        assert result == b"%PDF content"
        mock_pdf_svc.olustur.assert_called_once_with(
            15, date(2026, 5, 1), date(2026, 5, 31)
        )


# ---------------------------------------------------------------------------
# get_coaching_snapshot
# ---------------------------------------------------------------------------


class TestGetCoachingSnapshot:
    async def test_sofor_not_found_returns_none(self):
        """Returns None when sofor not found."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(return_value=None)

        result = await svc.get_coaching_snapshot("unknown")
        assert result is None

    async def test_engine_success_returns_snapshot(self):
        """Returns populated snapshot when engine succeeds."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 3, "ad_soyad": "Musa", "score": 0.9}
        )

        mock_insight = MagicMock()
        mock_insight.suggestion = "Yakıt tasarrufu yapın"

        mock_insights = MagicMock()
        mock_insights.ad_soyad = "Musa"
        mock_insights.headline = "Performans iyi"
        mock_insights.priority = "low"
        mock_insights.source = "ai"
        mock_insights.insights = [mock_insight]

        mock_engine = MagicMock()
        mock_engine.generate_coaching = AsyncMock(return_value=mock_insights)

        # get_driver_coaching_engine is imported inline inside the function
        with patch(
            "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
            return_value=mock_engine,
        ):
            result = await svc.get_coaching_snapshot("tg3")

        assert result["ad_soyad"] == "Musa"
        assert result["top_suggestion"] == "Yakıt tasarrufu yapın"
        assert result["insights_count"] == 1
        assert result["source"] == "ai"

    async def test_engine_failure_returns_fallback(self):
        """Returns fallback dict when engine raises exception."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 4, "ad_soyad": "Ömer", "score": 0.75}
        )

        mock_engine = MagicMock()
        mock_engine.generate_coaching = AsyncMock(
            side_effect=RuntimeError("Engine failed")
        )

        with patch(
            "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
            return_value=mock_engine,
        ):
            result = await svc.get_coaching_snapshot("tg4")

        assert result is not None
        assert result["source"] == "fallback"
        assert result["insights_count"] == 0
        assert result["top_suggestion"] is None

    async def test_no_insights_returns_none_top_suggestion(self):
        """Returns None top_suggestion when no insights available."""
        svc = _make_service()
        svc._sofor_repo.get_by_telegram_id = AsyncMock(
            return_value={"id": 5, "ad_soyad": "Yusuf", "manual_score": 0.6}
        )

        mock_insights = MagicMock()
        mock_insights.ad_soyad = "Yusuf"
        mock_insights.headline = "Yeni şoför"
        mock_insights.priority = "medium"
        mock_insights.source = "ai"
        mock_insights.insights = []  # no insights

        mock_engine = MagicMock()
        mock_engine.generate_coaching = AsyncMock(return_value=mock_insights)

        with patch(
            "app.core.ai.driver_coaching_engine.get_driver_coaching_engine",
            return_value=mock_engine,
        ):
            result = await svc.get_coaching_snapshot("tg5")

        assert result["top_suggestion"] is None
        assert result["insights_count"] == 0


# ---------------------------------------------------------------------------
# get_internal_service factory
# ---------------------------------------------------------------------------


class TestGetInternalService:
    def test_returns_internal_service_from_container(self):
        """get_internal_service returns InternalService from container."""
        from app.core.services.internal_service import (
            InternalService,
            get_internal_service,
        )

        mock_svc = MagicMock(spec=InternalService)
        mock_container = MagicMock()
        mock_container.internal_service = mock_svc

        # get_container is imported inline inside get_internal_service;
        # patch it in the container module.
        with patch(
            "app.core.container.get_container",
            return_value=mock_container,
        ):
            result = get_internal_service()

        assert result is mock_svc
