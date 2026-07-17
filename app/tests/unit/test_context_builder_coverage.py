"""
Unit tests for build_context free functions — targeting ≥70% coverage.

All service/repo calls are mocked; no DB, no network. B.1: eski
`ContextBuilder` sınıfı taşınırken free function'lara bölündü (dalga 12,
constructor'ı `pass` idi — anlamlı state yoktu), bu testler de class-mock'tan
free-function-mock'a çevrildi (patch hedefi
`v2.modules.ai_assistant.application.build_context.<fn>`).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.ai_assistant.application import build_context

pytestmark = pytest.mark.unit

MOD = "v2.modules.ai_assistant.application.build_context"


def _mock_report_service(stats: dict):
    return AsyncMock(return_value=stats)


def _mock_rag_engine(total_documents: int = 100):
    engine = MagicMock()
    engine.get_stats = MagicMock(return_value={"total_documents": total_documents})
    return engine


# ---------------------------------------------------------------------------
# build_system_context — happy path
# ---------------------------------------------------------------------------


async def test_build_system_context_returns_formatted_string():
    stats = {
        "aktif_arac": 10,
        "aktif_sofor": 8,
        "toplam_sefer": 500,
        "toplam_km": 250000,
        "filo_ortalama": 31.5,
    }

    with (
        patch(f"{MOD}._get_dashboard_summary", _mock_report_service(stats)),
        patch(f"{MOD}._get_rag_engine", return_value=_mock_rag_engine(42)),
    ):
        result = await build_context.build_system_context()

    assert "10" in result
    assert "8" in result
    assert "42" in result
    assert "31.5" in result


async def test_build_system_context_exception_returns_fallback():
    with patch(
        f"{MOD}._get_dashboard_summary",
        AsyncMock(side_effect=RuntimeError("DB down")),
    ):
        result = await build_context.build_system_context()

    assert "erişilemiyor" in result.lower() or "sistem" in result.lower()


# ---------------------------------------------------------------------------
# build_vehicle_context
# ---------------------------------------------------------------------------


async def test_build_vehicle_context_invalid_id_string_returns_error():
    result = await build_context.build_vehicle_context("bad")  # type: ignore
    assert "Geçersiz" in result


async def test_build_vehicle_context_invalid_id_zero_returns_error():
    result = await build_context.build_vehicle_context(0)
    assert "Geçersiz" in result


async def test_build_vehicle_context_arac_not_found_returns_error():
    mock_arac_repo = MagicMock()
    mock_arac_repo.get_by_id = AsyncMock(return_value=None)

    with patch(f"{MOD}._get_arac_repo", return_value=mock_arac_repo):
        result = await build_context.build_vehicle_context(1)

    assert "bulunamadı" in result


async def test_build_vehicle_context_success():
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

    # Mock Arac entity — patched at its source module (lazy import inside function)
    mock_arac_entity = MagicMock()
    mock_arac_entity.yas = 4
    mock_arac_entity.euro_sinifi = "Euro 6"
    mock_arac_entity.yas_faktoru = 1.02

    with (
        patch(f"{MOD}._get_arac_repo", return_value=mock_arac_repo),
        patch(f"{MOD}._get_sefer_repo", return_value=mock_sefer_repo),
        patch(f"{MOD}._get_yakit_repo", return_value=mock_yakit_repo),
        patch("app.core.entities.models.Arac", return_value=mock_arac_entity),
    ):
        result = await build_context.build_vehicle_context(1)

    assert "34 TIR 001" in result
    assert "VOLVO" in result


async def test_build_vehicle_context_exception_returns_fallback():
    mock_arac_repo = MagicMock()
    mock_arac_repo.get_by_id = AsyncMock(side_effect=RuntimeError("DB error"))

    with patch(f"{MOD}._get_arac_repo", return_value=mock_arac_repo):
        result = await build_context.build_vehicle_context(1)

    assert "erişilemiyor" in result.lower()


# ---------------------------------------------------------------------------
# build_driver_context
# ---------------------------------------------------------------------------


async def test_build_driver_context_invalid_id_returns_error():
    result = await build_context.build_driver_context(-1)
    assert "Geçersiz" in result


async def test_build_driver_context_no_evaluation_returns_error():
    with patch(
        "v2.modules.driver.public.evaluate_driver",
        AsyncMock(return_value=None),
    ):
        result = await build_context.build_driver_context(1)

    assert "yapılamadı" in result


async def test_build_driver_context_success():
    from v2.modules.driver.domain.evaluation import DereceEnum, TrendEnum

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
        "v2.modules.driver.public.evaluate_driver",
        AsyncMock(return_value=mock_eval),
    ):
        result = await build_context.build_driver_context(1)

    assert "Mehmet Kaya" in result
    assert "78.5" in result
    assert "Yakıt verimliliği iyi" in result


async def test_build_driver_context_exception_returns_fallback():
    with patch(
        "v2.modules.driver.public.evaluate_driver",
        AsyncMock(side_effect=RuntimeError("evaluate_driver error")),
    ):
        result = await build_context.build_driver_context(1)

    assert "erişilemiyor" in result.lower()


# ---------------------------------------------------------------------------
# build_analysis_context
# ---------------------------------------------------------------------------


async def test_build_analysis_context_success():
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
        patch(f"{MOD}._get_analiz_repo", return_value=mock_analiz_repo),
        patch(f"{MOD}._get_arac_repo", return_value=mock_arac_repo),
        patch(
            "v2.modules.driver.public.get_rankings",
            AsyncMock(return_value=mock_rankings),
        ),
    ):
        result = await build_context.build_analysis_context()

    assert "31.8" in result
    assert "3" in result  # 3 araç
    assert "Ali" in result


async def test_build_analysis_context_filo_none_defaults_to_32():
    mock_analiz_repo = MagicMock()
    mock_analiz_repo.get_filo_ortalama_tuketim = AsyncMock(return_value=None)

    mock_arac_repo = MagicMock()
    mock_arac_repo.get_all = AsyncMock(return_value=[])

    with (
        patch(f"{MOD}._get_analiz_repo", return_value=mock_analiz_repo),
        patch(f"{MOD}._get_arac_repo", return_value=mock_arac_repo),
        patch(
            "v2.modules.driver.public.get_rankings",
            AsyncMock(return_value={"genel": []}),
        ),
    ):
        result = await build_context.build_analysis_context()

    assert "32.0" in result


async def test_build_analysis_context_exception_returns_fallback():
    mock_analiz_repo = MagicMock()
    mock_analiz_repo.get_filo_ortalama_tuketim = AsyncMock(
        side_effect=RuntimeError("DB error")
    )

    with patch(f"{MOD}._get_analiz_repo", return_value=mock_analiz_repo):
        result = await build_context.build_analysis_context()

    assert "erişilemiyor" in result.lower()


# ---------------------------------------------------------------------------
# build_full_context
# ---------------------------------------------------------------------------


async def test_build_full_context_system_only():
    with patch(
        f"{MOD}.build_system_context",
        new_callable=AsyncMock,
        return_value="## Sistem",
    ):
        result = await build_context.build_full_context()

    assert "## Sistem" in result


async def test_build_full_context_with_arac_and_sofor():
    with (
        patch(
            f"{MOD}.build_system_context", new_callable=AsyncMock, return_value="SYS"
        ),
        patch(
            f"{MOD}.build_vehicle_context",
            new_callable=AsyncMock,
            return_value="ARAC",
        ),
        patch(
            f"{MOD}.build_driver_context",
            new_callable=AsyncMock,
            return_value="SOFOR",
        ),
    ):
        result = await build_context.build_full_context(arac_id=1, sofor_id=2)

    assert "SYS" in result
    assert "ARAC" in result
    assert "SOFOR" in result


async def test_build_full_context_with_analysis():
    with (
        patch(
            f"{MOD}.build_system_context", new_callable=AsyncMock, return_value="SYS"
        ),
        patch(
            f"{MOD}.build_analysis_context",
            new_callable=AsyncMock,
            return_value="ANALIZ",
        ),
    ):
        result = await build_context.build_full_context(include_analysis=True)

    assert "ANALIZ" in result


async def test_build_full_context_truncates_long_output():
    long_text = "X" * (build_context.MAX_CONTEXT_CHARS + 1000)

    with patch(
        f"{MOD}.build_system_context",
        new_callable=AsyncMock,
        return_value=long_text,
    ):
        result = await build_context.build_full_context()

    assert (
        len(result) <= build_context.MAX_CONTEXT_CHARS + 100
    )  # truncation marker overhead
    assert "kırpıldı" in result
