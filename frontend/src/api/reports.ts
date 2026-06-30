import {
  getDashboardStatsApiV1ReportsDashboardGet,
  getConsumptionTrendApiV1ReportsConsumptionTrendGet,
} from "../generated/api/reports/reports";
import {
  getCostTrendApiV1AdvancedReportsCostTrendGet,
  getVehicleCostComparisonApiV1AdvancedReportsCostVehicleComparisonGet,
  getRoiAnalysisApiV1AdvancedReportsCostRoiGet,
  getSavingsPotentialApiV1AdvancedReportsCostSavingsPotentialGet,
  getPeriodCostApiV1AdvancedReportsCostPeriodGet,
} from "../generated/api/advanced-reports/advanced-reports";
import axiosInstance from "../services/api/axios-instance";
import { DashboardStats, RoiStats } from "../types";

export interface ConsumptionTrendPoint {
  month: string;
  consumption: number;
}

export interface MonthlyCostTrend {
  month: number;
  year: number;
  label: string;
  fuel_cost: number;
  fuel_liters: number;
  trip_count: number;
  total_distance: number;
  cost_per_km: number;
  // Aliases expected by CostAnalysisChart
  fuel: number;
  maintenance: number;
}

export interface PeriodCostBreakdown {
  fuel_cost: number;
  fuel_liters: number;
  avg_price_per_liter: number;
  trip_count: number;
  total_distance: number;
  cost_per_km: number;
  period_start: string;
  period_end: string;
}

export interface VehicleCostComparison {
  arac_id: number;
  plaka: string;
  fuel_cost: number;
  avg_consumption: number;
  average_consumption: number;
  trip_count: number;
  total_distance: number;
  unavailable?: boolean;
  error_code?: string;
}

export type FleetComparisonPeriod = "week" | "month";

export interface PeriodMetrics {
  fuel_l: number;
  fuel_cost_tl: number;
  anomaly_count: number;
  trip_count: number;
}

export interface FleetComparison {
  period: FleetComparisonPeriod;
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

export const reportService = {
  getDashboardStats: async (): Promise<DashboardStats> => {
    const data = await getDashboardStatsApiV1ReportsDashboardGet();
    return data as unknown as DashboardStats;
  },

  getConsumptionTrend: async (): Promise<ConsumptionTrendPoint[]> => {
    const data = await getConsumptionTrendApiV1ReportsConsumptionTrendGet();
    return data as unknown as ConsumptionTrendPoint[];
  },

  getCostAnalysis: async (months: number = 12): Promise<MonthlyCostTrend[]> => {
    const data = await getCostTrendApiV1AdvancedReportsCostTrendGet({ months });
    const raw = Array.isArray(data) ? data : [];
    return raw.map((item: Record<string, unknown>) => ({
      ...(item as object),
      fuel: (item.fuel_cost as number) ?? 0,
      maintenance: 0,
    })) as MonthlyCostTrend[];
  },

  getVehicleComparison: async (
    months: number = 3,
  ): Promise<VehicleCostComparison[]> => {
    const data =
      await getVehicleCostComparisonApiV1AdvancedReportsCostVehicleComparisonGet(
        { months },
      );
    const raw = Array.isArray(data) ? data : [];
    return (raw as Array<Record<string, unknown>>)
      .filter((v) => !v.unavailable)
      .map((v) => ({
        ...(v as object),
        average_consumption: (v.avg_consumption as number) ?? 0,
      })) as VehicleCostComparison[];
  },

  getRoiStats: async (
    investment: number,
    targetConsumption: number = 30,
  ): Promise<RoiStats> => {
    const data = await getRoiAnalysisApiV1AdvancedReportsCostRoiGet({
      investment,
      target_consumption: targetConsumption,
    });
    return data as unknown as RoiStats;
  },

  getSavingsPotential: async (
    targetConsumption: number = 30,
  ): Promise<unknown> => {
    const data =
      await getSavingsPotentialApiV1AdvancedReportsCostSavingsPotentialGet({
        target_consumption: targetConsumption,
      });
    return data;
  },

  /**
   * Dönemsel maliyet kırılımı. arac_id opsiyonel (drill-down için).
   */
  getPeriodCost: async (
    startDate: string,
    endDate: string,
    aracId?: number,
  ): Promise<PeriodCostBreakdown> => {
    const params: Record<string, string | number> = {
      start_date: startDate,
      end_date: endDate,
    };
    if (aracId !== undefined && aracId !== null) params.arac_id = aracId;
    const data = await getPeriodCostApiV1AdvancedReportsCostPeriodGet(
      params as Parameters<
        typeof getPeriodCostApiV1AdvancedReportsCostPeriodGet
      >[0],
    );
    return data as unknown as PeriodCostBreakdown;
  },

  getFleetComparison: async (
    period: FleetComparisonPeriod = "month",
  ): Promise<FleetComparison> => {
    const response = await axiosInstance.get(
      "/reports/insights/fleet/comparison",
      { params: { period } },
    );
    return response.data as FleetComparison;
  },

  downloadPdf: async (
    type: string,
    id?: number,
    params: Record<string, string | number> = {},
  ): Promise<Blob> => {
    let url = `/advanced-reports/pdf/${type.replace("_", "-")}`;
    if (id) {
      url = `/advanced-reports/pdf/${type.split("_")[0]}/${id}`;
    }
    const response = await axiosInstance.get(url, {
      params,
      responseType: "blob",
    });
    return response.data;
  },

  downloadExcel: async (
    type: string,
    params: Record<string, string | number> = {},
  ): Promise<Blob> => {
    const response = await axiosInstance.get("/advanced-reports/excel/export", {
      params: { report_type: type, ...params },
      responseType: "blob",
    });
    return response.data;
  },
};
