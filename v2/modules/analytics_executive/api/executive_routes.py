"""Feature E — Strategic Cockpit endpoint'leri."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import settings
from app.infrastructure.audit.audit_logger import log_audit_event
from v2.modules.analytics_executive.application.aggregate_cross_feature import (
    aggregate_cross_feature,
)
from v2.modules.analytics_executive.application.get_bus_factor import (
    compute_bus_factor,
)
from v2.modules.analytics_executive.application.get_fleet_carbon import (
    compute_fleet_carbon,
)
from v2.modules.analytics_executive.application.get_fleet_efficiency import (
    gather_fvi_inputs,
)
from v2.modules.analytics_executive.application.project_cashflow import (
    project_cashflow,
)
from v2.modules.analytics_executive.application.scan_compliance import scan_compliance
from v2.modules.analytics_executive.application.simulate_what_if import (
    simulate_fleet_renewal,
    simulate_route_portfolio,
    simulate_training_program,
)
from v2.modules.analytics_executive.domain.fleet_efficiency import compute_fvi
from v2.modules.analytics_executive.infrastructure.pdf_export import (
    generate_executive_pdf,
)
from v2.modules.analytics_executive.schemas import (
    BusFactorResponse,
    CashflowProjectionResponse,
    CashflowWeekResponse,
    ComplianceHeatmapResponse,
    ComplianceItemResponse,
    CrossFeatureImpactResponse,
    FleetCarbonResponse,
    FleetEfficiencyResponse,
    MonteCarloBand,
    RiskLevelBus,
    TopDriverAnonymized,
    TopEmitterResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from v2.modules.auth_rbac.public import Kullanici, require_yetki
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

router = APIRouter()

CACHE_KEY_FVI = "executive:fvi:current"


_exec_redis: Any = None  # singleton — modül ömrü boyunca tek bağlantı havuzu


async def _get_redis():
    """Async Redis client (singleton); başarısızlıkta None → cache miss.

    Eskiden her endpoint her HTTP isteğinde aioredis.from_url(...) çağrıyor,
    yeni bir ConnectionPool yaratıyordu. 6 endpoint × N istek =
    ConnectionPool sızıntısı; yük altında Redis max_connections limitini
    aşıyordu.
    """
    global _exec_redis
    if _exec_redis is not None:
        return _exec_redis
    try:
        import redis.asyncio as aioredis

        _exec_redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        return _exec_redis
    except Exception as exc:
        logger.debug("Executive redis init failed: %s", exc)
        return None


def _ensure_enabled() -> None:
    if not settings.EXECUTIVE_ENABLED:
        raise HTTPException(status_code=503, detail="Strategic Cockpit devre dışı")


@router.get("/kpi", response_model=FleetEfficiencyResponse)
async def get_fleet_efficiency_index(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
) -> FleetEfficiencyResponse:
    """Filo Verimliliği Endeksi — 4 alt-skor weighted average.

    Redis cache 30 dk; bakım/anomali değişikliklerinde otomatik invalidate
    edilmez (TTL ile yenilenir). Flag kapalıysa 503.
    """
    _ensure_enabled()

    redis_client = await _get_redis()
    if redis_client is not None:
        try:
            cached = await redis_client.get(CACHE_KEY_FVI)
            if cached:
                return FleetEfficiencyResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("FVI cache read failed: %s", exc)

    async with UnitOfWork() as uow:
        inputs = await gather_fvi_inputs(uow, days_back=30)

    breakdown = compute_fvi(
        fuel_avg=(
            float(inputs["fuel_avg"]) if inputs["fuel_avg"] is not None else None
        ),
        fuel_target=(float(inputs["target"]) if inputs["target"] is not None else None),
        overdue_maintenance=int(inputs["overdue_count"] or 0),
        total_active_vehicles=int(inputs["total_active"] or 0),
        driver_avg_hybrid=(
            float(inputs["driver_avg"]) if inputs["driver_avg"] is not None else None
        ),
        resolved_anomalies=int(inputs["resolved"] or 0),
        acked_anomalies=int(inputs["acked"] or 0),
        total_anomalies=int(inputs["total_anomalies"] or 0),
        previous_fvi=None,  # v1: history yok (plan §18.4)
    )

    response = FleetEfficiencyResponse(
        fvi=breakdown.fvi,
        fuel_score=breakdown.fuel_score,
        maintenance_score=breakdown.maintenance_score,
        driver_score=breakdown.driver_score,
        anomaly_quality_score=breakdown.anomaly_quality_score,
        confidence=breakdown.confidence,
        trend_30d=breakdown.trend_30d,
        reasons=breakdown.reasons,
        computed_at=breakdown.computed_at,
    )

    if redis_client is not None:
        try:
            await redis_client.setex(
                CACHE_KEY_FVI,
                settings.EXECUTIVE_CACHE_TTL_S,
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("FVI cache write failed: %s", exc)

    # Audit (PII'siz; sadece kullanım kanıtı)
    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_viewed",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "endpoint": "kpi",
                "fvi": breakdown.fvi,
                "confidence": breakdown.confidence,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Audit log failed: %s", exc)

    return response


@router.post("/what-if", response_model=WhatIfResponse)
async def run_what_if(
    payload: WhatIfRequest,
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
) -> WhatIfResponse:
    """E.2 — 3 senaryo simülatörü.

    scenario_type'a göre uygun simulate_* fonksiyonu çağrılır:
      - fleet_renewal: lineer ROI + CO2
      - training: lineer ROI
      - route_portfolio: Monte Carlo P10/P50/P90
    """
    _ensure_enabled()
    if not settings.EXECUTIVE_WHAT_IF_ENABLED:
        raise HTTPException(status_code=503, detail="What-if devre dışı")

    async with UnitOfWork() as uow:
        if payload.scenario_type == "fleet_renewal":
            if not payload.fleet_renewal:
                raise HTTPException(
                    status_code=400,
                    detail="fleet_renewal inputs gerekli",
                )
            result = await simulate_fleet_renewal(
                uow, **payload.fleet_renewal.model_dump()
            )
        elif payload.scenario_type == "training":
            if not payload.training:
                raise HTTPException(status_code=400, detail="training inputs gerekli")
            result = await simulate_training_program(
                uow, **payload.training.model_dump()
            )
        elif payload.scenario_type == "route_portfolio":
            if not payload.route_portfolio:
                raise HTTPException(
                    status_code=400,
                    detail="route_portfolio inputs gerekli",
                )
            result = await simulate_route_portfolio(
                uow, **payload.route_portfolio.model_dump()
            )
        else:  # pragma: no cover — Pydantic Literal zaten reddeder
            raise HTTPException(status_code=400, detail="Bilinmeyen scenario_type")

    # Audit (PII'siz; inputs scenario için makul kanıt)
    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="what_if_run",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "scenario_type": payload.scenario_type,
                "yearly_savings_tl": result.yearly_savings_tl,
                "five_year_roi_pct": result.five_year_roi_pct,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("What-if audit log failed: %s", exc)

    return WhatIfResponse(
        scenario_type=result.scenario_type,
        inputs=result.inputs,
        yearly_savings_tl=result.yearly_savings_tl,
        upfront_cost_tl=result.upfront_cost_tl,
        payback_years=result.payback_years,
        five_year_roi_pct=result.five_year_roi_pct,
        co2_reduction_kg=result.co2_reduction_kg,
        confidence=result.confidence,
        monte_carlo=cast("MonteCarloBand", result.monte_carlo),
        reasons=result.reasons,
    )


@router.get("/carbon", response_model=FleetCarbonResponse)
async def get_fleet_carbon(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
    days: int = 30,
) -> FleetCarbonResponse:
    """E.3 — Filo karbon raporu (Euro sınıfı bazında + sektör karşılaştırma).

    Args:
        days: rapor periyodu (default 30; min 7, max 365)
    """
    _ensure_enabled()
    if days < 7 or days > 365:
        raise HTTPException(
            status_code=400,
            detail="days parametresi 7-365 arası olmalı",
        )

    # 1 saat Redis cache (period_days bazında ayrı key)
    redis_client = await _get_redis()
    cache_key = f"executive:carbon:{days}"
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return FleetCarbonResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("Carbon cache read failed: %s", exc)

    async with UnitOfWork() as uow:
        report = await compute_fleet_carbon(uow, period_days=days)

    response = FleetCarbonResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        total_co2_kg=report.total_co2_kg,
        total_km=report.total_km,
        co2_per_km=report.co2_per_km,
        benchmark_co2_per_km=report.benchmark_co2_per_km,
        delta_pct=report.delta_pct,
        by_euro_class=report.by_euro_class,
        top_emitters=[
            TopEmitterResponse(
                plaka=e.plaka,
                co2_kg=e.co2_kg,
                euro_class=e.euro_class,
                yearly_l=e.yearly_l,
            )
            for e in report.top_emitters
        ],
        vehicle_count=report.vehicle_count,
    )

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key,
                settings.EXECUTIVE_CACHE_TTL_S,
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("Carbon cache write failed: %s", exc)

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_viewed",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "endpoint": "carbon",
                "days": days,
                "total_co2_kg": report.total_co2_kg,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Carbon audit failed: %s", exc)

    return response


@router.get("/compliance", response_model=ComplianceHeatmapResponse)
async def get_compliance_heatmap(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
    days_horizon: int = 90,
) -> ComplianceHeatmapResponse:
    """E.4 — Compliance heatmap v1 (muayene takibi).

    Args:
        days_horizon: bugünden N gün ileri pencere (default 90, 7-365)

    v1 yalnız muayene; SRC/K1/tachograph backlog'da.
    """
    _ensure_enabled()
    if days_horizon < 7 or days_horizon > 365:
        raise HTTPException(
            status_code=400,
            detail="days_horizon 7-365 arası olmalı",
        )

    # 30 dk cache (days_horizon bazında ayrı key)
    redis_client = await _get_redis()
    cache_key = f"executive:compliance:{days_horizon}"
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return ComplianceHeatmapResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("Compliance cache read failed: %s", exc)

    async with UnitOfWork() as uow:
        items = await scan_compliance(uow, days_horizon=days_horizon)

    overdue = sum(1 for i in items if i.risk_level == "overdue")
    soon = sum(1 for i in items if i.risk_level == "soon")
    response = ComplianceHeatmapResponse(
        days_horizon=days_horizon,
        total_items=len(items),
        overdue_count=overdue,
        soon_count=soon,
        items=[
            ComplianceItemResponse(
                entity_type=i.entity_type,
                entity_id=i.entity_id,
                plaka=i.plaka,
                field=i.field,
                expiry_date=i.expiry_date,
                days_until=i.days_until,
                risk_level=i.risk_level,
            )
            for i in items
        ],
    )

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key,
                settings.EXECUTIVE_CACHE_TTL_S,
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("Compliance cache write failed: %s", exc)

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_viewed",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "endpoint": "compliance",
                "days_horizon": days_horizon,
                "total_items": len(items),
                "overdue_count": overdue,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Compliance audit failed: %s", exc)

    return response


@router.get("/cashflow", response_model=CashflowProjectionResponse)
async def get_cashflow_projection(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
    days: int = 90,
) -> CashflowProjectionResponse:
    """E.5 — 90 gün cashflow projeksiyonu.

    2 kalem aktif: yakıt (aktif planlı seferlerin tahmini × diesel fiyat) +
    bakım (D.1 predictions × avg maliyet). Ceza (trafik/idari) kalemi
    cezalar tablosu eklenince aktive olur — şimdilik response'ta
    `penalty_data_available=false` ve `total_penalty_tl=null`.

    Args:
        days: ileri pencere (default 90, 14-365 arası).
    """
    _ensure_enabled()
    if days < 14 or days > 365:
        raise HTTPException(
            status_code=400, detail="days parametresi 14-365 arası olmalı"
        )

    # 30 dk cache (days bazında ayrı key)
    redis_client = await _get_redis()
    cache_key = f"executive:cashflow:{days}"
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return CashflowProjectionResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("Cashflow cache read failed: %s", exc)

    async with UnitOfWork() as uow:
        projection = await project_cashflow(
            uow,
            horizon_days=days,
            diesel_price_tl=settings.LITRE_DIESEL_TL,
            avg_bakim_cost_fallback_tl=settings.AVG_BAKIM_COST_TL,
        )

    response = CashflowProjectionResponse(
        horizon_days=projection.horizon_days,
        weeks=[
            CashflowWeekResponse(
                week_start=w.week_start,
                fuel_tl=w.fuel_tl,
                maintenance_tl=w.maintenance_tl,
                penalty_tl=w.penalty_tl,
                total_tl=w.total_tl,
            )
            for w in projection.weeks
        ],
        total_fuel_tl=projection.total_fuel_tl,
        total_maintenance_tl=projection.total_maintenance_tl,
        total_penalty_tl=projection.total_penalty_tl,
        grand_total_tl=projection.grand_total_tl,
        confidence=projection.confidence,
        assumptions=projection.assumptions,
    )

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key,
                settings.EXECUTIVE_CACHE_TTL_S,
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("Cashflow cache write failed: %s", exc)

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_viewed",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "endpoint": "cashflow",
                "days": days,
                "grand_total_tl": projection.grand_total_tl,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Cashflow audit failed: %s", exc)

    return response


@router.get("/cross-feature", response_model=CrossFeatureImpactResponse)
async def get_cross_feature_impact(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
    days: int = 90,
) -> CrossFeatureImpactResponse:
    """E.6 — D.4 + A.5 + B cross-feature impact aggregator.

    Args:
        days: lookback penceresi (default 90, 14-365 arası).
    """
    _ensure_enabled()
    if days < 14 or days > 365:
        raise HTTPException(
            status_code=400, detail="days parametresi 14-365 arası olmalı"
        )

    # 30 dk cache
    redis_client = await _get_redis()
    cache_key = f"executive:cross-feature:{days}"
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return CrossFeatureImpactResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("Cross-feature cache read failed: %s", exc)

    async with UnitOfWork() as uow:
        impact = await aggregate_cross_feature(
            uow,
            period_days=days,
            diesel_price_tl=settings.LITRE_DIESEL_TL,
        )

    response = CrossFeatureImpactResponse(
        period_days=impact.period_days,
        maintenance_delay_loss_tl=impact.maintenance_delay_loss_tl,
        coaching_savings_tl=impact.coaching_savings_tl,
        theft_loss_tl=impact.theft_loss_tl,
        confidence=impact.confidence,
    )

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key,
                settings.EXECUTIVE_CACHE_TTL_S,
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("Cross-feature cache write failed: %s", exc)

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_viewed",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "endpoint": "cross-feature",
                "days": days,
                "maintenance_delay_loss_tl": impact.maintenance_delay_loss_tl,
                "theft_loss_tl": impact.theft_loss_tl,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Cross-feature audit failed: %s", exc)

    return response


@router.get("/bus-factor", response_model=BusFactorResponse)
async def get_bus_factor(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
    n: int = 3,
) -> BusFactorResponse:
    """E.7 — Top-N şoför ayrılırsa filo verim kaybı.

    PII koruma (plan §15): yanıtta yalnız skor + yıllık km döner;
    şoför adı/ID döndürülmez.

    Args:
        n: top-N şoför (default 3, 1-10 arası).
    """
    _ensure_enabled()
    if n < 1 or n > 10:
        raise HTTPException(status_code=400, detail="n parametresi 1-10 arası olmalı")

    # 30 dk cache (n bazında ayrı key)
    redis_client = await _get_redis()
    cache_key = f"executive:bus-factor:{n}"
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return BusFactorResponse(**json.loads(cached))
        except Exception as exc:
            logger.warning("Bus-factor cache read failed: %s", exc)

    async with UnitOfWork() as uow:
        report = await compute_bus_factor(
            uow,
            n=n,
            diesel_price_tl=settings.LITRE_DIESEL_TL,
        )

    response = BusFactorResponse(
        n=report.n,
        top_n_drivers_loss_tl=report.top_n_drivers_loss_tl,
        top_n_drivers=[
            TopDriverAnonymized(score=d["score"], yearly_km=d["yearly_km"])
            for d in report.top_n_drivers
        ],
        bottlenecked_routes=report.bottlenecked_routes,
        risk_level=cast("RiskLevelBus", report.risk_level),
    )

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key,
                settings.EXECUTIVE_CACHE_TTL_S,
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("Bus-factor cache write failed: %s", exc)

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_viewed",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "endpoint": "bus-factor",
                "n": n,
                "loss_tl": report.top_n_drivers_loss_tl,
                "risk_level": report.risk_level,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Bus-factor audit failed: %s", exc)

    return response


@router.get(
    "/pdf",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "CEO 1-pager A4 PDF",
        },
    },
)
async def download_executive_pdf(
    current_user: Annotated[
        Kullanici,
        Depends(require_yetki(["super_admin", "fleet_manager", "yonetim_rapor"])),
    ],
) -> Response:
    """E.9 — CEO 1-pager A4 PDF.

    İçerik: FVI + 90g cashflow + cross-feature etki + top what-if.
    Plan §15: cache'lenmez, audit'e yazılır.
    """
    _ensure_enabled()

    # Tüm motorları paralel çağırma — hata gracefull (eksik kalemler '—'
    # gösterilir, plan §12 spec)
    fvi_dict: dict[str, object] | None = None
    cashflow_dict: dict[str, object] | None = None
    cross_dict: dict[str, object] | None = None

    async with UnitOfWork() as uow:
        try:
            inputs = await gather_fvi_inputs(uow, days_back=30)
            breakdown = compute_fvi(
                fuel_avg=(
                    float(inputs["fuel_avg"])
                    if inputs["fuel_avg"] is not None
                    else None
                ),
                fuel_target=(
                    float(inputs["target"]) if inputs["target"] is not None else None
                ),
                overdue_maintenance=int(inputs["overdue_count"] or 0),
                total_active_vehicles=int(inputs["total_active"] or 0),
                driver_avg_hybrid=(
                    float(inputs["driver_avg"])
                    if inputs["driver_avg"] is not None
                    else None
                ),
                resolved_anomalies=int(inputs["resolved"] or 0),
                acked_anomalies=int(inputs["acked"] or 0),
                total_anomalies=int(inputs["total_anomalies"] or 0),
            )
            fvi_dict = {
                "fvi": breakdown.fvi,
                "fuel_score": breakdown.fuel_score,
                "maintenance_score": breakdown.maintenance_score,
                "driver_score": breakdown.driver_score,
                "anomaly_quality_score": breakdown.anomaly_quality_score,
                "trend_30d": breakdown.trend_30d,
            }
        except Exception as exc:
            logger.warning("PDF FVI fetch failed: %s", exc)

        try:
            cashflow = await project_cashflow(
                uow,
                horizon_days=90,
                diesel_price_tl=settings.LITRE_DIESEL_TL,
                avg_bakim_cost_fallback_tl=settings.AVG_BAKIM_COST_TL,
            )
            cashflow_dict = {
                "total_fuel_tl": cashflow.total_fuel_tl,
                "total_maintenance_tl": cashflow.total_maintenance_tl,
                "total_penalty_tl": cashflow.total_penalty_tl,
                "grand_total_tl": cashflow.grand_total_tl,
            }
        except Exception as exc:
            logger.warning("PDF cashflow fetch failed: %s", exc)

        try:
            impact = await aggregate_cross_feature(
                uow,
                period_days=90,
                diesel_price_tl=settings.LITRE_DIESEL_TL,
            )
            cross_dict = {
                "maintenance_delay_loss_tl": impact.maintenance_delay_loss_tl,
                "coaching_savings_tl": impact.coaching_savings_tl,
                "theft_loss_tl": impact.theft_loss_tl,
            }
        except Exception as exc:
            logger.warning("PDF cross-feature fetch failed: %s", exc)

    pdf_bytes = await asyncio.to_thread(
        generate_executive_pdf,
        fvi=fvi_dict,
        cashflow=cashflow_dict,
        cross_feature=cross_dict,
        what_if_top=None,  # v1: kullanıcı UI'da what-if çalıştırıp seçmiş olabilir
        generated_date=None,
    )

    creator_id = current_user.id if current_user.id and current_user.id > 0 else None
    try:
        await log_audit_event(
            action="executive_pdf_downloaded",
            module="executive",
            entity_id=None,
            user_id=creator_id,
            new_value={
                "size_bytes": len(pdf_bytes),
                "has_fvi": fvi_dict is not None,
                "has_cashflow": cashflow_dict is not None,
                "has_cross": cross_dict is not None,
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("PDF audit failed: %s", exc)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": ('attachment; filename="executive-cockpit.pdf"'),
            # Plan §15: cache'lenmez
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )
