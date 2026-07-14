"""
Unit tests for ContextBuilder — targeting ≥70% coverage.

All service/repo calls are mocked; no DB, no network.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.ai.context_builder import ContextBuilder, get_context_builder

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_builder() -> ContextBuilder:
    return ContextBuilder()


def _mock_report_service(stats: dict):
    svc = MagicMock()
    svc.get_dashboard_summary = AsyncMock(return_value=stats)
    return svc


def _mock_rag_engine(total_documents: int = 100):
    engine = MagicMock()
    engine.get_stats = MagicMock(return_value={"total_documents": total_documents})
    return engine


# ---------------------------------------------------------------------------
# build_system_context — happy path
# ---------------------------------------------------------------------------


async def test_build_system_context_returns_formatted_string():
    builder = _make_builder()
    stats = {
        "aktif_arac": 10,
        "aktif_sofor": 8,
        "toplam_sefer": 500,
        "toplam_km": 250000,
        "filo_ortalama": 31.5,
    }

    with (
        patch.object(
            type(builder),
            "report_service",
            new_callable=lambda: property(lambda self: _mock_report_service(stats)),
        ),
        patch.object(
            type(builder),
            "rag_engine",
            new_callable=lambda: property(lambda self: _mock_rag_engine(42)),
        ),
    ):
        result = await builder.build_system_context()

    assert "10" in result
    assert "8" in result
    assert "42" in result
    assert "31.5" in result


async def test_build_system_context_exception_returns_fallback():
    builder = _make_builder()

    with (
        patch.object(
            type(builder),
            "report_service",
            new_callable=lambda: property(
                lambda self: MagicMock(
                    get_dashboard_summary=AsyncMock(side_effect=RuntimeError("DB down"))
                )
            ),
        ),
    ):
        result = await builder.build_system_context()

    assert "erişilemiyor" in result.lower() or "sistem" in result.lower()


# ---------------------------------------------------------------------------
# build_vehicle_context
# ---------------------------------------------------------------------------


async def test_build_vehicle_context_invalid_id_string_returns_error():
    builder = _make_builder()
    result = await builder.build_vehicle_context("bad")  # type: ignore
    assert "Geçersiz" in result


async def test_build_vehicle_context_invalid_id_zero_returns_error():
    builder = _make_builder()
    result = await builder.build_vehicle_context(0)
    assert "Geçersiz" in result


async def test_build_vehicle_context_arac_not_found_returns_error():
    builder = _make_builder()

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_by_id = AsyncMock(return_value=None)

    with patch.object(
        type(builder),
        "arac_repo",
        new_callable=lambda: property(lambda self: mock_arac_repo),
    ):
        result = await builder.build_vehicle_context(1)

    assert "bulunamadı" in result


async def test_build_vehicle_context_success():
    builder = _make_builder()

    arac_data = {
        "id": 1,
        "plaka": "34 TIR 001",
        "marka": "VOLVO",
        "model": "FH",
        "yil": 2020,
        "tank_kapasitesi": 600,
        "hedef_tuketim": 32.0,
    }
    mock_arac_repo = MagicMock()
    mock_arac_repo.get_by_id = AsyncMock(return_value=arac_data)

    mock_sefer_repo = MagicMock()
    mock_sefer_repo.get_all = AsyncMock(return_value=[])

    mock_yakit_repo = MagicMock()
    mock_yakit_repo.get_all = AsyncMock(return_value=[])

    # Mock Arac entity — patched at its source module (lazy import inside method)
    mock_arac_entity = MagicMock()
    mock_arac_entity.yas = 4
    mock_arac_entity.euro_sinifi = "Euro 6"
    mock_arac_entity.yas_faktoru = 1.02

    with (
        patch.object(
            type(builder),
            "arac_repo",
            new_callable=lambda: property(lambda self: mock_arac_repo),
        ),
        patch.object(
            type(builder),
            "sefer_repo",
            new_callable=lambda: property(lambda self: mock_sefer_repo),
        ),
        patch.object(
            type(builder),
            "yakit_repo",
            new_callable=lambda: property(lambda self: mock_yakit_repo),
        ),
        patch("app.core.entities.models.Arac", return_value=mock_arac_entity),
    ):
        result = await builder.build_vehicle_context(1)

    assert "34 TIR 001" in result
    assert "VOLVO" in result


async def test_build_vehicle_context_exception_returns_fallback():
    builder = _make_builder()

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_by_id = AsyncMock(side_effect=RuntimeError("DB error"))

    with patch.object(
        type(builder),
        "arac_repo",
        new_callable=lambda: property(lambda self: mock_arac_repo),
    ):
        result = await builder.build_vehicle_context(1)

    assert "erişilemiyor" in result.lower()


# ---------------------------------------------------------------------------
# build_driver_context
# ---------------------------------------------------------------------------


async def test_build_driver_context_invalid_id_returns_error():
    builder = _make_builder()
    result = await builder.build_driver_context(-1)
    assert "Geçersiz" in result


async def test_build_driver_context_no_evaluation_returns_error():
    builder = _make_builder()

    with patch(
        "v2.modules.driver.domain.evaluation.evaluate_driver",
        AsyncMock(return_value=None),
    ):
        result = await builder.build_driver_context(1)

    assert "yapılamadı" in result


async def test_build_driver_context_success():
    from v2.modules.driver.domain.evaluation import DereceEnum, TrendEnum

    builder = _make_builder()

    mock_eval = MagicMock()
    mock_eval.ad_soyad = "Mehmet Kaya"
    mock_eval.genel_puan = 78.5
    mock_eval.derece = DereceEnum.B
    mock_eval.yildiz = 4
    mock_eval.verimlilik_puani = 80.0
    mock_eval.tutarlilik_puani = 75.0
    mock_eval.deneyim_puani = 70.0
    mock_eval.trend_puani = 65.0
    mock_eval.toplam_sefer = 150
    mock_eval.toplam_km = 120000
    mock_eval.ort_tuketim = 30.5
    mock_eval.filo_karsilastirma = 4.7
    mock_eval.trend = TrendEnum.IMPROVING
    mock_eval.guclu_yanlar = ["Yakıt verimliliği iyi"]
    mock_eval.tavsiyeler = []

    with patch(
        "v2.modules.driver.domain.evaluation.evaluate_driver",
        AsyncMock(return_value=mock_eval),
    ):
        result = await builder.build_driver_context(1)

    assert "Mehmet Kaya" in result
    assert "78.5" in result
    assert "Yakıt verimliliği iyi" in result


async def test_build_driver_context_exception_returns_fallback():
    builder = _make_builder()

    with patch(
        "v2.modules.driver.domain.evaluation.evaluate_driver",
        AsyncMock(side_effect=RuntimeError("evaluate_driver error")),
    ):
        result = await builder.build_driver_context(1)

    assert "erişilemiyor" in result.lower()


# ---------------------------------------------------------------------------
# build_analysis_context
# ---------------------------------------------------------------------------


async def test_build_analysis_context_success():
    builder = _make_builder()

    mock_analiz_repo = MagicMock()
    mock_analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=31.8)

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_all = AsyncMock(return_value=[{"id": 1}, {"id": 2}, {"id": 3}])

    mock_rankings = {
        "genel": [
            {"sira": 1, "ad": "Ali", "puan": 90.0, "derece": "A"},
            {"sira": 2, "ad": "Mehmet", "puan": 80.0, "derece": "B"},
        ],
        "verimlilik": [],
        "tutarlilik": [],
    }
    with (
        patch.object(
            type(builder),
            "analiz_repo",
            new_callable=lambda: property(lambda self: mock_analiz_repo),
        ),
        patch.object(
            type(builder),
            "arac_repo",
            new_callable=lambda: property(lambda self: mock_arac_repo),
        ),
        patch(
            "v2.modules.driver.domain.evaluation.get_rankings",
            AsyncMock(return_value=mock_rankings),
        ),
    ):
        result = await builder.build_analysis_context()

    assert "31.8" in result
    assert "3" in result  # 3 araç
    assert "Ali" in result


async def test_build_analysis_context_filo_none_defaults_to_32():
    builder = _make_builder()

    mock_analiz_repo = MagicMock()
    mock_analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=None)

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_all = AsyncMock(return_value=[])

    with (
        patch.object(
            type(builder),
            "analiz_repo",
            new_callable=lambda: property(lambda self: mock_analiz_repo),
        ),
        patch.object(
            type(builder),
            "arac_repo",
            new_callable=lambda: property(lambda self: mock_arac_repo),
        ),
        patch(
            "v2.modules.driver.domain.evaluation.get_rankings",
            AsyncMock(return_value={"genel": []}),
        ),
    ):
        result = await builder.build_analysis_context()

    assert "32.0" in result


async def test_build_analysis_context_exception_returns_fallback():
    builder = _make_builder()

    mock_analiz_repo = MagicMock()
    mock_analiz_repo.get_filo_ortalama_tuketim = AsyncMock(
        side_effect=RuntimeError("DB error")
    )

    with patch.object(
        type(builder),
        "analiz_repo",
        new_callable=lambda: property(lambda self: mock_analiz_repo),
    ):
        result = await builder.build_analysis_context()

    assert "erişilemiyor" in result.lower()


# ---------------------------------------------------------------------------
# build_full_context
# ---------------------------------------------------------------------------


async def test_build_full_context_system_only():
    builder = _make_builder()

    with patch.object(
        builder,
        "build_system_context",
        new_callable=AsyncMock,
        return_value="## Sistem",
    ):
        result = await builder.build_full_context()

    assert "## Sistem" in result


async def test_build_full_context_with_arac_and_sofor():
    builder = _make_builder()

    with (
        patch.object(
            builder, "build_system_context", new_callable=AsyncMock, return_value="SYS"
        ),
        patch.object(
            builder,
            "build_vehicle_context",
            new_callable=AsyncMock,
            return_value="ARAC",
        ),
        patch.object(
            builder,
            "build_driver_context",
            new_callable=AsyncMock,
            return_value="SOFOR",
        ),
    ):
        result = await builder.build_full_context(arac_id=1, sofor_id=2)

    assert "SYS" in result
    assert "ARAC" in result
    assert "SOFOR" in result


async def test_build_full_context_with_analysis():
    builder = _make_builder()

    with (
        patch.object(
            builder, "build_system_context", new_callable=AsyncMock, return_value="SYS"
        ),
        patch.object(
            builder,
            "build_analysis_context",
            new_callable=AsyncMock,
            return_value="ANALIZ",
        ),
    ):
        result = await builder.build_full_context(include_analysis=True)

    assert "ANALIZ" in result


async def test_build_full_context_truncates_long_output():
    builder = _make_builder()
    long_text = "X" * (builder.MAX_CONTEXT_CHARS + 1000)

    with patch.object(
        builder, "build_system_context", new_callable=AsyncMock, return_value=long_text
    ):
        result = await builder.build_full_context()

    assert len(result) <= builder.MAX_CONTEXT_CHARS + 100  # truncation marker overhead
    assert "kırpıldı" in result


# ---------------------------------------------------------------------------
# get_context_builder — singleton
# ---------------------------------------------------------------------------


def test_get_context_builder_returns_singleton():
    import app.core.ai.context_builder as mod

    # Reset singleton
    mod._context_builder = None

    c1 = get_context_builder()
    c2 = get_context_builder()
    assert c1 is c2
    assert isinstance(c1, ContextBuilder)

    # cleanup
    mod._context_builder = None
