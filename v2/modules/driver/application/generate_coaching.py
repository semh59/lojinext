"""Feature A — DriverCoachingEngine.

Şoför × anomali + skor + güzergah profili → Türkçe kategorize koçluk
önerileri. Groq LLM kullanır; LLM hata verirse rule-based fallback.

PII Politikası (v2 plan Q1):
- LLM'e gönderilen prompt'ta plaka, ad-soyad, telegram_id veya sofor_id
  GİTMEZ. Sadece anonim sayısal/kategorik özetler.

Sınıf olarak kalma gerekçesi (B.1 istisnası — RouteSimulator/
LokasyonHydrator ile aynı sınıf): constructor-injected client bağımlılıkları
(``groq``, ``anomaly_detector``) olan tek-cohesive-pipeline (``generate_coaching``
tek giriş noktası). CRUD-benzeri bir servis değil.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.ai.groq_service import get_groq_service
from app.database.unit_of_work import UnitOfWork
from v2.modules.anomaly.public import get_anomaly_detector
from v2.modules.driver.application.get_route_profile import get_route_profile_sofor
from v2.modules.driver.application.get_score import get_score_breakdown_sofor
from v2.modules.driver.schemas import (
    CoachingCategory,
    CoachingInsightItem,
    CoachingInsightsResponse,
    CoachingPriority,
)

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Sen LojiNext filo yönetim sisteminin uzman koçluk asistanısın.
Görevin: TIR şoförleri için yakıt verimliliği, güzergah seçimi ve sürüş
alışkanlıkları hakkında somut, eyleme dönüştürülebilir öneriler üretmek.

KURALLAR:
1. Yanıtın yalnızca geçerli JSON olsun (markdown code fence YOK).
2. Şema: {"headline": str, "priority": "low"|"medium"|"high", "insights": [{"category": str, "pattern": str, "evidence": [str], "suggestion": str, "impact_score": 0..1}]}
3. headline ≤ 200 karakter, suggestion ≤ 480 karakter.
4. category SADECE şu değerlerden biri: yakit_yonetimi, guzergah_tercihi, sofor_pratigi, diger.
5. priority: anomali sapma % toplamı >40 ise "high", >20 ise "medium", aksi "low".
6. Sayısal kanıtları evidence'a sayı + birim ile koy ("28.5 L/100km", "+%18 sapma").
7. Şoföre kişisel ifade ASLA kullanma (isim/plaka/ID yok) — sadece davranışsal kalıptan bahset.
8. Türkçe, profesyonel, suçlayıcı olmayan ton.
9. Eğer veri yetersizse: insights boş array, headline="Şu an için iyileştirme önerisi yok".
"""  # noqa: E501


_LABEL_TO_CATEGORY = {
    "yakit_yonetimi": "yakit_yonetimi",
    "guzergah_tercihi": "guzergah_tercihi",
    "sofor_pratigi": "sofor_pratigi",
    "diger": "diger",
}

_FALLBACK_SUGGESTION = {
    "yakit_yonetimi": "Rölantide bekleme süresini azaltın; soğuk-start sayısını düşürün.",
    "guzergah_tercihi": "Otoyol ağırlıklı rotaları tercih edin; şehir içi mesafeyi minimize edin.",
    "sofor_pratigi": "Hız sınırlarına uyum + vites geçişlerinde ekonomik bant.",
    "diger": "Sefer kayıtlarını gözden geçirin ve operasyon yöneticisi ile görüşün.",
}


class DriverCoachingEngine:
    """Stateless engine — paylaşılan singleton olarak kullanılır."""

    def __init__(self) -> None:
        self.groq = get_groq_service()
        self.detector = get_anomaly_detector()

    async def generate_coaching(self, sofor_id: int) -> CoachingInsightsResponse:
        """Ana giriş noktası. LLM hatası (LLMProviderError) generate_coaching
        içindeki try/except tarafından yakalanır — dışarıya asla fırlamaz,
        _fallback_response()'a düşer."""
        async with UnitOfWork() as uow:
            sofor = await uow.sofor_repo.get_by_id(sofor_id)
            if not sofor:
                raise ValueError("Şoför bulunamadı")
            score = await get_score_breakdown_sofor(sofor_id, uow=uow)
            route_profile = await get_route_profile_sofor(sofor_id, uow=uow)
        # sofor_id filter: anomaly_detector.get_recent_anomalies sefer
        # JOIN üzerinden seferler.sofor_id'ye filtre uygular. Bu sayede
        # başka şoförün anomali örüntüleri Şoför A'nın coaching prompt'una
        # sızmıyor (HATA 5 — LOJINEXT_v7 raporu).
        anomalies = await self.detector.get_recent_anomalies(
            days=30, status="open", sofor_id=sofor_id
        )

        categorized = self._categorize_anomalies(anomalies)

        has_any = any(items for items in categorized.values())
        if not has_any and int(score.get("trip_count") or 0) < 5:
            return self._empty_response(sofor_id, sofor.get("ad_soyad", ""))

        prompt = self._build_prompt(score, route_profile, categorized)

        try:
            raw = await self.groq.chat(
                user_message=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=1024,
            )
            parsed = self._parse_response(raw)
            return CoachingInsightsResponse(
                sofor_id=sofor_id,
                ad_soyad=sofor.get("ad_soyad", ""),
                generated_at=datetime.now(timezone.utc).isoformat(),
                source="llm",
                **parsed,
            )
        except Exception as exc:
            logger.warning(
                "Coaching LLM failed for sofor %s: %s — falling back", sofor_id, exc
            )
            return self._fallback_response(
                sofor_id, sofor.get("ad_soyad", ""), categorized, score
            )

    # ── Pure-py helpers ────────────────────────────────────────────────────

    def _categorize_anomalies(
        self, anomalies: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Tipe + sapma yüzdesine göre 4 kategoriye ayır."""
        buckets: Dict[str, List[Dict[str, Any]]] = {
            "yakit_yonetimi": [],
            "guzergah_tercihi": [],
            "sofor_pratigi": [],
            "diger": [],
        }
        for a in anomalies:
            tip = a.get("tip") or ""
            sapma = float(a.get("sapma_yuzde") or 0)
            if tip == "tuketim":
                if abs(sapma) > 30:
                    buckets["sofor_pratigi"].append(a)
                else:
                    buckets["yakit_yonetimi"].append(a)
            elif tip == "maliyet":
                buckets["yakit_yonetimi"].append(a)
            elif tip == "sefer":
                buckets["guzergah_tercihi"].append(a)
            else:
                buckets["diger"].append(a)
        return buckets

    def _build_prompt(
        self,
        score: Dict[str, Any],
        route_profile: Dict[str, Any],
        categorized: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """LLM'e gönderilecek user message. KESİNLİKLE PII içermez.

        - Şoför ID / ad_soyad / plaka YOK
        - Sadece sayısal + kategorik veri
        """
        lines: List[str] = [
            "Filo Şoför Profili (anonim):",
            f"- Hibrit skor: {score.get('total', 0)} "
            f"(manuel={score.get('manual', 0)}, otomatik={score.get('auto', 0)})",
            f"- Geçen yıl tamamlanan sefer: {int(score.get('trip_count') or 0)}",
            f"- Ortalama tüketim: {score.get('avg_consumption', 0)} L/100km",
        ]

        profiles = route_profile.get("profiles") or []
        active_profiles = [p for p in profiles if int(p.get("trip_count") or 0) > 0]
        if active_profiles:
            lines.append("")
            lines.append("Güzergah Tipi Performansı:")
            for p in active_profiles:
                lines.append(
                    f"- {p['label']}: {p['trip_count']} sefer, "
                    f"sapma %{float(p.get('deviation_pct') or 0):+.1f}"
                )
            best = route_profile.get("best_route_type")
            if best:
                lines.append(f"En iyi performans gösterilen tip: {best}")

        any_anom = any(items for items in categorized.values())
        if any_anom:
            lines.append("")
            lines.append("Son 30 günün açık anomalileri (kategori bazlı):")
            for cat, items in categorized.items():
                if not items:
                    continue
                avg_dev = sum(
                    abs(float(i.get("sapma_yuzde") or 0)) for i in items
                ) / len(items)
                lines.append(
                    f"- {cat}: {len(items)} adet, ortalama sapma %{avg_dev:.1f}"
                )

        lines.append("")
        lines.append(
            "Görev: Yukarıdaki verilere bakarak şema kurallarına uygun JSON "
            "formatında 1-4 insight üret. Veri yetersizse insights=[] dön."
        )
        return "\n".join(lines)

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """LLM çıktısını JSON'a parse + Pydantic doğrulama."""
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```\s*$",
            "",
            raw.strip(),
            flags=re.MULTILINE,
        )
        data = json.loads(cleaned)
        raw_insights = data.get("insights") or []

        validated: List[CoachingInsightItem] = []
        for item in raw_insights:
            cat = item.get("category")
            if cat not in _LABEL_TO_CATEGORY:
                cat = "diger"
            validated.append(
                CoachingInsightItem(
                    category=cat,  # type: ignore[arg-type]
                    pattern=str(item.get("pattern", ""))[:240],
                    evidence=[str(e)[:120] for e in (item.get("evidence") or [])][:5],
                    suggestion=str(item.get("suggestion", ""))[:480],
                    impact_score=max(
                        0.0, min(1.0, float(item.get("impact_score") or 0))
                    ),
                )
            )

        priority_raw = str(data.get("priority", "low")).lower()
        priority: CoachingPriority = (
            priority_raw if priority_raw in ("low", "medium", "high") else "low"  # type: ignore[assignment]
        )
        return {
            "headline": str(data.get("headline", ""))[:200],
            "priority": priority,
            "insights": validated,
        }

    def _empty_response(self, sofor_id: int, ad_soyad: str) -> CoachingInsightsResponse:
        return CoachingInsightsResponse(
            sofor_id=sofor_id,
            ad_soyad=ad_soyad,
            headline="Şu an için iyileştirme önerisi yok",
            priority="low",
            insights=[],
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="fallback",
        )

    def _fallback_response(
        self,
        sofor_id: int,
        ad_soyad: str,
        categorized: Dict[str, List[Dict[str, Any]]],
        score: Dict[str, Any],
    ) -> CoachingInsightsResponse:
        """LLM yokken kullanılır — rule-based özet."""
        insights: List[CoachingInsightItem] = []
        total_dev = 0.0
        for cat, items in categorized.items():
            if not items:
                continue
            cat_sum = sum(abs(float(a.get("sapma_yuzde") or 0)) for a in items)
            avg_dev = cat_sum / len(items)
            total_dev += cat_sum
            cat_key: CoachingCategory = cat  # type: ignore[assignment]
            insights.append(
                CoachingInsightItem(
                    category=cat_key,
                    pattern=f"{len(items)} adet anomali, ortalama %{avg_dev:.0f} sapma",
                    evidence=[
                        f"{len(items)} olay",
                        f"ort. %{avg_dev:.0f} sapma",
                    ],
                    suggestion=_FALLBACK_SUGGESTION.get(
                        cat_key, _FALLBACK_SUGGESTION["diger"]
                    ),
                    impact_score=min(1.0, avg_dev / 50.0),
                )
            )

        priority: CoachingPriority = (
            "high" if total_dev > 40 else "medium" if total_dev > 20 else "low"
        )
        headline = (
            f"Skor {score.get('total', 0):.2f} — "
            f"{len(insights)} alanda iyileştirme önerisi"
            if insights
            else "Şu an için kritik anomali yok"
        )
        return CoachingInsightsResponse(
            sofor_id=sofor_id,
            ad_soyad=ad_soyad,
            headline=headline[:200],
            priority=priority,
            insights=insights,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="fallback",
        )


_engine_singleton: DriverCoachingEngine | None = None
_engine_lock = threading.Lock()


def get_driver_coaching_engine() -> DriverCoachingEngine:
    """Thread-safe singleton accessor (double-checked locking).

    ml_probe.py'deki kalıbı takip eder. FastAPI async worker'larda
    düşük ihtimal, yine de iki concurrent çağrı race'i engellenir.
    """
    global _engine_singleton
    if _engine_singleton is None:
        with _engine_lock:
            if _engine_singleton is None:
                _engine_singleton = DriverCoachingEngine()
    return _engine_singleton
