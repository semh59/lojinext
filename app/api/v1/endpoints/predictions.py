import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import and_, select

from app.api.deps import SessionDep, get_current_active_admin, get_current_active_user
from app.database.models import Kullanici, Sefer, Sofor
from app.infrastructure.background.celery_app import celery_app
from app.schemas.api_responses import (
    SSE_RESPONSES,
    EnsembleStatusResponse,
    ExplainPredictionResponse,
    TimeSeriesStatusResponse,
    TrendAnalysisResponse,
)
from app.schemas.prediction import (
    AccuracyDistribution,
    ForecastResponseModel,
    PredictionComparisonPoint,
    PredictionComparisonResponse,
    PredictionEnqueueRequest,
    PredictionEnqueueResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionStatusResponse,
    TrainingResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter()


def _build_time_series_error_response(
    result: dict, default_message: str
) -> JSONResponse:
    """Map structured service failures to a direct JSONResponse.

    Returns a JSONResponse (bypasses the global error envelope) so clients
    receive the flat time-series contract body with ``request_id`` and
    ``timestamp`` fields at the top level.
    """
    import uuid as _uuid

    body = {
        "success": False,
        "error_code": result.get("error_code", "TIME_SERIES_ERROR"),
        "error_message": result.get("error", default_message),
        "request_id": str(_uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(
        status_code=int(result.get("status_code", 503)),
        content=body,
    )


@router.post("", response_model=PredictionEnqueueResponse, status_code=202)
async def enqueue_prediction(
    request: PredictionEnqueueRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Uzun süren tahmin isteklerini kuyruğa alır (Celery)."""
    task = celery_app.send_task(
        "prediction.generate", args=[request.question, request.context]
    )
    return PredictionEnqueueResponse(task_id=task.id)


@router.post("/predict", response_model=PredictionResponse)
async def predict_fuel(
    request: PredictionRequest,
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """
    Sefer senaryosu için yakıt tüketim tahmini yap.
    sofor_id verilirse veritabanından puan çekilir,
    sofor_score verilirse direkt kullanılır.
    """
    # Şoför puanını belirle
    sofor_score = 1.0  # Varsayılan

    if request.sofor_score is not None:
        # Doğrulanmış aralık: 0.1 (Kötü) - 2.0 (Mükemmel)
        if not (0.1 <= request.sofor_score <= 2.0):
            raise HTTPException(
                status_code=400, detail="Şoför puanı 0.1 ile 2.0 arasında olmalıdır"
            )
        sofor_score = request.sofor_score
    elif request.sofor_id is not None:
        # Şoför puanını veritabanından çek
        sofor = await db.get(Sofor, request.sofor_id)
        if sofor:
            sofor_score = sofor.score or 1.0
        else:
            raise HTTPException(status_code=404, detail="Şoför bulunamadı")

    service = PredictionService()
    result = await service.predict_consumption(
        arac_id=request.arac_id,
        mesafe_km=request.mesafe_km,
        ton=request.ton,
        ascent_m=request.ascent_m,
        descent_m=request.descent_m,
        flat_distance_km=request.flat_distance_km,
        zorluk=getattr(request, "zorluk", "Normal"),
        sofor_id=request.sofor_id,
        sofor_score=sofor_score,
        route_analysis=request.route_analysis,
    )

    if result["status"] == "error":
        error_code = result.get("code")
        if error_code == "model_not_trained":
            status_code = 422
        elif error_code == "service_unavailable":
            status_code = 503
        else:
            status_code = 500
        raise HTTPException(
            status_code=status_code, detail=result.get("message", "Tahmin hatası")
        )

    return result


@router.post("/train/{arac_id}", response_model=TrainingResponse)
async def train_vehicle_model(
    arac_id: int,
    current_admin: Annotated[Kullanici, Depends(get_current_active_admin)],
):
    """Belirli bir araç için tüm ML modellerini (Ensemble) eğitir."""
    service = PredictionService()
    result = await service.train_xgboost_model(arac_id, user_id=current_admin.id)
    if result.get("status") != "success":
        raise HTTPException(
            status_code=500, detail=result.get("message", "Model eğitimi başarısız")
        )
    return result


@router.get("/comparison", response_model=PredictionComparisonResponse)
async def get_prediction_comparison(
    db: SessionDep,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    days: int = Query(30, ge=1, le=365),
    arac_id: Optional[int] = Query(
        None,
        ge=1,
        description="Tek bir aracın tahmin/gerçek karşılaştırmasıyla sınırla",
    ),
):
    """
    Tahmin vs Gerçek karşılaştırma metriklerini getirir.
    MEA, RMSE, doğruluk dağılımı ve trend verilerini içerir.
    """
    start_date = datetime.now(timezone.utc).date() - timedelta(days=days)

    # 1. Verileri çek (Hem tahmin hem gerçek verisi olanlar)
    where_clauses = [
        Sefer.tarih >= start_date,
        Sefer.tahmini_tuketim.isnot(None),
        Sefer.tuketim.isnot(None),
        Sefer.tuketim > 0,
    ]
    if arac_id is not None:
        where_clauses.append(Sefer.arac_id == arac_id)

    query = select(Sefer).where(and_(*where_clauses)).order_by(Sefer.tarih.asc())
    result = await db.execute(query)
    seferler = result.scalars().all()

    if not seferler:
        return PredictionComparisonResponse(
            mae=0.0,
            rmse=0.0,
            accuracy_distribution=AccuracyDistribution(
                good=0, warning=0, error=0, good_pct=0, warning_pct=0, error_pct=0
            ),
            trend=[],
            total_compared=0,
        )

    # 2. Metrikleri hesapla
    total_abs_error = 0.0
    total_sq_error = 0.0
    good = 0
    warning = 0
    error = 0

    trend_data: Dict[str, Any] = {}

    for s in seferler:
        actual = s.tuketim
        predicted = s.tahmini_tuketim

        err = actual - predicted
        abs_err = abs(err)
        total_abs_error += abs_err
        total_sq_error += err**2

        # Dağılım
        pct_err = (abs_err / predicted) * 100 if predicted > 0 else 100
        if pct_err <= 5:
            good += 1
        elif pct_err <= 15:
            warning += 1
        else:
            error += 1

        # Trend için grupla (günlük ortalama)
        d_str = s.tarih.isoformat()
        if d_str not in trend_data:
            trend_data[d_str] = {"actual": [], "predicted": []}
        trend_data[d_str]["actual"].append(actual)
        trend_data[d_str]["predicted"].append(predicted)

    count = len(seferler)
    mae = total_abs_error / count
    rmse = (total_sq_error / count) ** 0.5

    # Trend listesi
    trend_list = []
    for d_str, vals in sorted(trend_data.items()):
        trend_list.append(
            PredictionComparisonPoint(
                date=d_str,
                actual=sum(vals["actual"]) / len(vals["actual"]),
                predicted=sum(vals["predicted"]) / len(vals["predicted"]),
            )
        )

    return PredictionComparisonResponse(
        mae=mae,
        rmse=rmse,
        accuracy_distribution=AccuracyDistribution(
            good=good,
            warning=warning,
            error=error,
            good_pct=(good / count) * 100,
            warning_pct=(warning / count) * 100,
            error_pct=(error / count) * 100,
        ),
        trend=trend_list,
        total_compared=count,
    )


@router.post("/time-series/forecast", response_model=ForecastResponseModel)
async def forecast_consumption(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    arac_id: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=30),
):
    """Return a real weekly consumption forecast when prerequisites are met."""
    from app.services.time_series_service import get_time_series_service

    service = get_time_series_service()
    res = await service.predict_weekly(arac_id)

    if not res["success"]:
        return _build_time_series_error_response(
            res, "Time-series forecast is unavailable."
        )

    # Convert to schema — use zip to avoid IndexError on mismatched array lengths
    points = []
    for f_date, f_val, conf_low, conf_high in zip(
        res.get("forecast_dates", []),
        res.get("forecast", []),
        res.get("confidence_low", []),
        res.get("confidence_high", []),
    ):
        points.append(
            {
                "date": f_date,
                "value": f_val,
                "confidence_low": conf_low,
                "confidence_high": conf_high,
            }
        )

    return {
        "series": points,
        "trend": res["trend"],
        "summary": "Model-based forward-looking consumption projection.",
        "method": res.get("method", "LSTM"),
    }


@router.get("/time-series/trend", response_model=TrendAnalysisResponse)
async def get_trend_analysis(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
    arac_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """Return historical consumption trend analysis based on real aggregates."""
    from app.services.time_series_service import get_time_series_service

    service = get_time_series_service()
    result = await service.get_trend_analysis(arac_id, days)
    if not result.get("success"):
        return _build_time_series_error_response(
            result, "Time-series trend analysis is unavailable."
        )
    return result


@router.get("/time-series/status", response_model=TimeSeriesStatusResponse)
async def get_time_series_status(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Zaman serisi model durumu."""
    from app.services.time_series_service import get_time_series_service

    service = get_time_series_service()
    return service.get_model_status()


@router.get("/ensemble/status", response_model=EnsembleStatusResponse)
async def get_ensemble_status(
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """Ensemble model durumu."""
    from app.core.ml.ensemble_predictor import (
        LIGHTGBM_AVAILABLE,
        SKLEARN_AVAILABLE,
        XGBOOST_AVAILABLE,
        EnsembleFuelPredictor,
    )

    predictor = EnsembleFuelPredictor()

    return {
        "models": {
            "physics": True,
            "lightgbm": LIGHTGBM_AVAILABLE,
            "xgboost": XGBOOST_AVAILABLE,
            "gradient_boosting": SKLEARN_AVAILABLE,
            "random_forest": SKLEARN_AVAILABLE,
        },
        "weights": predictor.weights,
        "sklearn_available": SKLEARN_AVAILABLE,
        "lightgbm_available": LIGHTGBM_AVAILABLE,
        "xgboost_available": XGBOOST_AVAILABLE,
        "total_models": sum(
            [
                1,  # Physics
                1 if LIGHTGBM_AVAILABLE else 0,
                1 if XGBOOST_AVAILABLE else 0,
                1 if SKLEARN_AVAILABLE else 0,  # GB
                1 if SKLEARN_AVAILABLE else 0,  # RF
            ]
        ),
    }


@router.post("/explain", response_model=ExplainPredictionResponse)
async def explain_fuel_prediction(
    request: PredictionRequest,
    current_user: Annotated[Kullanici, Depends(get_current_active_user)],
):
    """
    Tahmin sonucunun nedenlerini (XAI) getirir.
    """
    service = PredictionService()
    result = await service.explain_consumption(
        arac_id=request.arac_id,
        mesafe_km=request.mesafe_km,
        ton=request.ton,
        ascent_m=request.ascent_m,
        descent_m=request.descent_m,
        flat_distance_km=request.flat_distance_km,
        zorluk=getattr(request, "zorluk", "Normal"),
        sofor_id=request.sofor_id,
        sofor_score=request.sofor_score,
        route_analysis=request.route_analysis,
    )
    return result


# Parameterized routes last — static paths above must be registered first
# so Starlette doesn't swallow /comparison, /ensemble/status etc. as task_ids.
@router.get("/{task_id}", response_model=PredictionStatusResponse)
async def prediction_status(
    task_id: str, current_user: Annotated[Kullanici, Depends(get_current_active_user)]
):
    """Task durumunu döndürür (polling)."""
    result = AsyncResult(task_id, app=celery_app)
    payload = result.result if isinstance(result.result, dict) else {}
    return PredictionStatusResponse(
        task_id=task_id,
        status=result.state.lower(),
        answer=payload.get("answer"),
        error=payload.get("error"),
        finished_at=payload.get("finished_at"),
    )


@router.get(
    "/{task_id}/stream",
    responses=SSE_RESPONSES,
    response_model=None,
    response_class=StreamingResponse,
)
async def prediction_stream(
    task_id: str, current_user: Annotated[Kullanici, Depends(get_current_active_user)]
):
    """SSE benzeri akış; polling yerine sürekli durum gönderir."""

    async def event_generator():
        MAX_WAIT_SECONDS = 300
        for _ in range(MAX_WAIT_SECONDS):
            result = AsyncResult(task_id, app=celery_app)
            payload = result.result if isinstance(result.result, dict) else {}
            data = {
                "task_id": task_id,
                "status": result.state.lower(),
                "answer": payload.get("answer"),
                "error": payload.get("error"),
                "finished_at": payload.get("finished_at"),
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            if result.state.lower() in {"success", "failure", "revoked"}:
                return
            await asyncio.sleep(1)
        yield f"data: {json.dumps({'task_id': task_id, 'status': 'timeout', 'error': 'Task timed out'}, ensure_ascii=False)}\n\n"  # noqa: E501

    return StreamingResponse(event_generator(), media_type="text/event-stream")
