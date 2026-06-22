import {
  getFleetEfficiencyIndexApiV1ReportsExecutiveKpiGet,
  runWhatIfApiV1ReportsExecutiveWhatIfPost,
  getFleetCarbonApiV1ReportsExecutiveCarbonGet,
  getComplianceHeatmapApiV1ReportsExecutiveComplianceGet,
  getCashflowProjectionApiV1ReportsExecutiveCashflowGet,
  getCrossFeatureImpactApiV1ReportsExecutiveCrossFeatureGet,
  getBusFactorApiV1ReportsExecutiveBusFactorGet,
} from "../generated/api/executive/executive";
import axiosInstance from "../services/api/axios-instance";

// ── Types (backend schemas ↔ frontend; plan §11 contract) ──────────────

export interface FleetEfficiencyResponse {
  fvi: number;
  fuel_score: number;
  maintenance_score: number;
  driver_score: number;
  anomaly_quality_score: number;
  confidence: number;
  trend_30d: number | null;
  reasons: string[];
  computed_at: string;
}

export type WhatIfScenarioType =
  | "fleet_renewal"
  | "training"
  | "route_portfolio";

export interface FleetRenewalInputs {
  max_age_years: number;
  replacement_cost_per_vehicle_tl: number;
  expected_l_100km_improvement_pct?: number;
  diesel_price_tl?: number;
}

export interface TrainingInputs {
  improvement_pct: number;
  training_cost_per_driver_tl: number;
  diesel_price_tl?: number;
}

export interface RoutePortfolioInputs {
  drop_bottom_n: number;
  iterations?: number;
  diesel_price_tl?: number;
}

export interface WhatIfRequest {
  scenario_type: WhatIfScenarioType;
  fleet_renewal?: FleetRenewalInputs;
  training?: TrainingInputs;
  route_portfolio?: RoutePortfolioInputs;
}

export interface MonteCarloBand {
  p10: number;
  p50: number;
  p90: number;
  iterations: number;
}

export interface WhatIfResponse {
  scenario_type: WhatIfScenarioType;
  inputs: Record<string, unknown>;
  yearly_savings_tl: number;
  upfront_cost_tl: number;
  payback_years: number | null;
  five_year_roi_pct: number;
  co2_reduction_kg: number;
  confidence: number;
  monte_carlo: MonteCarloBand | null;
  reasons: string[];
}

export interface TopEmitter {
  plaka: string;
  co2_kg: number;
  euro_class: string;
  yearly_l: number;
}

export interface FleetCarbonResponse {
  period_start: string;
  period_end: string;
  total_co2_kg: number;
  total_km: number;
  co2_per_km: number;
  benchmark_co2_per_km: number;
  delta_pct: number;
  by_euro_class: Record<string, number>;
  top_emitters: TopEmitter[];
  vehicle_count: number;
}

export type ComplianceRisk = "overdue" | "soon" | "normal" | "low";

export interface ComplianceItem {
  entity_type: "arac" | "dorse";
  entity_id: number;
  plaka: string;
  field: string;
  expiry_date: string;
  days_until: number;
  risk_level: ComplianceRisk;
}

export interface ComplianceHeatmapResponse {
  days_horizon: number;
  total_items: number;
  overdue_count: number;
  soon_count: number;
  items: ComplianceItem[];
}

export interface CashflowWeek {
  week_start: string;
  fuel_tl: number;
  maintenance_tl: number;
  penalty_tl: number;
  total_tl: number;
}

export interface CashflowProjectionResponse {
  horizon_days: number;
  weeks: CashflowWeek[];
  total_fuel_tl: number;
  total_maintenance_tl: number;
  total_penalty_tl: number;
  grand_total_tl: number;
  confidence: number;
  assumptions: Record<string, number>;
}

export interface CrossFeatureImpactResponse {
  period_days: number;
  maintenance_delay_loss_tl: number;
  coaching_savings_tl: number;
  theft_loss_tl: number;
  confidence: number;
}

export type BusFactorRisk = "high" | "medium" | "low";

export interface TopDriverAnonymized {
  score: number;
  yearly_km: number;
}

export interface BusFactorResponse {
  n: number;
  top_n_drivers_loss_tl: number;
  top_n_drivers: TopDriverAnonymized[];
  bottlenecked_routes: Array<Record<string, unknown>>;
  risk_level: BusFactorRisk;
}

// ── API wrapper ────────────────────────────────────────────────────────

export const executiveService = {
  getFvi: async (): Promise<FleetEfficiencyResponse> => {
    const data = await getFleetEfficiencyIndexApiV1ReportsExecutiveKpiGet();
    return data as unknown as FleetEfficiencyResponse;
  },

  runWhatIf: async (payload: WhatIfRequest): Promise<WhatIfResponse> => {
    const data = await runWhatIfApiV1ReportsExecutiveWhatIfPost(
      payload as unknown as Parameters<
        typeof runWhatIfApiV1ReportsExecutiveWhatIfPost
      >[0],
    );
    return data as unknown as WhatIfResponse;
  },

  getCarbon: async (days = 30): Promise<FleetCarbonResponse> => {
    const data = await getFleetCarbonApiV1ReportsExecutiveCarbonGet({ days });
    return data as unknown as FleetCarbonResponse;
  },

  getCompliance: async (
    daysHorizon = 90,
  ): Promise<ComplianceHeatmapResponse> => {
    const data = await getComplianceHeatmapApiV1ReportsExecutiveComplianceGet({
      days_horizon: daysHorizon,
    });
    return data as unknown as ComplianceHeatmapResponse;
  },

  getCashflow: async (days = 90): Promise<CashflowProjectionResponse> => {
    const data = await getCashflowProjectionApiV1ReportsExecutiveCashflowGet({
      days,
    });
    return data as unknown as CashflowProjectionResponse;
  },

  getCrossFeature: async (days = 90): Promise<CrossFeatureImpactResponse> => {
    const data =
      await getCrossFeatureImpactApiV1ReportsExecutiveCrossFeatureGet({ days });
    return data as unknown as CrossFeatureImpactResponse;
  },

  getBusFactor: async (n = 3): Promise<BusFactorResponse> => {
    const data = await getBusFactorApiV1ReportsExecutiveBusFactorGet({ n });
    return data as unknown as BusFactorResponse;
  },

  /** E.9 — CEO 1-pager PDF (blob download). */
  downloadPdf: async (): Promise<void> => {
    const r = await axiosInstance.get("/reports/executive/pdf", {
      responseType: "blob",
    });
    const blob = new Blob([r.data], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `executive-cockpit-${new Date()
      .toISOString()
      .slice(0, 10)}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
