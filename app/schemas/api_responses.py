"""Response schemas for endpoints whose shape does not fit a domain entity.

Used by:
  - health/admin_health        — system health snapshots
  - admin_imports              — import job history
  - admin_notifications        — notification rules + user inbox
  - admin_maintenance          — maintenance records, alerts, completion
  - fuel/stats                 — fuel statistics summary
  - weather/dashboard-summary  — dashboard risk roll-up
  - locations/route-info       — coordinate→route lookup
  - routes/analyze             — route analysis with difficulty
"""

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CONN_STR_RE = re.compile(
    r"(postgresql|redis|mongodb|amqp|mysql)://[^\s\"']+", re.IGNORECASE
)

# ─── Health / Admin Health ───────────────────────────────────────────────────


class ComponentHealth(BaseModel):
    """One subsystem's health probe outcome."""

    status: str = Field(..., description="healthy | degraded | unhealthy")
    latency_ms: Optional[float] = None
    error: Optional[str] = None

    @field_validator("error", mode="before")
    @classmethod
    def sanitize_error(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        msg = _CONN_STR_RE.sub("[connection-redacted]", str(v))
        return msg[:300]

    model_config = ConfigDict(extra="allow")


class HealthCheckResponse(BaseModel):
    """Liveness/readiness summary returned by `/health`."""

    status: str
    uptime_seconds: int
    components: Dict[str, ComponentHealth]

    model_config = ConfigDict(extra="allow")


class AdminHealthResponse(HealthCheckResponse):
    """Admin variant adds Sentry, circuit-breaker, and backup state."""

    sentry: Optional[Dict[str, Any]] = None
    circuit_breakers: Optional[Union[Dict[str, Any], List[Any]]] = None
    backups: Optional[Dict[str, Any]] = None


class CircuitBreakerResetResponse(BaseModel):
    success: bool
    message: str


class BackupTriggerResponse(BaseModel):
    message: str
    task_id: str


# ─── Admin Imports ───────────────────────────────────────────────────────────


class ImportHistoryItem(BaseModel):
    """One row from the import-job history table."""

    id: int
    dosya_adi: str
    aktarim_tipi: str
    durum: str
    toplam: int
    basarili: int
    hatali: int
    baslama_zamani: Optional[datetime] = None
    yukleyen_id: Optional[int] = None

    @field_validator("dosya_adi", "aktarim_tipi", "durum", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("toplam", "basarili", "hatali", mode="before")
    @classmethod
    def heal_ints(cls, v: Any) -> int:
        """Bozuk int değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("baslama_zamani", mode="before")
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


# ─── Admin Notifications ─────────────────────────────────────────────────────


class NotificationRuleResponse(BaseModel):
    id: int
    olay_tipi: str
    kanallar: List[str]
    alici_rol_id: int
    aktif: bool

    model_config = ConfigDict(extra="allow", from_attributes=True)


class NotificationItemResponse(BaseModel):
    id: int
    baslik: str
    icerik: str
    olay_tipi: Optional[str] = None
    kanal: str
    durum: str
    okundu: bool
    olusturma_tarihi: str

    @field_validator("baslik", "icerik", "kanal", "durum", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("olay_tipi", mode="before")
    @classmethod
    def heal_optional_string(cls, v: Any) -> Optional[str]:
        """Boş optional string alanlarını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("olusturma_tarihi", mode="before")
    @classmethod
    def heal_datetime_string(cls, v: Any) -> str:
        """Bozuk datetime string değerlerini fallback'ler."""
        if v is None:
            return datetime.now(timezone.utc).isoformat()
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v).strip()


class MarkAllReadResponse(BaseModel):
    success: bool
    count: int


class MarkSingleReadResponse(BaseModel):
    success: bool


# ─── Admin Maintenance ───────────────────────────────────────────────────────


class MaintenanceRecordResponse(BaseModel):
    """`AracBakim` row, exposed via SQLAlchemy `from_attributes`."""

    id: int
    arac_id: Optional[int] = None
    dorse_id: Optional[int] = None
    bakim_tipi: str
    km_bilgisi: int
    bakim_tarihi: datetime
    maliyet: Decimal = Field(default=Decimal("0"))
    detaylar: Optional[str] = None
    tamamlandi: bool = False
    guncelleme_tarihi: Optional[datetime] = None

    @field_validator("bakim_tipi", mode="before")
    @classmethod
    def heal_bakim_tipi(cls, v: Any) -> str:
        """Boş bakim_tipi alanını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("km_bilgisi", mode="before")
    @classmethod
    def heal_km(cls, v: Any) -> int:
        """Bozuk km değerlerini 0 yapar."""
        if v is None:
            return 0
        try:
            return max(0, int(v))
        except (ValueError, TypeError):
            return 0

    @field_validator("maliyet", mode="before")
    @classmethod
    def heal_maliyet(cls, v: Any) -> Decimal:
        """Bozuk maliyet değerlerini 0 yapar."""
        if v is None:
            return Decimal("0")
        try:
            val = Decimal(str(v))
            return val if val >= 0 else Decimal("0")
        except (ValueError, TypeError, Exception):
            return Decimal("0")

    @field_validator("detaylar", mode="before")
    @classmethod
    def heal_detaylar(cls, v: Any) -> Optional[str]:
        """Boş detaylar alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    @field_validator("bakim_tarihi", mode="before")
    @classmethod
    def heal_bakim_tarihi(cls, v: Any) -> datetime:
        """Bozuk datetime değerlerini şu andan yapılır."""
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return datetime.now(timezone.utc)

    @field_validator("guncelleme_tarihi", mode="before")
    @classmethod
    def heal_update_time(cls, v: Any) -> Optional[datetime]:
        """Bozuk optional datetime değerlerini NULL yapar."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return None

    model_config = ConfigDict(from_attributes=True)


class MaintenanceAlertItem(BaseModel):
    """Single maintenance alert as enriched by the service layer."""

    id: int
    arac_id: Optional[int] = None
    plaka: str
    bakim_tipi: str
    tarih: datetime
    vade_durumu: str = Field(..., description="UPCOMING | OVERDUE")

    @field_validator("plaka", "bakim_tipi", "vade_durumu", mode="before")
    @classmethod
    def heal_strings(cls, v: Any) -> str:
        """Boş string alanlarını fallback'ler."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "BİLİNMİYOR"
        return str(v).strip()

    @field_validator("tarih", mode="before")
    @classmethod
    def heal_datetime(cls, v: Any) -> datetime:
        """Bozuk datetime değerlerini şu andan yapılır."""
        if v is None:
            return datetime.now(timezone.utc)
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError, Exception):
            return datetime.now(timezone.utc)


class MaintenanceCompleteResponse(BaseModel):
    success: bool


# ─── Fuel statistics ─────────────────────────────────────────────────────────


class FuelStatsResponse(BaseModel):
    """Fuel aggregation summary. Service-driven, so extra keys are tolerated
    (e.g. per-vehicle breakdown, percentile metrics) — but the headline numbers
    are documented for the client contract."""

    toplam_litre: Optional[float] = None
    toplam_maliyet: Optional[float] = None
    ortalama_birim_fiyat: Optional[float] = None
    kayit_sayisi: Optional[int] = None

    @field_validator(
        "toplam_litre", "toplam_maliyet", "ortalama_birim_fiyat", mode="before"
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

    @field_validator("kayit_sayisi", mode="before")
    @classmethod
    def heal_count(cls, v: Any) -> Optional[int]:
        """Bozuk count değerlerini NULL yapar."""
        if v is None:
            return None
        try:
            val = int(v)
            return val if val >= 0 else None
        except (ValueError, TypeError):
            return None

    model_config = ConfigDict(extra="allow")


# ─── Weather dashboard ──────────────────────────────────────────────────────


class WeatherTripDetail(BaseModel):
    trip_id: int
    plaka: str
    risk: str = Field(..., description="High | Unavailable")
    impact: Optional[float] = None
    error_code: Optional[str] = None


class WeatherDashboardResponse(BaseModel):
    total_active: int
    high_risk: int
    medium_risk: int
    normal: int
    unavailable: int
    details: List[WeatherTripDetail]


# ─── Routes / locations ─────────────────────────────────────────────────────


class RouteInfoResponse(BaseModel):
    """Result of a coordinate→route lookup. Provider returns extra fields
    (geometry, segments, elevation profile) — kept under `extra=allow` so
    callers can read them, but the documented core is mandatory."""

    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    otoban_mesafe_km: Optional[float] = None
    sehir_ici_mesafe_km: Optional[float] = None
    source: Optional[str] = None

    @field_validator(
        "distance_km",
        "duration_min",
        "ascent_m",
        "descent_m",
        "otoban_mesafe_km",
        "sehir_ici_mesafe_km",
        mode="before",
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

    @field_validator("source", mode="before")
    @classmethod
    def heal_source(cls, v: Any) -> Optional[str]:
        """Boş source alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()

    model_config = ConfigDict(extra="allow")


class RouteAnalysisResponse(RouteInfoResponse):
    difficulty: Optional[str] = Field(
        None, description="Düz | Hafif Eğimli | Dik/Dağlık (computed by service)"
    )

    @field_validator("difficulty", mode="before")
    @classmethod
    def heal_difficulty(cls, v: Any) -> Optional[str]:
        """Boş difficulty alanını NULL yapar."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()


# ─── Generic message responses ──────────────────────────────────────────────
# Tier E madde 33: shared shapes for the many endpoints that just return
# {"detail": "..."} — reused instead of a bespoke schema per endpoint.


class MessageResponse(BaseModel):
    """Plain `{"detail": "..."}` acknowledgement."""

    detail: str


class MessageWithWarningResponse(MessageResponse):
    """Same as `MessageResponse`, plus an optional non-fatal warning
    (e.g. auth logout when token-blacklisting failed but logout still
    succeeded)."""

    warning: Optional[str] = None


class SuccessCountResponse(BaseModel):
    """`{"success": bool, "message": str}` acknowledgement, optionally with
    a count of affected rows."""

    success: bool
    message: str
    count: Optional[int] = None


class ImportResultResponse(BaseModel):
    """Shared shape for Excel/bulk-import endpoints:
    `{"count": int, "errors": [str, ...]}`."""

    count: int
    errors: List[str] = Field(default_factory=list)


class DeleteResultResponse(BaseModel):
    """Shared shape for single-row delete endpoints that report whether the
    row was hard- or soft-deleted."""

    success: bool
    deleted_id: int
    mode: str = Field(..., description="Hard | Soft")


# ─── Locations ───────────────────────────────────────────────────────────────


class LocationStatsData(BaseModel):
    total: int
    analyzed: int
    stale: int
    avg_distance_km: float
    high_difficulty: int


class LocationStatsResponse(BaseModel):
    status: str
    data: LocationStatsData


class StaleLocationItem(BaseModel):
    id: int
    cikis_yeri: str
    varis_yeri: str
    mesafe_km: Optional[float] = None
    zorluk: Optional[str] = None
    last_api_call: Optional[datetime] = None

    model_config = ConfigDict(extra="allow")


class StaleLocationsResponse(BaseModel):
    status: str
    data: List[StaleLocationItem]
    threshold_days: int


class RouteAnalyzeResponse(BaseModel):
    success: bool
    api_mesafe_km: Optional[float] = None
    api_sure_saat: Optional[float] = None
    ascent_m: Optional[float] = None
    descent_m: Optional[float] = None
    otoban_mesafe_km: Optional[float] = None
    sehir_ici_mesafe_km: Optional[float] = None
    source: Optional[str] = None
    is_corrected: bool = False
    correction_reason: Optional[str] = None
    route_analysis: Optional[Any] = None
    elevation_profile: List[Any] = Field(default_factory=list)


# ─── Weather ─────────────────────────────────────────────────────────────────


class WeatherSummary(BaseModel):
    avg_temperature: float
    avg_precipitation: float
    avg_wind_speed: float


class TripWeatherImpactResponse(BaseModel):
    success: bool
    weather_summary: WeatherSummary
    fuel_impact_factor: float
    fuel_impact_percent: float
    conditions: List[str]
    recommendation: str


class UploadResultResponse(BaseModel):
    """Shared shape for Excel-upload endpoints:
    `{"success": bool, "message": str, "errors": [str, ...]}`."""

    success: bool
    message: str
    errors: List[str] = Field(default_factory=list)


# ─── Fleet (vehicles / trailers) ────────────────────────────────────────────
# Identical shapes reused by vehicles.py and trailers.py — CLAUDE.md already
# documents these two files as near-duplicates of each other.


class FleetStatsResponse(BaseModel):
    total: int
    active: int
    inspection_expiring: int
    inspection_overdue: int


class InspectionAlertItem(BaseModel):
    id: int
    plaka: str
    marka: Optional[str] = None
    model: Optional[str] = None
    yil: Optional[int] = None
    muayene_tarihi: Optional[str] = None
    days_remaining: Optional[int] = None


class InspectionAlertsResponse(BaseModel):
    expiring: List[InspectionAlertItem]
    overdue: List[InspectionAlertItem]
    within_days: int


class FleetEventItem(BaseModel):
    id: int
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    triggered_by: Optional[str] = None
    details: Optional[Any] = None
    created_at: Optional[str] = None


class DriverFleetStatsResponse(BaseModel):
    total: int
    active: int


class DorseInspectionAlertItem(BaseModel):
    id: int
    plaka: str
    marka: Optional[str] = None
    tipi: Optional[str] = None
    yil: Optional[int] = None
    muayene_tarihi: Optional[str] = None
    days_remaining: Optional[int] = None


class DorseInspectionAlertsResponse(BaseModel):
    expiring: List[DorseInspectionAlertItem]
    overdue: List[DorseInspectionAlertItem]
    within_days: int


class DorseImportResult(BaseModel):
    imported: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# ─── Async background job polling ───────────────────────────────────────────
# See CLAUDE.md "Async job pattern" — shared by any endpoint polling
# BackgroundJobManager (e.g. trips.get_task_status).


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str = Field(..., description="PROCESSING | SUCCESS | FAILED")
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None


class TripTimelineResponse(BaseModel):
    items: List[Dict[str, Any]]


class FuelPerformanceKpis(BaseModel):
    mae: float
    rmse: float
    total_compared: int
    high_deviation_ratio: float


class FuelPerformanceTrendPoint(BaseModel):
    week: str
    avg_consumption: float
    count: int


class FuelPerformanceDistributionBucket(BaseModel):
    range: str
    count: int


class FuelPerformanceOutlier(BaseModel):
    sefer_id: int
    tarih: Optional[str] = None
    actual: float
    predicted: float
    deviation_pct: float


class FuelPerformanceAnalyticsResponse(BaseModel):
    kpis: FuelPerformanceKpis
    trend: List[FuelPerformanceTrendPoint]
    distribution: List[FuelPerformanceDistributionBucket]
    outliers: List[FuelPerformanceOutlier]
    low_data: bool


# ─── Predictions (time-series / ensemble / XAI) ────────────────────────────


class TrendAnalysisResponse(BaseModel):
    success: bool
    trend: str = Field(..., description="decreasing | increasing | stable")
    trend_tr: str
    slope: float
    current_avg: float
    previous_avg: Optional[float] = None
    moving_average_7: List[float]
    daily_values: List[float]
    daily_total_values: List[float]
    dates: List[Optional[str]]
    days_analyzed: int


class TimeSeriesStatusResponse(BaseModel):
    is_trained: bool
    training_epochs: Optional[int] = None
    last_loss: Optional[float] = None
    n_training_samples: Optional[int] = None
    train_time_s: Optional[float] = None
    bilstm_mae: Optional[float] = None
    tcn_mae: Optional[float] = None
    torch_available: bool
    deep_learning_active: bool
    min_days_for_deep: Optional[int] = None


class EnsembleModelFlags(BaseModel):
    physics: bool
    lightgbm: bool
    xgboost: bool
    gradient_boosting: bool
    random_forest: bool


class EnsembleStatusResponse(BaseModel):
    models: EnsembleModelFlags
    weights: Dict[str, float]
    sklearn_available: bool
    lightgbm_available: bool
    xgboost_available: bool
    total_models: int


class ExplainPredictionResponse(BaseModel):
    prediction: float
    unit: str
    contributions: Dict[str, float]
    confidence: float


# ─── Cost analyzer ───────────────────────────────────────────────────────────


class CostTrendPoint(BaseModel):
    month: int
    year: int
    label: str
    fuel_cost: float
    fuel_liters: float
    trip_count: int
    total_distance: float
    cost_per_km: float


class VehicleCostComparisonItem(BaseModel):
    arac_id: int
    plaka: Optional[str] = None
    fuel_cost: Optional[float] = None
    total_distance: Optional[float] = None
    cost_per_km: Optional[float] = None
    avg_consumption: Optional[float] = None
    unavailable: Optional[bool] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# ─── AI chat/status ──────────────────────────────────────────────────────────


class AiProgressResponse(BaseModel):
    status: str = Field(..., description="ready | loading | error | offline")
    pending_jobs: int


class AiStatusResponse(BaseModel):
    is_ready: bool
    progress: AiProgressResponse


class AiChatResponse(BaseModel):
    response: str
    timestamp: str


# ─── Admin imports ───────────────────────────────────────────────────────────


class ImportPreviewResponse(BaseModel):
    filename: Optional[str] = None
    aktarim_tipi: str
    headers: List[str]
    total_rows: int
    preview: List[Dict[str, Any]]


class ImportCommitResponse(BaseModel):
    job_id: int
    basarili: int
    hatali: int
    errors: Dict[str, str] = Field(default_factory=dict)


class BackfillTriggerResponse(BaseModel):
    status: str = Field(..., description="PROCESSING | SUCCESS | FAILED")
    task_id: str


class SuccessOnlyResponse(BaseModel):
    """Bare `{"success": bool}` acknowledgement."""

    success: bool


class TraceChainResponse(BaseModel):
    """Combined error_events + audit_log rows for one trace_id (debugging)."""

    errors: List[Dict[str, Any]]
    audit: List[Dict[str, Any]]
    trace_id: str
    counts: Dict[str, int]
    hint: Optional[str] = None


class SseTokenResponse(BaseModel):
    token: str
    expires_in: int


class CoachingSnapshotResponse(BaseModel):
    ad_soyad: str
    skor: float
    headline: str
    top_suggestion: Optional[str] = None
    priority: str
    insights_count: int
    source: str


# ─── Binary/stream media-type documentation ────────────────────────────────
# Tier E madde 33: these endpoints genuinely return non-JSON bodies (Excel/
# PDF/ICS files, SSE streams) — a Pydantic response_model would be wrong for
# them. FastAPI's `responses={...}` param still lets the OpenAPI schema
# declare the real content-type instead of defaulting to nothing, so
# generated SDKs know to treat these as binary/blob/stream rather than
# `unknown`.

EXCEL_XLSX_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "content": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
        },
        "description": "Excel (.xlsx) dosyası",
    }
}

PDF_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {"content": {"application/pdf": {}}, "description": "PDF dosyası"}
}

ICS_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "content": {"text/calendar; charset=utf-8": {}},
        "description": "iCalendar (.ics) dosyası",
    }
}

SSE_RESPONSES: Dict[Union[int, str], Dict[str, Any]] = {
    200: {
        "content": {"text/event-stream": {}},
        "description": "Server-Sent Events akışı",
    }
}
