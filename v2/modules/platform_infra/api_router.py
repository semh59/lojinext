"""Router-aggregation composition root (~50 include_router calls, zero
business logic) — moved from app/api/v1/api.py 2026-07-22 (Kalem 3 commit 3),
same "pure composition-root" category as container.py. Mechanical move,
router-ordering + include_router calls preserved byte-for-byte (see the
trip_read_router ordering note below — never reorder without re-reading it).
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    feedback,
)
from v2.modules.admin_platform.api.admin_config_routes import (
    router as admin_config_router,
)
from v2.modules.admin_platform.api.admin_health_routes import (
    router as admin_health_router,
)
from v2.modules.admin_platform.api.admin_integrations_routes import (
    router as admin_integrations_router,
)
from v2.modules.admin_platform.api.admin_ws_routes import (
    router as admin_ws_router,
)
from v2.modules.admin_platform.api.error_stream_routes import (
    router as error_stream_router,
)
from v2.modules.admin_platform.api.health_routes import router as health_router
from v2.modules.admin_platform.api.internal_routes import router as internal_router
from v2.modules.admin_platform.api.system_routes import router as system_router
from v2.modules.ai_assistant.api.plan_wizard_routes import (
    router as plan_wizard_router,
)
from v2.modules.analytics_executive.api.executive_routes import (
    router as executive_router,
)
from v2.modules.analytics_executive.api.trip_analytics_routes import (
    router as trip_analytics_router,
)
from v2.modules.anomaly.api.anomaly_routes import router as anomalies_router
from v2.modules.anomaly.api.attribution_routes import (
    router as admin_attribution_router,
)
from v2.modules.anomaly.api.investigation_routes import (
    router as investigations_router,
)
from v2.modules.auth_rbac.api.admin_role_routes import router as admin_roles_router
from v2.modules.auth_rbac.api.admin_user_routes import router as admin_users_router
from v2.modules.auth_rbac.api.auth_routes import router as auth_router
from v2.modules.auth_rbac.api.preference_routes import router as preferences_router
from v2.modules.auth_rbac.api.user_routes import router as users_router
from v2.modules.auth_rbac.api.ws_ticket_routes import router as ws_ticket_router
from v2.modules.driver.api.coaching_routes import router as coaching_router
from v2.modules.driver.api.driver_routes import router as driver_router
from v2.modules.fleet.api.admin_maintenance_routes import (
    router as admin_maintenance_router,
)
from v2.modules.fleet.api.maintenance_routes import router as maintenance_router
from v2.modules.fleet.api.trailer_routes import router as trailer_router
from v2.modules.fleet.api.vehicle_routes import router as vehicle_router
from v2.modules.fuel.api.fuel_routes import admin_router as admin_fuel_accuracy
from v2.modules.fuel.api.fuel_routes import router as fuel_router
from v2.modules.import_excel.api.import_routes import router as import_router
from v2.modules.import_excel.api.trip_export_routes import (
    router as trip_export_router,
)
from v2.modules.import_excel.api.trip_import_routes import (
    router as trip_import_router,
)
from v2.modules.location.api.location_routes import router as location_router
from v2.modules.notification.api.live_ws_routes import (
    router as notification_live_ws_router,
)
from v2.modules.notification.api.notification_routes import (
    router as notification_router,
)
from v2.modules.notification.api.push_routes import router as push_router
from v2.modules.prediction_ml.api.admin_ml import router as admin_ml_router
from v2.modules.prediction_ml.api.admin_pilot import router as admin_pilot_router
from v2.modules.prediction_ml.api.admin_predictions import (
    router as admin_predictions_router,
)
from v2.modules.prediction_ml.api.predictions import router as predictions_router
from v2.modules.reports.api.advanced_reports_routes import (
    router as advanced_reports_router,
)
from v2.modules.reports.api.dashboard_routes import router as reports_router
from v2.modules.reports.api.fleet_insights_routes import (
    router as fleet_insights_router,
)
from v2.modules.reports.api.page_view_routes import (
    admin_router as page_view_admin_router,
)
from v2.modules.reports.api.page_view_routes import router as page_view_router
from v2.modules.reports.api.studio_routes import router as reports_studio_router
from v2.modules.reports.api.triage_routes import router as today_triage_router
from v2.modules.route_simulation.api.admin_calibration_routes import (
    router as admin_calibration_router,
)
from v2.modules.route_simulation.api.route_routes import router as route_router
from v2.modules.route_simulation.api.weather_routes import router as weather_router
from v2.modules.trip.api.trip_approval_routes import router as trip_approval_router
from v2.modules.trip.api.trip_bulk_routes import router as trip_bulk_router
from v2.modules.trip.api.trip_read_routes import router as trip_read_router
from v2.modules.trip.api.trip_write_routes import router as trip_write_router

api_router = APIRouter()
api_router.include_router(route_router, prefix="/routes", tags=["routes"])
api_router.include_router(location_router, prefix="/locations", tags=["locations"])
api_router.include_router(
    maintenance_router, prefix="/maintenance", tags=["maintenance"]
)
api_router.include_router(weather_router, prefix="/weather", tags=["weather"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(
    admin_config_router, prefix="/admin/config", tags=["admin-config"]
)
api_router.include_router(
    admin_integrations_router,
    prefix="/admin/integrations",
    tags=["admin-integrations"],
)
api_router.include_router(
    admin_roles_router, prefix="/admin/roles", tags=["admin-roles"]
)
api_router.include_router(
    admin_users_router, prefix="/admin/users", tags=["admin-users"]
)
api_router.include_router(vehicle_router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(driver_router, prefix="/drivers", tags=["drivers"])
# NOT: trip_read_router EN SON eklenir — kendi ``GET /{sefer_id}`` catch-all
# route'u tek-segment bir path param'ı (FastAPI/Starlette route eşleşmesi
# kayıt SIRASINA göredir, otomatik specificity yok). Diğer router'ların
# ``GET /stats`` (trip_analytics_router) / ``GET /export`` (trip_export_router)
# gibi tek-segment literal path'leri trip_read_router'dan ÖNCE eklenmezse,
# `/{sefer_id}` bunları önce yakalar ve sefer_id=<literal> int-coercion'ı
# 422 ile patlar (bu regresyon `test_trip_contracts_and_bulk_flows`'ta
# bulundu ve düzeltildi — dalga 14).
api_router.include_router(trip_write_router, prefix="/trips", tags=["trips"])
api_router.include_router(trip_bulk_router, prefix="/trips", tags=["trips"])
api_router.include_router(trip_approval_router, prefix="/trips", tags=["trips"])
api_router.include_router(trip_export_router, prefix="/trips", tags=["trips"])
api_router.include_router(trip_import_router, prefix="/trips", tags=["trips"])
api_router.include_router(trip_analytics_router, prefix="/trips", tags=["trips"])
api_router.include_router(plan_wizard_router, prefix="/trips", tags=["trips"])
api_router.include_router(trip_read_router, prefix="/trips", tags=["trips"])
api_router.include_router(fuel_router, prefix="/fuel", tags=["fuel"])
api_router.include_router(
    predictions_router, prefix="/predictions", tags=["predictions"]
)
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(
    executive_router, prefix="/reports/executive", tags=["executive"]
)
api_router.include_router(anomalies_router, prefix="/anomalies", tags=["anomalies"])
api_router.include_router(coaching_router, prefix="/coaching", tags=["coaching"])
api_router.include_router(
    investigations_router,
    prefix="/admin/investigations",
    tags=["investigations"],
)
api_router.include_router(
    advanced_reports_router, prefix="/advanced-reports", tags=["advanced-reports"]
)
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])
api_router.include_router(ws_ticket_router, prefix="/ws", tags=["websocket"])
api_router.include_router(admin_ws_router, prefix="/admin/ws", tags=["admin-ws"])
api_router.include_router(
    notification_live_ws_router, prefix="/admin/ws", tags=["notifications"]
)
api_router.include_router(
    import_router, prefix="/admin/imports", tags=["admin-imports"]
)
api_router.include_router(admin_ml_router, prefix="/admin/ml", tags=["admin-ml"])
api_router.include_router(
    admin_attribution_router, prefix="/admin/attribution", tags=["admin-attribution"]
)
api_router.include_router(
    admin_calibration_router, prefix="/admin/calibration", tags=["admin-calibration"]
)
api_router.include_router(
    admin_fuel_accuracy, prefix="/admin", tags=["admin-fuel-accuracy"]
)
api_router.include_router(admin_pilot_router, prefix="/admin", tags=["admin-pilot"])
api_router.include_router(
    admin_predictions_router, prefix="/admin", tags=["admin-predictions"]
)
api_router.include_router(page_view_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(
    page_view_admin_router, prefix="/admin", tags=["admin-analytics"]
)
api_router.include_router(
    admin_maintenance_router, prefix="/admin/maintenance", tags=["admin-maintenance"]
)
api_router.include_router(
    notification_router,
    prefix="/admin/notifications",
    tags=["admin-notifications"],
)
api_router.include_router(
    admin_health_router, prefix="/admin/health", tags=["admin-health"]
)
api_router.include_router(trailer_router, prefix="/trailers", tags=["trailers"])
api_router.include_router(
    preferences_router, prefix="/preferences", tags=["preferences"]
)
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(
    today_triage_router, prefix="/reports/today", tags=["reports-v2"]
)
api_router.include_router(
    fleet_insights_router,
    prefix="/reports/insights/fleet",
    tags=["reports-v2"],
)
api_router.include_router(
    reports_studio_router,
    prefix="/reports/studio",
    tags=["reports-v2"],
)
api_router.include_router(push_router, prefix="/push", tags=["push"])
api_router.include_router(error_stream_router, prefix="/system", tags=["monitoring"])
api_router.include_router(internal_router, prefix="/internal", tags=["internal"])
