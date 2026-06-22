import { planWizardApiV1TripsPlanWizardPost } from "../generated/api/trips/trips";
import type { PlanWizardRequest, PlanWizardResponse } from "../generated/types";

export type RiskLabel = "low" | "medium" | "high" | "unknown";
export type RouteType = "highway_dominant" | "mountain" | "urban" | "mixed";

export interface VehicleSuggestion {
  arac_id: number;
  plaka: string;
  yas: number;
  score: number;
  predicted_liters: number;
  fuel_score: number;
  route_history_score: number;
  vehicle_health_score: number;
  availability_score: number;
  similar_trip_count: number;
  cold_start: boolean;
  reasons?: string[];
}

export interface DriverSuggestion {
  sofor_id: number;
  ad_soyad: string;
  score: number;
  route_type_perf: number;
  overall_hybrid: number;
  availability_score: number;
  route_type: RouteType;
  deviation_pct: number;
  cold_start: boolean;
  reasons?: string[];
}

export interface PlanWizardRequestPayload {
  tarih: string; // YYYY-MM-DD
  guzergah_id?: number | null;
  cikis_yeri: string;
  varis_yeri: string;
  mesafe_km: number;
  ascent_m?: number;
  descent_m?: number;
  flat_distance_km?: number;
  weight_kg?: number;
  top_n?: number;
}

export interface PlanWizardResponseLocal {
  weather_impact: number;
  risk_label: RiskLabel;
  route_type: RouteType;
  vehicles: VehicleSuggestion[];
  drivers: DriverSuggestion[];
  generated_at: string;
  cache_hit: boolean;
}

export { type PlanWizardRequest, type PlanWizardResponse };

export const tripPlannerService = {
  plan: async (
    payload: PlanWizardRequestPayload,
  ): Promise<PlanWizardResponseLocal> => {
    const result = await planWizardApiV1TripsPlanWizardPost(
      payload as PlanWizardRequest,
    );
    return result as unknown as PlanWizardResponseLocal;
  },
};
