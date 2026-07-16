"""Public surface of the analytics_executive module.

Other modules that need to call into analytics_executive should import from
here, not from ``application/``, ``domain/``, or ``infrastructure/``
directly. This module is a pure read-model (no tablosuna yazmaz) — most
consumers (`driver`, `fuel`, `reports`, `anomaly`, `prediction_ml`) reach
`AnalizRepository`/`get_analiz_repo()` via `uow.analiz_repo` or a direct
import; this is documented as a temporary cross-module dependency in each
consumer's own CLAUDE.md (aynı location/route_simulation dalga 1'deki
geçici bağımlılık gerekçesi) and will be revisited once every module has
migrated (FAZ2 read-model SELECT-only rol talebi).
"""

from v2.modules.analytics_executive.application.aggregate_cross_feature import (
    CrossFeatureImpact,
    aggregate_cross_feature,
)
from v2.modules.analytics_executive.application.analyze_costs import (
    CostBreakdown,
    calculate_period_cost,
    calculate_roi,
    calculate_savings_potential,
    get_monthly_trend,
    get_vehicle_cost_comparison,
)
from v2.modules.analytics_executive.application.generate_insights import (
    Insight,
    generate_all_and_save,
)
from v2.modules.analytics_executive.application.get_bus_factor import (
    compute_bus_factor,
)
from v2.modules.analytics_executive.application.get_fleet_carbon import (
    FleetCarbonReport,
    compute_fleet_carbon,
)
from v2.modules.analytics_executive.application.get_fleet_efficiency import (
    gather_fvi_inputs,
)
from v2.modules.analytics_executive.application.project_cashflow import (
    CashflowProjection,
    project_cashflow,
)
from v2.modules.analytics_executive.application.scan_compliance import scan_compliance
from v2.modules.analytics_executive.application.simulate_what_if import (
    WhatIfResult,
    simulate_fleet_renewal,
    simulate_route_portfolio,
    simulate_training_program,
)
from v2.modules.analytics_executive.domain.bus_factor_scoring import BusFactorReport
from v2.modules.analytics_executive.domain.compliance_risk import ComplianceItem
from v2.modules.analytics_executive.domain.fleet_efficiency import (
    FleetEfficiencyBreakdown,
    compute_fvi,
)
from v2.modules.analytics_executive.infrastructure.executive_read_models import (
    AnalizRepository,
    get_analiz_repo,
)

__all__ = [
    "AnalizRepository",
    "BusFactorReport",
    "CashflowProjection",
    "ComplianceItem",
    "CostBreakdown",
    "CrossFeatureImpact",
    "FleetCarbonReport",
    "FleetEfficiencyBreakdown",
    "Insight",
    "WhatIfResult",
    "aggregate_cross_feature",
    "calculate_period_cost",
    "calculate_roi",
    "calculate_savings_potential",
    "compute_bus_factor",
    "compute_fleet_carbon",
    "compute_fvi",
    "gather_fvi_inputs",
    "generate_all_and_save",
    "get_analiz_repo",
    "get_monthly_trend",
    "get_vehicle_cost_comparison",
    "project_cashflow",
    "scan_compliance",
    "simulate_fleet_renewal",
    "simulate_route_portfolio",
    "simulate_training_program",
]
