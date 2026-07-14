"""Feature A.1 — DriverCoachingEngine unit testleri.

Engine'in fonksiyonel davranışı + PII regex doğrulaması.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database.unit_of_work import UnitOfWork
from v2.modules.driver.application.generate_coaching import DriverCoachingEngine
from v2.modules.driver.schemas import CoachingInsightsResponse

# ── Test fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _stop_all_patches_after_test():
    """_make_engine içindeki patcher.start() çağrılarını test bitiminde
    geri al. Aksi halde SoforService global olarak _FakeService'e patched
    kalıyor ve sonraki suite test'leri TypeError veriyor (event_bus arg)."""
    yield
    patch.stopall()


SOFOR_RECORD: Dict[str, Any] = {"id": 7, "ad_soyad": "Ali Veli", "aktif": True}

SCORE_OK: Dict[str, Any] = {
    "sofor_id": 7,
    "ad_soyad": "Ali Veli",
    "manual": 1.2,
    "manual_weight": 0.4,
    "auto": 1.08,
    "auto_weight": 0.6,
    "total": 1.13,
    "trip_count": 12,
    "avg_consumption": 27.8,
    "target_reference": 30.0,
    "has_trips": True,
}

SCORE_NO_TRIPS: Dict[str, Any] = {
    **SCORE_OK,
    "trip_count": 0,
    "has_trips": False,
}

ROUTE_PROFILE_OK: Dict[str, Any] = {
    "sofor_id": 7,
    "ad_soyad": "Ali Veli",
    "min_trips_for_best": 5,
    "best_route_type": "highway_dominant",
    "profiles": [
        {
            "route_type": "highway_dominant",
            "label": "Otoyol Ağırlıklı",
            "trip_count": 12,
            "avg_actual": 27.5,
            "avg_predicted": 30.0,
            "deviation_pct": -8.3,
        }
    ],
}


def _mk_anomaly(tip: str, sapma: float) -> Dict[str, Any]:
    return {"id": 1, "tip": tip, "sapma_yuzde": sapma, "severity": "high"}


# ── Engine ile çalışan mock kurulumu ──────────────────────────────────────


def _make_engine(
    groq_response: str | None = None,
    groq_exc: Exception | None = None,
    anomalies: List[Dict[str, Any]] | None = None,
    score: Dict[str, Any] | None = None,
    route: Dict[str, Any] | None = None,
    sofor: Dict[str, Any] | None = None,
) -> DriverCoachingEngine:
    """Engine'i tüm dış bağımlılıklarla mock'lar."""
    engine = DriverCoachingEngine()
    # Groq
    if groq_exc is not None:
        engine.groq.chat = AsyncMock(side_effect=groq_exc)  # type: ignore[method-assign]
    else:
        engine.groq.chat = AsyncMock(return_value=groq_response or "{}")  # type: ignore[method-assign]
    # AnomalyDetector
    engine.detector.get_recent_anomalies = AsyncMock(  # type: ignore[method-assign]
        return_value=anomalies if anomalies is not None else []
    )

    # get_score_breakdown_sofor + get_route_profile_sofor free-function mock
    # (eski SoforService.get_score_breakdown/get_route_profile sınıfı silindi;
    # engine artık bu iki free function'ı doğrudan import edip çağırıyor).
    patcher_score = patch(
        "v2.modules.driver.application.generate_coaching.get_score_breakdown_sofor",
        AsyncMock(return_value=score or SCORE_OK),
    )
    patcher_score.start()

    patcher_route = patch(
        "v2.modules.driver.application.generate_coaching.get_route_profile_sofor",
        AsyncMock(return_value=route or ROUTE_PROFILE_OK),
    )
    patcher_route.start()

    # UoW patch
    fake_uow = MagicMock()
    fake_uow.sofor_repo = MagicMock()
    fake_uow.sofor_repo.get_by_id = AsyncMock(return_value=sofor or SOFOR_RECORD)

    patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=fake_uow)).start()
    patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)).start()

    return engine


# ── Senaryolar ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_when_no_data():
    """Anomali 0 + sefer<5 → empty fallback."""
    engine = _make_engine(
        anomalies=[],
        score=SCORE_NO_TRIPS,
    )
    res = await engine.generate_coaching(7)
    assert isinstance(res, CoachingInsightsResponse)
    assert res.source == "fallback"
    assert res.insights == []
    assert "iyileştirme önerisi yok" in res.headline.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_success_parses_json():
    """Geçerli JSON cevabı parse edilir, source='llm'."""
    raw = (
        '{"headline":"Test başlık","priority":"medium",'
        '"insights":[{"category":"yakit_yonetimi","pattern":"X","evidence":["a"],'
        '"suggestion":"Y","impact_score":0.5}]}'
    )
    engine = _make_engine(
        groq_response=raw,
        anomalies=[_mk_anomaly("tuketim", 18)],
    )
    res = await engine.generate_coaching(7)
    assert res.source == "llm"
    assert res.headline == "Test başlık"
    assert res.priority == "medium"
    assert len(res.insights) == 1
    assert res.insights[0].category == "yakit_yonetimi"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_markdown_fence_stripped():
    """Bazı LLM'ler ```json fence ekler — temizlenmeli."""
    raw = '```json\n{"headline":"H","priority":"low","insights":[]}\n```'
    engine = _make_engine(
        groq_response=raw,
        anomalies=[_mk_anomaly("tuketim", 5)],
    )
    res = await engine.generate_coaching(7)
    assert res.source == "llm"
    assert res.headline == "H"
    assert res.insights == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_exception_uses_fallback():
    """Groq exception fırlatırsa rule-based fallback'a düşülür."""
    engine = _make_engine(
        groq_exc=TimeoutError("groq timeout"),
        anomalies=[_mk_anomaly("tuketim", 35)],  # Yüksek sapma → high priority
    )
    res = await engine.generate_coaching(7)
    assert res.source == "fallback"
    # Yüksek sapma anomali → sofor_pratigi kategorisinde insight bekleriz
    cats = [i.category for i in res.insights]
    assert "sofor_pratigi" in cats


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_invalid_json_uses_fallback():
    """Geçersiz JSON döndürürse fallback'e geçilir."""
    engine = _make_engine(
        groq_response="Bu JSON değil, sadece bir cümle.",
        anomalies=[_mk_anomaly("maliyet", 25)],
    )
    res = await engine.generate_coaching(7)
    assert res.source == "fallback"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_categorization_high_deviation_goes_to_practice():
    """Tüketim sapması >30% → sofor_pratigi."""
    engine = _make_engine()
    anomalies = [_mk_anomaly("tuketim", 35)]
    buckets = engine._categorize_anomalies(anomalies)
    assert len(buckets["sofor_pratigi"]) == 1
    assert len(buckets["yakit_yonetimi"]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_categorization_low_deviation_stays_yakit_yonetimi():
    """Tüketim sapması ≤30% → yakit_yonetimi."""
    engine = _make_engine()
    anomalies = [_mk_anomaly("tuketim", 12)]
    buckets = engine._categorize_anomalies(anomalies)
    assert len(buckets["yakit_yonetimi"]) == 1
    assert len(buckets["sofor_pratigi"]) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prompt_contains_no_pii():
    """Q1 kararı: LLM prompt'unda plaka, ad-soyad, telegram_id, sofor_id yok."""
    engine = DriverCoachingEngine()
    prompt = engine._build_prompt(
        SCORE_OK,
        ROUTE_PROFILE_OK,
        {
            "yakit_yonetimi": [_mk_anomaly("tuketim", 15)],
            "guzergah_tercihi": [],
            "sofor_pratigi": [],
            "diger": [],
        },
    )

    # İsim/soyisim yok
    assert "Ali" not in prompt
    assert "Veli" not in prompt
    # Plaka formatı yok: "34 ABC 1234" benzeri eşleşme
    assert not re.search(r"\d{2}\s+[A-Z]{2,3}\s+\d{2,4}", prompt)
    # telegram referansı yok
    assert "telegram" not in prompt.lower()
    # Şoför id yok (id sözcüğü ve sayısal id birlikte)
    assert "Şoför ID" not in prompt
    assert "sofor_id" not in prompt.lower()
