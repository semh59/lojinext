"""Feature B — Yakıt Hırsızlığı Tespit + Soruşturma Pydantic şemaları.

Tasarım kararları (v3 plan):
- Tüm enum'lar Literal — DB string column ile birebir
- Pii politikası: classifier `factors` listesi sadece sayısal/kategorik
  açıklama içerir, plaka/isim YOK (test ile doğrulanır)
- max_length sınırları LLM/UI hallucination bütçesini sınırlar
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SuspicionLevel = Literal["low", "medium", "high", "unknown"]
InvestigationStatus = Literal["open", "assigned", "investigating", "resolved", "closed"]
ResolutionType = Literal["real_theft", "false_alarm", "data_error", "inconclusive"]


class TheftClassification(BaseModel):
    """B.1 — classifier çıktısı."""

    anomaly_id: int
    suspicion_score: float = Field(..., ge=0, le=1, description="0..1 normalize")
    suspicion_level: SuspicionLevel
    factors: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="İnsan-okur açıklama listesi (PII YOK)",
    )
    suggested_action: str = Field(..., max_length=240)


class InvestigationCreate(BaseModel):
    anomaly_id: int = Field(..., gt=0)
    initial_notes: Optional[str] = Field(None, max_length=2000)


class InvestigationUpdate(BaseModel):
    """Tüm alanlar opsiyonel — partial update."""

    status: Optional[InvestigationStatus] = None
    assigned_to_user_id: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=4000)
    resolution_type: Optional[ResolutionType] = None
    evidence_files: Optional[List[str]] = Field(None, max_length=10)


class InvestigationResponse(BaseModel):
    id: int
    anomaly_id: int
    status: InvestigationStatus
    suspicion_score: Optional[float] = None
    suspicion_level: Optional[SuspicionLevel] = None
    assigned_to_user_id: Optional[int] = None
    notes: Optional[str] = None
    resolution_type: Optional[ResolutionType] = None
    evidence_files: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    # JOIN'den gelen meta (Optional çünkü kaynak_tip != 'sefer' olabilir)
    plaka: Optional[str] = None
    sofor_adi: Optional[str] = None
    sapma_yuzde: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class PatternMatch(BaseModel):
    sofor_id: Optional[int] = None
    sofor_adi: Optional[str] = None
    arac_id: Optional[int] = None
    plaka: Optional[str] = None
    occurrence_count: int = Field(..., ge=1)
    avg_suspicion_score: float = Field(..., ge=0, le=1)
    last_seen: datetime
