import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# A component sources its Turkish copy from resource files if it either imports the
# domain resource module directly (resources/tr/<domain>) OR consumes the
# locale-aware use<Domain>Resources hook (backed by resources/useResources). Both
# satisfy the "no hardcoded Turkish copy" guard; the hook is the current pattern.
_RESOURCE_HOOK_RE = re.compile(r"use[A-Z]\w*Resources")


def _sources_copy_from_resources(text: str, direct_import: str) -> bool:
    return direct_import in text or bool(_RESOURCE_HOOK_RE.search(text))


LEGACY_REAL_FLAG = "is" + "_real"
LEGACY_REAL_FIELD = "is" + "_real: bool = Field(True)"
LEGACY_REAL_OPTIONAL = "is" + "_real: Optional[bool] = None"
LEGACY_REAL_ENTITY = "is" + "_real: bool = True"
LEGACY_REAL_ASSIGNMENT = "is" + "_real=data.is" + "_real"
LEGACY_REAL_FALLBACK = 'ref_sefer.get("is' + '_real", True)'


def test_frontend_runtime_no_longer_imports_legacy_api_module():
    frontend_root = ROOT / "frontend" / "src"
    offenders = [
        path
        for path in frontend_root.rglob("*.ts*")
        if "services/api/legacy" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_runtime_remnant_files_were_deleted():
    deleted_runtime_files = [
        ROOT / "frontend" / "src" / "services" / "api" / "legacy.ts",
        ROOT / "frontend" / "src" / "components" / "vehicles" / "VehicleStatusCard.tsx",
        ROOT / "frontend" / "src" / "services" / "mockData.ts",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "locations"
        / "LocationAnalyzeModal.tsx",
        ROOT / "frontend" / "src" / "components" / "trips" / "NewTripStepper.tsx",
        ROOT / "frontend" / "src" / "components" / "trips" / "SmartRouteAnalysis.tsx",
        ROOT / "frontend" / "src" / "components" / "drivers" / "DriverCard.tsx",
        ROOT / "frontend" / "src" / "components" / "vehicles" / "VehicleGridView.tsx",
        ROOT / "app" / "schemas" / "sefer.py.mangled",
    ]
    assert [
        str(path.relative_to(ROOT)) for path in deleted_runtime_files if path.exists()
    ] == []


def test_non_production_generators_and_benchmarks_were_deleted():
    deleted_paths = [
        ROOT / "scripts" / "benchmark_models.py",
        ROOT / "scripts" / "cleanup_test_data.py",
        ROOT / "scripts" / "compare_models.py",
        ROOT / "scripts" / "generate_complex_data.py",
        ROOT / "scripts" / "generate_pg_complex_data.py",
        ROOT / "scripts" / "generate_sync_data.py",
        ROOT / "scripts" / "locustfile.py",
        ROOT / "scripts" / "seed_real_data.py",
        ROOT / "scripts" / "synthesize_20k_realistic.py",
        ROOT / "scripts" / "synthesize_elite_data.py",
        ROOT / "scripts" / "train_demo_model.py",
        ROOT / "scripts" / "retraining" / "compare_old_vs_new.py",
    ]

    assert [
        str(path.relative_to(ROOT)) for path in deleted_paths if path.exists()
    ] == []


def test_active_pages_do_not_render_known_placeholder_copy():
    locations_page = (
        ROOT / "frontend" / "src" / "pages" / "LocationsPage.tsx"
    ).read_text(encoding="utf-8")
    overview_page = (
        ROOT / "frontend" / "src" / "pages" / "admin" / "OverviewPage.tsx"
    ).read_text(encoding="utf-8")
    roi_calculator = (
        ROOT / "frontend" / "src" / "components" / "reports" / "ROICalculator.tsx"
    ).read_text(encoding="utf-8")
    trailer_detail_modal = (
        ROOT / "frontend" / "src" / "components" / "trailers" / "TrailerDetailModal.tsx"
    ).read_text(encoding="utf-8")
    location_list = (
        ROOT / "frontend" / "src" / "components" / "locations" / "LocationList.tsx"
    ).read_text(encoding="utf-8")

    assert "Map Simulation" not in locations_page
    assert "CanlÄ± Åebeke Analizi" not in locations_page
    assert "Ã§ok yakÄ±nda" not in overview_page
    assert "YatÄ±rÄ±m SimÃ¼lasyonu" not in roi_calculator
    assert "YakÄ±nda:" not in trailer_detail_modal
    assert "SÄ°MÃœLASYON" not in location_list


def test_reports_route_uses_resource_only_turkish_copy():
    expected_resource_imports = {
        ROOT / "frontend" / "src" / "pages" / "ReportsPage.tsx": "resources/tr/reports",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "reports"
        / "ReportCards.tsx": "resources/tr/reports",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "shared"
        / "ExportDialog.tsx": "resources/tr/reports",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "reports"
        / "CostAnalysisChart.tsx": "resources/tr/reports",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "reports"
        / "ROICalculator.tsx": "resources/tr/reports",
    }
    for path, resource_import in expected_resource_imports.items():
        text = path.read_text(encoding="utf-8")
        assert _sources_copy_from_resources(text, resource_import), path


def test_active_foundation_routes_use_resource_only_turkish_copy():
    expected_resource_imports = {
        ROOT / "frontend" / "src" / "pages" / "FleetPage.tsx": "resources/tr/fleet",
        ROOT / "frontend" / "src" / "pages" / "FuelPage.tsx": "resources/tr/fuel",
        ROOT / "frontend" / "src" / "pages" / "TripsPage.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "LocationsPage.tsx": "resources/tr/locations",
        ROOT
        / "frontend"
        / "src"
        / "features"
        / "trips"
        / "TripsModule.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "fleet"
        / "FleetInsights.tsx": "resources/tr/fleet",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "modules"
        / "VehiclesModule.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "modules"
        / "DriversModule.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "modules"
        / "TrailersModule.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "OverviewPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "KonfigurasyonPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "KullanicilarPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "MLYonetimPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "BakimPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "VeriYonetimPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "BildirimlerPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "SistemSaglikPage.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "pages"
        / "admin"
        / "AdminLayout.tsx": "resources/tr/admin",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "fuel"
        / "FuelModal.tsx": "resources/tr/fuel",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "fuel"
        / "FuelTable.tsx": "resources/tr/fuel",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "fuel"
        / "FuelPagination.tsx": "resources/tr/fuel",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "fuel"
        / "ComparisonWidget.tsx": "resources/tr/fuel",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "vehicles"
        / "VehicleHeader.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "vehicles"
        / "VehicleFilters.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "vehicles"
        / "VehicleTable.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "vehicles"
        / "VehicleModal.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "vehicles"
        / "VehicleDetailModal.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "vehicles"
        / "VehicleDeleteModal.tsx": "resources/tr/vehicles",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverHeader.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverFilters.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverTable.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverGrid.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverModal.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverScoreModal.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "drivers"
        / "DriverPerformanceModal.tsx": "resources/tr/drivers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trailers"
        / "TrailerHeader.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trailers"
        / "TrailerFilters.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trailers"
        / "TrailerTable.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trailers"
        / "TrailerModal.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trailers"
        / "TrailerDetailModal.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trailers"
        / "TrailerDeleteModal.tsx": "resources/tr/trailers",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "locations"
        / "LocationList.tsx": "resources/tr/locations",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "locations"
        / "LocationFormModal.tsx": "resources/tr/locations",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "locations"
        / "AnalysisModal.tsx": "resources/tr/locations",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "locations"
        / "RouteAnalysisCard.tsx": "resources/tr/locations",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripHeader.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripFilters.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripTable.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripStats.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripAnalytics.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripFormModal.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripTimeline.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "BulkActionBar.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "BulkStatusModal.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "BulkCancelModal.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TelemetrySection.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripList.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripForm"
        / "DateTimeSection.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripForm"
        / "RouteSelector.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripForm"
        / "StaffVehicleSection.tsx": "resources/tr/trips",
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "trips"
        / "TripForm"
        / "LoadManagementSection.tsx": "resources/tr/trips",
    }
    for path, resource_import in expected_resource_imports.items():
        text = path.read_text(encoding="utf-8")
        assert _sources_copy_from_resources(text, resource_import), path


def test_backend_truthfulness_guards_hold_for_time_series_and_route_matching():
    time_series_service = (
        ROOT
        / "v2"
        / "modules"
        / "prediction_ml"
        / "application"
        / "time_series_service.py"
    ).read_text(encoding="utf-8")
    route_calibration_service = (
        ROOT / "app" / "core" / "services" / "route_calibration_service.py"
    ).read_text(encoding="utf-8")
    route_service = (
        ROOT
        / "v2"
        / "modules"
        / "route_simulation"
        / "application"
        / "get_route_details.py"
    ).read_text(encoding="utf-8")
    weather_service = (
        ROOT / "app" / "core" / "services" / "weather_service.py"
    ).read_text(encoding="utf-8")
    lightgbm_predictor = (
        ROOT / "v2" / "modules" / "prediction_ml" / "domain" / "lightgbm_predictor.py"
    ).read_text(encoding="utf-8")
    sefer_repo = (
        ROOT / "v2" / "modules" / "trip" / "infrastructure" / "repository.py"
    ).read_text(encoding="utf-8")

    assert "Cold-Start-Mock" not in time_series_service
    assert "Mock-Fallback" not in time_series_service
    assert "falling back to mock data" not in time_series_service
    assert '"matches": True' not in route_calibration_service
    assert "offline_fallback" not in route_service
    assert "prediction * 0.08" not in lightgbm_predictor
    assert "include_synthetic" not in sefer_repo
    assert "Mevsimsel Tahmin" not in weather_service
    assert not (
        ROOT / "frontend" / "src" / "components" / "trips" / "SmartRouteAnalysis.tsx"
    ).exists()


def test_runtime_components_do_not_use_randomized_input_ids():
    input_component = (
        ROOT / "frontend" / "src" / "components" / "ui" / "Input.tsx"
    ).read_text(encoding="utf-8")

    assert "Math.random" not in input_component


def test_frontend_public_trip_contract_no_longer_exposes_is_real():
    trip_types = (ROOT / "frontend" / "src" / "types" / "index.ts").read_text(
        encoding="utf-8"
    )
    trip_schema = (ROOT / "frontend" / "src" / "schemas" / "entities.ts").read_text(
        encoding="utf-8"
    )
    trip_form_modal = (
        ROOT / "frontend" / "src" / "components" / "trips" / "TripFormModal.tsx"
    ).read_text(encoding="utf-8")
    trips_module = (
        ROOT / "frontend" / "src" / "features" / "trips" / "TripsModule.tsx"
    ).read_text(encoding="utf-8")

    assert LEGACY_REAL_FLAG not in trip_types
    assert LEGACY_REAL_FLAG not in trip_schema
    assert LEGACY_REAL_FLAG not in trip_form_modal
    assert LEGACY_REAL_FLAG not in trips_module


def test_backend_trip_contract_no_longer_exposes_is_real():
    """dalga 14/16'da trip modülüne taşındı: app/schemas/sefer.py ->
    v2/modules/trip/schemas.py, app/core/entities/models.py ->
    v2/modules/trip/domain/entities.py, app/core/services/
    sefer_write_service.py (B.1'de dissolve edildi) -> v2/modules/trip/
    application/*.py (tüm dosyalar birleşik taranır)."""
    trip_schema = (ROOT / "v2" / "modules" / "trip" / "schemas.py").read_text(
        encoding="utf-8"
    )
    trip_entities = (
        ROOT / "v2" / "modules" / "trip" / "domain" / "entities.py"
    ).read_text(encoding="utf-8")
    trip_application = "".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "v2" / "modules" / "trip" / "application").glob("*.py")
    )

    assert LEGACY_REAL_FIELD not in trip_schema
    assert LEGACY_REAL_OPTIONAL not in trip_schema
    assert LEGACY_REAL_ENTITY not in trip_entities
    assert LEGACY_REAL_OPTIONAL not in trip_entities
    assert LEGACY_REAL_ASSIGNMENT not in trip_application
    assert LEGACY_REAL_FALLBACK not in trip_application


def test_runtime_and_persistence_layers_no_longer_reference_is_real():
    db_models = (ROOT / "app" / "database" / "models.py").read_text(encoding="utf-8")
    trip_repo = (
        ROOT / "v2" / "modules" / "trip" / "infrastructure" / "repository.py"
    ).read_text(encoding="utf-8")
    analytics_repo = (
        ROOT
        / "v2"
        / "modules"
        / "analytics_executive"
        / "infrastructure"
        / "executive_read_models.py"
    ).read_text(encoding="utf-8")
    vehicle_repo = (
        ROOT / "v2" / "modules" / "fleet" / "infrastructure" / "vehicle_repository.py"
    ).read_text(encoding="utf-8")
    test_conftest = (ROOT / "app" / "tests" / "conftest.py").read_text(encoding="utf-8")
    training_contracts = (
        ROOT / "app" / "tests" / "unit" / "test_ml_training_contracts.py"
    ).read_text(encoding="utf-8")
    training_script = (ROOT / "scripts" / "train_ensemble.py").read_text(
        encoding="utf-8"
    )

    assert LEGACY_REAL_FLAG not in db_models
    assert LEGACY_REAL_FLAG not in trip_repo
    assert LEGACY_REAL_FLAG not in analytics_repo
    assert LEGACY_REAL_FLAG not in vehicle_repo
    assert LEGACY_REAL_FLAG not in test_conftest
    assert LEGACY_REAL_FLAG not in training_contracts
    assert LEGACY_REAL_FLAG not in training_script
