"""Feature A — Şoför Koçluk Modülü Pydantic şemaları.

Tasarım kararları (`docs/superpowers/plans/2026-05-22-feature-a-driver-coaching-mini-plan-v2.md`):
- LLM'e gönderilen prompt'ta ad-soyad/plaka/telegram_id YOK (anonim-tam).
- Response objesi ad-soyad'ı dahili sayfa render'ı için tutar (Groq'a gitmez).
- Tüm string alanlar max_length ile sınırlı (LLM hallucination bütçesi).
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CoachingCategory = Literal[
    "yakit_yonetimi",
    "guzergah_tercihi",
    "sofor_pratigi",
    "diger",
]

CoachingPriority = Literal["low", "medium", "high"]
CoachingSource = Literal["llm", "fallback"]


class CoachingInsightItem(BaseModel):
    """LLM'in ürettiği tek koçluk önerisi."""

    category: CoachingCategory
    pattern: str = Field(
        ..., max_length=240, description="Tespit edilen davranış kalıbı"
    )
    evidence: List[str] = Field(default_factory=list, max_length=5)
    suggestion: str = Field(
        ..., max_length=480, description="Eyleme dönüştürülebilir öneri"
    )
    impact_score: float = Field(
        0.0, ge=0, le=1, description="Önerilen aksiyon etkisi (0..1)"
    )


class CoachingInsightsResponse(BaseModel):
    """`/coaching/{id}/insights` response payload'u."""

    sofor_id: int
    ad_soyad: str = Field(..., description="Yalnız UI gösterimi için; LLM'e gitmedi")
    headline: str = Field(..., max_length=200)
    priority: CoachingPriority
    insights: List[CoachingInsightItem]
    generated_at: str = Field(..., description="ISO datetime")
    source: CoachingSource

    model_config = ConfigDict(from_attributes=True)


class SendCoachingRequest(BaseModel):
    """`POST /coaching/{id}/send` body."""

    message: str = Field(..., min_length=10, max_length=1000)
    channel: Literal["telegram"] = "telegram"
    insight_category: Optional[CoachingCategory] = Field(
        None, description="A.5 telemetri için kategori etiketi"
    )


class SendCoachingResponse(BaseModel):
    sent: bool
    delivery_id: Optional[int] = None
    channel: str
    sent_at: str


class CoachingEffectivenessResponse(BaseModel):
    """`/coaching/effectiveness?days=N` response — A.5."""

    window_days: int
    total_sent: int
    total_evaluated: int
    improved: int
    worsened: int
    improve_rate: Optional[float] = Field(None, ge=0, le=1)
    avg_score_delta_pct: Optional[float] = None
    caveat: str = Field(
        ...,
        description="UI'da açıkça gösterilecek istatistiksel uyarı",
    )
