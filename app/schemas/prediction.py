"""
Tahmin (Prediction) Pydantic şemaları.

ML model tahminleri için request/response şemaları.
Güvenlik: Dict boyut limiti, tip güvenliği.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.validators import validate_dict_size

# Maksimum metrics dict boyutu
MAX_METRICS_KEYS = 50


class PredictionRequest(BaseModel):
    """ML tahmin isteği şeması."""

    model_config = ConfigDict(protected_namespaces=())

    arac_id: int = Field(..., gt=0, le=999999999, description="Araç ID")
    mesafe_km: float = Field(..., gt=0, le=100000, description="Mesafe (km)")
    ton: float = Field(0.0, ge=0, le=1000, description="Yük ağırlığı (ton)")
    ascent_m: float = Field(0.0, ge=0, le=50000, description="Toplam tırmanış (m)")
    descent_m: float = Field(0.0, ge=0, le=50000, description="Toplam iniş (m)")
    flat_distance_km: float = Field(
        0.0, ge=0, le=100000, description="Düz yol mesafesi (km)"
    )
    sofor_id: Optional[int] = Field(
        None, gt=0, description="Şoför ID (otomatik puan çekmek için)"
    )
    sofor_score: Optional[float] = Field(
        None, ge=0.1, le=2.0, description="Manuel şoför puanı (0.1-2.0)"
    )
    zorluk: Literal["Normal", "Orta", "Zor"] = Field(
        "Normal", description="Güzergah zorluk derecesi"
    )
    model_type: Literal["linear", "xgboost", "ensemble"] = Field(
        "ensemble", description="Kullanılacak ML model tipi"
    )
    route_analysis: Optional[Dict[str, Any]] = Field(
        None, description="Rota detay analizi (JSON)"
    )


class PredictionResponse(BaseModel):
    """ML tahmin yanit semasi."""

    model_config = ConfigDict(protected_namespaces=())

    tahmini_tuketim: float = Field(..., ge=0, description="Tahmini tuketim (L/100km)")
    tahmini_litre: Optional[float] = Field(
        None, ge=0, description="Tahmini toplam yakit (litre, mesafe bazli hesaplanir)"
    )
    prediction_liters: Optional[float] = Field(
        None,
        ge=0,
        description="Deprecated alias for tahmini_litre. Geriye donuk uyumluluk icin tutulur.",
    )
    model_used: Literal[
        "linear",
        "xgboost",
        "ensemble",
        "physics",
        "physics_fallback",
    ] = "ensemble"
    model_version: Optional[str] = Field(
        None, max_length=100, description="Model versiyon etiketi"
    )
    status: Literal["success", "failure"] = "success"
    confidence_score: Optional[float] = Field(
        None, ge=0, le=1, description="Tahmin guven skoru"
    )
    confidence_low: Optional[float] = Field(
        None, ge=0, description="Guven araligi alt sinir (L/100km)"
    )
    confidence_high: Optional[float] = Field(
        None, ge=0, description="Guven araligi ust sinir (L/100km)"
    )
    warning_level: Optional[Literal["GREEN", "YELLOW", "RED"]] = Field(
        None, description="Guven seviyesine gore uyari seviyesi"
    )
    fallback_triggered: Optional[bool] = Field(
        False, description="Tahmin fallback ile mi sonuclandi"
    )
    faktorler: Optional[Dict[str, Any]] = Field(
        None, description="Tahmin faktor breakdown"
    )
    explanation_summary: Optional[str] = Field(
        None, max_length=500, description="Kisa aciklama ozeti"
    )


class TrainingResponse(BaseModel):
    """Model eğitim yanıtı şeması."""

    model_config = ConfigDict(protected_namespaces=())

    status: str = Field(..., max_length=50)
    model_type: str = Field(..., max_length=20)
    r2_score: float = Field(..., ge=-1.0, le=1.0, description="R² skoru")
    sample_count: int = Field(..., ge=0, description="Eğitim örneği sayısı")
    metrics: Optional[Dict[str, Any]] = Field(
        None, description="Ek metrikler (max 50 anahtar)"
    )

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics_size(cls, v: Optional[Dict]) -> Optional[Dict]:
        """Metrics dict boyut kontrolü - DoS koruması."""
        return validate_dict_size(v, max_keys=MAX_METRICS_KEYS)

    @field_validator("metrics")
    @classmethod
    def validate_metrics_values(cls, v: Optional[Dict]) -> Optional[Dict]:
        """Metrics değerlerinin serializable olduğunu kontrol et."""
        if v is None:
            return v

        # İzin verilen tipler
        allowed_types = (int, float, str, bool, type(None), list, dict)

        def check_value(val: Any, depth: int = 0) -> bool:
            if depth > 5:  # Maksimum derinlik
                raise ValueError("Metrics çok derin iç içe yapı içeriyor")

            if not isinstance(val, allowed_types):
                raise ValueError(f"Metrics desteklenmeyen tip içeriyor: {type(val)}")

            if isinstance(val, dict):
                for k, sub_v in val.items():
                    if not isinstance(k, str):
                        raise ValueError("Metrics anahtarları string olmalı")
                    check_value(sub_v, depth + 1)
            elif isinstance(val, list):
                for item in val:
                    check_value(item, depth + 1)

            return True

        for key, value in v.items():
            check_value(value)

        return v


class ForecastDataPoint(BaseModel):
    """Tek bir tahmin noktası."""

    date: str
    value: float
    confidence_low: float
    confidence_high: float


class ForecastResponseModel(BaseModel):
    """Tahmin yanıt şeması."""

    series: list[ForecastDataPoint]
    trend: str
    summary: str
    method: str


class PredictionComparisonPoint(BaseModel):
    """Trend grafiği için veri noktası."""

    date: str
    actual: float
    predicted: float


class AccuracyDistribution(BaseModel):
    """Doğruluk dağılımı özet bilgisi."""

    good: int  # <= 5%
    warning: int  # 5-15%
    error: int  # > 15%
    good_pct: float
    warning_pct: float
    error_pct: float


class PredictionComparisonResponse(BaseModel):
    """Tahmin vs Gerçek karşılaştırma raporu."""

    mae: float
    rmse: float
    accuracy_distribution: AccuracyDistribution
    trend: List[PredictionComparisonPoint]
    total_compared: int


# Async prediction queue schemas
class PredictionEnqueueRequest(BaseModel):
    question: str
    context: Optional[str] = None


class PredictionEnqueueResponse(BaseModel):
    task_id: str
    status: str = "queued"


class PredictionStatusResponse(BaseModel):
    task_id: str
    status: str
    answer: Optional[str] = None
    error: Optional[str] = None
    finished_at: Optional[str] = None
    best_vehicle_id: Optional[int] = None
    worst_vehicle_id: Optional[int] = None
