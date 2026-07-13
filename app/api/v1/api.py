from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_attribution,
    admin_calibration,
    admin_config,
    admin_fuel_accuracy,
    admin_health,
    admin_imports,
    admin_integrations,
    admin_maintenance,
    admin_ml,
    admin_pilot,
    admin_predictions,
    admin_roles,
    admin_users,
    admin_ws,
    advanced_reports,
    ai,
    analytics,
    anomalies,
    auth,
    coaching,
    drivers,
    error_stream,
    executive,
    feedback,
    fleet_insights,
    fuel,
    health,
    internal,
    investigations,
    maintenance,
    predictions,
    preferences,
    reports,
    reports_studio,
    system,
    today_triage,
    trailers,
    trips,
    users,
    vehicles,
    weather,
    ws_ticket,
)
from v2.modules.location.api.location_routes import router as location_router
from v2.modules.notification.api.live_ws_routes import (
    router as notification_live_ws_router,
)
from v2.modules.notification.api.notification_routes import (
    router as notification_router,
)
from v2.modules.notification.api.push_routes import router as push_router
from v2.modules.route_simulation.api.route_routes import router as route_router

api_router = APIRouter()
api_router.include_router(route_router, prefix="/routes", tags=["routes"])
api_router.include_router(location_router, prefix="/locations", tags=["locations"])
api_router.include_router(
    maintenance.router, prefix="/maintenance", tags=["maintenance"]
)
api_router.include_router(weather.router, prefix="/weather", tags=["weather"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(
    admin_config.router, prefix="/admin/config", tags=["admin-config"]
)
api_router.include_router(
    admin_integrations.router,
    prefix="/admin/integrations",
    tags=["admin-integrations"],
)
api_router.include_router(
    admin_roles.router, prefix="/admin/roles", tags=["admin-roles"]
)
api_router.include_router(
    admin_users.router, prefix="/admin/users", tags=["admin-users"]
)
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["vehicles"])
api_router.include_router(drivers.router, prefix="/drivers", tags=["drivers"])
api_router.include_router(trips.router, prefix="/trips", tags=["trips"])
api_router.include_router(fuel.router, prefix="/fuel", tags=["fuel"])
api_router.include_router(
    predictions.router, prefix="/predictions", tags=["predictions"]
)
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(
    executive.router, prefix="/reports/executive", tags=["executive"]
)
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
api_router.include_router(coaching.router, prefix="/coaching", tags=["coaching"])
api_router.include_router(
    investigations.router,
    prefix="/admin/investigations",
    tags=["investigations"],
)
api_router.include_router(
    advanced_reports.router, prefix="/advanced-reports", tags=["advanced-reports"]
)
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI"])
api_router.include_router(ws_ticket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(admin_ws.router, prefix="/admin/ws", tags=["admin-ws"])
api_router.include_router(
    notification_live_ws_router, prefix="/admin/ws", tags=["notifications"]
)
api_router.include_router(
    admin_imports.router, prefix="/admin/imports", tags=["admin-imports"]
)
api_router.include_router(admin_ml.router, prefix="/admin/ml", tags=["admin-ml"])
api_router.include_router(
    admin_attribution.router, prefix="/admin/attribution", tags=["admin-attribution"]
)
api_router.include_router(
    admin_calibration.router, prefix="/admin/calibration", tags=["admin-calibration"]
)
api_router.include_router(
    admin_fuel_accuracy.router, prefix="/admin", tags=["admin-fuel-accuracy"]
)
api_router.include_router(admin_pilot.router, prefix="/admin", tags=["admin-pilot"])
api_router.include_router(
    admin_predictions.router, prefix="/admin", tags=["admin-predictions"]
)
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(
    analytics.admin_router, prefix="/admin", tags=["admin-analytics"]
)
api_router.include_router(
    admin_maintenance.router, prefix="/admin/maintenance", tags=["admin-maintenance"]
)
api_router.include_router(
    notification_router,
    prefix="/admin/notifications",
    tags=["admin-notifications"],
)
api_router.include_router(
    admin_health.router, prefix="/admin/health", tags=["admin-health"]
)
api_router.include_router(trailers.router, prefix="/trailers", tags=["trailers"])
api_router.include_router(
    preferences.router, prefix="/preferences", tags=["preferences"]
)
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(
    today_triage.router, prefix="/reports/today", tags=["reports-v2"]
)
api_router.include_router(
    fleet_insights.router,
    prefix="/reports/insights/fleet",
    tags=["reports-v2"],
)
api_router.include_router(
    reports_studio.router,
    prefix="/reports/studio",
    tags=["reports-v2"],
)
api_router.include_router(push_router, prefix="/push", tags=["push"])
api_router.include_router(error_stream.router, prefix="/system", tags=["monitoring"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
