from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LokasyonBase(BaseModel):
    ad: Optional[str] = Field(
        None,
        max_length=150,
        description="Kullanıcı verdiği takma isim (örn. 'Sabah Kargosu — İST-BUR')",
    )
    cikis_yeri: str = Field(..., max_length=100)
    varis_yeri: str = Field(..., max_length=100)
    mesafe_km: float = Field(..., gt=0)
    tahmini_sure_saat: Optional[float] = Field(None, ge=0)
    zorluk: str = Field("Normal", max_length=20)  # Düz, Hafif Eğimli, Dik/Dağlık
    cikis_lat: Optional[float] = Field(None, ge=-90, le=90)
    cikis_lon: Optional[float] = Field(None, ge=-180, le=180)
    varis_lat: Optional[float] = Field(None, ge=-90, le=90)
    varis_lon: Optional[float] = Field(None, ge=-180, le=180)
    ascent_m: Optional[float] = Field(
        None, ge=0, description="Toplam yokuş yukarı (metre)"
    )
    descent_m: Optional[float] = Field(
        None, ge=0, description="Toplam yokuş aşağı (metre)"
    )
    flat_distance_km: float = Field(0.0, ge=0, description="Düz yol mesafesi (km)")
    otoban_mesafe_km: Optional[float] = Field(
        None, ge=0, description="Otoban mesafesi (km)"
    )
    sehir_ici_mesafe_km: Optional[float] = Field(
        None, ge=0, description="Şehiriçi/Kırsal mesafe (km)"
    )
    route_analysis: Optional[dict] = Field(
        None, description="Detailed route geometry and segment stats"
    )
    source: Optional[str] = Field(None, description="Data source (api, mapbox, manual)")
    notlar: Optional[str] = None
    aktif: bool = True


class LokasyonCreate(LokasyonBase):
    pass


class LokasyonUpdate(BaseModel):
    ad: Optional[str] = Field(None, max_length=150)
    cikis_yeri: Optional[str] = Field(None, max_length=100)
    varis_yeri: Optional[str] = Field(None, max_length=100)
    mesafe_km: Optional[float] = Field(None, gt=0)
    tahmini_sure_saat: Optional[float] = Field(None, ge=0)
    zorluk: Optional[str] = Field(None, max_length=20)
    cikis_lat: Optional[float] = Field(None, ge=-90, le=90)
    cikis_lon: Optional[float] = Field(None, ge=-180, le=180)
    varis_lat: Optional[float] = Field(None, ge=-90, le=90)
    varis_lon: Optional[float] = Field(None, ge=-180, le=180)
    ascent_m: Optional[float] = Field(None, ge=0)
    descent_m: Optional[float] = Field(None, ge=0)
    flat_distance_km: Optional[float] = Field(None, ge=0)
    otoban_mesafe_km: Optional[float] = Field(None, ge=0)
    sehir_ici_mesafe_km: Optional[float] = Field(None, ge=0)
    route_analysis: Optional[dict] = None
    source: Optional[str] = None
    notlar: Optional[str] = None


class LokasyonResponse(LokasyonBase):
    id: int
    api_mesafe_km: Optional[float] = None
    api_sure_saat: Optional[float] = None
    tahmini_yakit_lt: Optional[float] = None
    last_api_call: Optional[datetime] = None
    route_analysis: Optional[dict] = None
    source: Optional[str] = Field(
        None, description="Veri kaynağı (api, mapbox_hybrid, etc.)"
    )
    is_corrected: bool = Field(False, description="Veri düzeltildi mi?")
    correction_reason: Optional[str] = Field(None, description="Düzeltme nedeni")
    # Phase 3.4 — hidrasyon meta (LokasyonHydrator çıktısı)
    hydrated_at: Optional[datetime] = Field(
        None, description="Son LokasyonHydrator çalışma zamanı"
    )
    raw_segment_count: int = 0
    resampled_segment_count: int = 0
    elevation_coverage_pct: float = 0.0

    @field_validator(
        "api_mesafe_km", "api_sure_saat", "tahmini_yakit_lt", mode="before"
    )
    @classmethod
    def heal_floats(cls, v: Any) -> Optional[float]:
        """Bozuk float değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = float(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    @field_validator("last_api_call", "hydrated_at", mode="before")
    @classmethod
    def heal_datetime(cls, v: Any) -> Optional[datetime]:
        """Bozuk datetime değerlerini NULL yapar."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return None

    @field_validator("raw_segment_count", "resampled_segment_count", mode="before")
    @classmethod
    def heal_counts(cls, v: Any) -> int:
        """Bozuk sayıları 0 yapar."""
        if v is None:
            return 0
        try:
            val = int(v)
            return max(0, val)
        except (ValueError, TypeError):
            return 0

    @field_validator("elevation_coverage_pct", mode="before")
    @classmethod
    def heal_coverage(cls, v: Any) -> float:
        """Bozuk coverage yüzdesini 0.0 yapar."""
        if v is None:
            return 0.0
        try:
            val = float(v)
            return max(0.0, min(100.0, val))
        except (ValueError, TypeError):
            return 0.0

    model_config = ConfigDict(from_attributes=True)


class LokasyonSegmentResponse(BaseModel):
    """Phase 3.5 — lokasyon_segments STATİK satırı.

    Trafik (traffic_speed/congestion) bu shape'te YOK; o veriler sefer
    simülasyonu sırasında route_segments'a yazılır.
    """

    seq: int
    length_km: float
    grade_pct: float
    road_class: Optional[str] = None
    maxspeed_kmh: Optional[float] = None
    mid_lon: Optional[float] = None
    mid_lat: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class LokasyonSegmentsResponse(BaseModel):
    """GET /locations/{id}/segments — segments + hidrasyon header meta."""

    lokasyon_id: int
    ad: Optional[str] = None
    hydrated_at: Optional[datetime] = None
    raw_segment_count: int
    resampled_segment_count: int
    elevation_coverage_pct: float
    segments: List[LokasyonSegmentResponse]


class LokasyonPaginationResponse(BaseModel):
    items: List[LokasyonResponse]
    total: int


class GeocodeSuggestion(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    label: str = Field(..., min_length=1, max_length=255)
    source: Literal["ors", "nominatim", "offline"]
