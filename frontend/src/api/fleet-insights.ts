import { getFleetComparisonApiV1ReportsInsightsFleetComparisonGet } from "../generated/api/reports-v2/reports-v2";

export type PeriodType = "week" | "month";

export interface PeriodMetrics {
  fuel_l: number;
  fuel_cost_tl: number;
  anomaly_count: number;
  trip_count: number;
}

export interface FleetComparisonResponse {
  period: PeriodType;
  current: PeriodMetrics;
  previous: PeriodMetrics;
  fuel_l_delta_pct: number | null;
  fuel_cost_delta_pct: number | null;
  anomaly_delta_pct: number | null;
  trip_delta_pct: number | null;
  current_start: string;
  current_end: string;
  previous_start: string;
  previous_end: string;
}

export const fleetInsightsService = {
  getComparison: async (
    period: PeriodType = "month",
  ): Promise<FleetComparisonResponse> => {
    const result =
      await getFleetComparisonApiV1ReportsInsightsFleetComparisonGet({
        period,
      });
    return result as unknown as FleetComparisonResponse;
  },
};
