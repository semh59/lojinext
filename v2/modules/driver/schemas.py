"""Driver + coaching Pydantic şemaları.

Güvenlik kontrolleri:
- İsim validasyonu (Türkçe karakter desteği)
- Telefon maskeleme (PII koruması)
- XSS koruması

Coaching tasarım kararları
(``docs/superpowers/plans/2026-05-22-feature-a-driver-coaching-mini-plan-v2.md``):
- LLM'e gönderilen prompt'ta ad-soyad/plaka/telegram_id YOK (anonim-tam).
- Response objesi ad-soyad'ı dahili sayfa render'ı için tutar (Groq'a gitmez).
- Tüm string alanlar max_length ile sınırlı (LLM hallucination bütçesi).
"""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from v2.modules.shared_kernel.schemas.validators import (
    mask_phone,
    sanitize_string,
    validate_phone,
    validate_safe_string,
)

# ── Driver ────────────────────────────────────────────────────────────────


class SoforBase(BaseModel):
    """Şoför base model - ortak alanlar."""

    ad_soyad: str = Field(..., min_length=3, max_length=100)
    telefon: Optional[str] = Field(None, max_length=20, description="Telefon numarası")

    @field_validator("telefon")
    @classmethod
    def validate_phone_field(cls, v: Optional[str]) -> Optional[str]:
        """Telefon formatı kontrolü."""
        return validate_phone(v)

    ise_baslama: Optional[date] = None
    ehliyet_sinifi: Literal["B", "C", "D", "E", "G", "CE", "D1E"] = Field("E")
    score: float = Field(1.0, ge=0.1, le=2.0, description="Sonuç puanı (0.1-2.0)")
    manual_score: float = Field(
        1.0, ge=0.1, le=2.0, description="Manuel değerlendirme puanı"
    )
    aktif: bool = True
    notlar: Optional[str] = Field(None, max_length=500)

    @field_validator("ad_soyad", mode="before")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """İsim sanitize ve title case."""
        if isinstance(v, str):
            v = sanitize_string(v)
            # Turkish-aware title case: 'i' → 'İ' (not 'I') at word start
            v = " ".join(
                ("İ" if w[0] == "i" else "I" if w[0] == "ı" else w[0].upper())
                + w[1:].lower()
                for w in v.split()
                if w
            )
        return v

    @field_validator("telefon", mode="before")
    @classmethod
    def sanitize_phone(cls, v: Optional[str]) -> Optional[str]:
        """Telefon sanitize."""
        if isinstance(v, str):
            v = sanitize_string(v)
        return v

    @field_validator("notlar", mode="before")
    @classmethod
    def validate_notlar(cls, v: Optional[str]) -> Optional[str]:
        """Notlar alanı XSS koruması."""
        return validate_safe_string(v)


class SoforCreate(SoforBase):
    """Şoför oluşturma şeması."""

    telegram_id: Optional[str] = Field(None, max_length=50)


class SoforUpdate(BaseModel):
    """Şoför güncelleme şeması - tüm alanlar optional."""

    ad_soyad: Optional[str] = Field(None, min_length=3, max_length=100)
    telefon: Optional[str] = Field(None, max_length=20)
    ise_baslama: Optional[date] = None
    ehliyet_sinifi: Optional[Literal["B", "C", "D", "E", "G", "CE", "D1E"]] = None
    score: Optional[float] = Field(None, ge=0.1, le=2.0)
    manual_score: Optional[float] = Field(None, ge=0.1, le=2.0)
    hiz_disiplin_skoru: Optional[float] = Field(
        None, ge=0.1, le=2.0, description="Hız Disiplin Skoru"
    )
    agresif_surus_faktoru: Optional[float] = Field(
        None, ge=0.1, le=2.0, description="Agresif Sürüş Faktörü"
    )
    aktif: Optional[bool] = None
    notlar: Optional[str] = Field(None, max_length=500)
    telegram_id: Optional[str] = Field(None, max_length=50)

    @field_validator("ad_soyad", mode="before")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        """İsim sanitize ve title case."""
        if isinstance(v, str):
            v = sanitize_string(v)
            v = " ".join(
                ("İ" if w[0] == "i" else "I" if w[0] == "ı" else w[0].upper())
                + w[1:].lower()
                for w in v.split()
                if w
            )
        return v

    @field_validator("telefon")
    @classmethod
    def validate_phone_field(cls, v: Optional[str]) -> Optional[str]:
        """Telefon formatı kontrolü."""
        return validate_phone(v)

    @field_validator("notlar", mode="before")
    @classmethod
    def validate_notlar(cls, v: Optional[str]) -> Optional[str]:
        """Notlar alanı XSS koruması."""
        return validate_safe_string(v)

    @field_validator("score", "manual_score")
    @classmethod
    def validate_scores(cls, v: Optional[float]) -> Optional[float]:
        """Puan aralık kontrolü."""
        if v is not None and (v < 0.1 or v > 2.0):
            raise ValueError("Puan 0.1-2.0 arasında olmalı")
        return v


class SoforResponse(SoforBase):
    """Şoför response şeması - API çıktısı."""

    id: int
    ad_soyad: str = Field(..., description="Permissive name")
    ise_baslama: Optional[date] = None
    created_at: datetime
    telegram_id: Optional[str] = None

    ehliyet_sinifi: str = Field("E")

    # Raw phone excluded from JSON output; only telefon_masked is serialized.
    telefon: Optional[str] = Field(default=None, exclude=True, max_length=20)

    @field_validator("ehliyet_sinifi", mode="before")
    @classmethod
    def validate_license_class(cls, v: Optional[str]) -> str:
        """Ehliyet sınıfı bozuksa (örn: lowercase) düzelt veya varsayılan ata."""
        valid_classes = {"B", "C", "D", "E", "G", "CE", "D1E"}
        if isinstance(v, str):
            v_upper = v.upper().strip()
            if v_upper in valid_classes:
                return v_upper
        return "E"

    @computed_field
    @property
    def telefon_masked(self) -> Optional[str]:
        """Maskelenmiş telefon numarası."""
        return mask_phone(self.telefon)

    @field_validator("ad_soyad", mode="before")
    @classmethod
    def heal_name(cls, v: object) -> str:
        """Kısa veya bozuk isimleri düzeltir."""
        if not v:
            return "İSİMSİZ SÜRÜCÜ"
        name = str(v).strip()
        if len(name) < 3:
            return f"{name} (Kısa İsim)"
        return name

    @field_validator("manual_score", "score", mode="before")
    @classmethod
    def heal_scores(cls, v: object) -> float:
        """NULL veya bozuk puanları 1.0 olarak düzeltir."""
        if v is None:
            return 1.0
        try:
            val = float(v)  # type: ignore[arg-type]
            if 0.1 <= val <= 2.0:
                return val
            return 1.0
        except (ValueError, TypeError, Exception):
            return 1.0

    @field_validator("ise_baslama", mode="before")
    @classmethod
    def heal_date(cls, v: object) -> Optional[date]:
        """Bozuk tarihleri null yapar."""
        if not v:
            return None
        if isinstance(v, date):
            return v
        try:
            return date.fromisoformat(str(v).split("T")[0])
        except (ValueError, TypeError, Exception):
            return None

    @field_validator("telefon", mode="before")
    @classmethod
    def heal_phone(cls, v: object) -> Optional[str]:
        """Boş/bozuk telefon numaralarını null yapar."""
        if not v or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            digits = "".join(filter(str.isdigit, v))
            if digits and 10 <= len(digits) <= 15:
                return v
        return None

    model_config = ConfigDict(from_attributes=True)


class DriverPerformanceSchema(BaseModel):
    """Sürücü Performans Karnesi (AI Analizli)"""

    safety_score: float = Field(..., ge=0, le=100, description="Güvenli Sürüş Puanı")
    eco_score: float = Field(..., ge=0, le=100, description="Ekonomik Sürüş Puanı")
    compliance_score: float = Field(
        ..., ge=0, le=100, description="Kurallara Uyum Puanı"
    )
    total_score: float = Field(
        ..., ge=0, le=100, description="Genel Performans Puanı (Ağırlıklı)"
    )
    trend: Literal["increasing", "decreasing", "stable"] = "stable"
    total_km: float = 0
    total_trips: int = 0


class DriverScoreBreakdownSchema(BaseModel):
    """XAI: hybrid score'un ağırlık kırılımı.

    Hesaplama: ``total = manual * manual_weight + auto * auto_weight``.
    Şu an manual_weight=0.4, auto_weight=0.6 (`calculate_hybrid_score`).
    `auto`, geçmiş seferlerden türetilir; sefer yoksa fallback `manual`.
    """

    sofor_id: int
    ad_soyad: str
    manual: float = Field(..., ge=0.1, le=2.0, description="Manuel verilen puan")
    manual_weight: float = Field(0.4, ge=0, le=1)
    auto: float = Field(..., ge=0.1, le=2.0, description="Otomatik (performans) puanı")
    auto_weight: float = Field(0.6, ge=0, le=1)
    total: float = Field(..., ge=0.1, le=2.0, description="Hibrit toplam")
    trip_count: int = Field(0, ge=0)
    avg_consumption: float = Field(0.0, ge=0)
    target_reference: float = Field(
        30.0, gt=0, description="Performans skorunda kullanılan referans L/100km"
    )
    has_trips: bool = Field(
        ..., description="auto skor gerçek sefer verisinden mi geldi"
    )


class DriverRouteProfileItemSchema(BaseModel):
    """Tek bir güzergah tipi için sürücü performans özeti."""

    route_type: Literal["highway_dominant", "mountain", "urban", "mixed"]
    label: str = Field(..., description="Türkçe gösterim adı")
    trip_count: int = Field(0, ge=0)
    avg_actual: float = Field(0.0, ge=0)
    avg_predicted: float = Field(0.0, ge=0)
    deviation_pct: float = Field(
        0.0, description="(actual-predicted)/predicted×100; negatif = tahminden iyi"
    )


class DriverRouteProfileSchema(BaseModel):
    """Şoför × 4 güzergah tipi profil özeti + en güçlü tip."""

    sofor_id: int
    ad_soyad: str
    profiles: list[DriverRouteProfileItemSchema]
    best_route_type: Optional[
        Literal["highway_dominant", "mountain", "urban", "mixed"]
    ] = Field(None, description="None → yeterli veri yok")
    min_trips_for_best: int = Field(5, ge=1)


# ── Coaching (Feature A) ────────────────────────────────────────────────────

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


# ─── Sürücü-filo istatistik response şeması (dalga 16 — eski app/schemas/api_responses.py'den taşındı) ───────


class DriverFleetStatsResponse(BaseModel):
    total: int
    active: int
