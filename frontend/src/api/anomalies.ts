import { z } from "zod";

import {
  getAnomalyClustersApiV1AnomaliesClustersGet,
  getFleetInsightsApiV1AnomaliesFleetInsightsGet,
  getRecentAnomaliesApiV1AnomaliesGet,
  acknowledgeAnomalyApiV1AnomaliesAnomalyIdAcknowledgePost,
  resolveAnomalyApiV1AnomaliesAnomalyIdResolvePost,
} from "../generated/api/anomalies/anomalies";

/** Anomali ve Filo Analiz API Servisi */

const LeakageStatsSchema = z.object({
  route_deviation_km: z.number(),
  route_deviation_cost: z.number(),
  fuel_gap_liters: z.number(),
  fuel_gap_cost: z.number(),
  total_leakage_cost: z.number().optional().default(0),
});

const MaintenanceReasonCodeSchema = z.object({
  code: z.string(),
  params: z.record(z.string(), z.union([z.string(), z.number()])),
});

const MaintenanceVehicleSchema = z.object({
  id: z.number(),
  plaka: z.string(),
  reason_codes: z.array(MaintenanceReasonCodeSchema),
  severity: z.enum(["medium", "high", "critical"]),
  toplam_km: z.number().optional().default(0),
  ort_tuketim: z.number().optional().default(0),
});

const MaintenanceStatsSchema = z.object({
  urgent_count: z.number(),
  warning_count: z.number(),
  vehicles: z.array(MaintenanceVehicleSchema),
});

const FleetInsightsDataSchema = z.object({
  leakage: LeakageStatsSchema,
  maintenance: MaintenanceStatsSchema,
});

const RecentAnomalySchema = z.object({
  id: z.number(),
  tarih: z.string(),
  tip: z.string(),
  kaynak_tip: z.string(),
  kaynak_id: z.number(),
  deger: z.number(),
  beklenen_deger: z.number(),
  sapma_yuzde: z.number(),
  severity: z.enum(["low", "medium", "high", "critical"]),
  aciklama: z.string(),
  rca_summary: z.string().nullable().optional(),
  suggested_action: z.string().nullable().optional(),
  plaka: z.string().nullable().optional(),
  sofor_adi: z.string().nullable().optional(),
  // T7 — eylem alanları (backward-compatible: tümü opsiyonel)
  acknowledged_at: z.string().nullable().optional(),
  acknowledged_by: z.number().nullable().optional(),
  resolved_at: z.string().nullable().optional(),
  resolved_by: z.number().nullable().optional(),
  resolution_notes: z.string().nullable().optional(),
});

const RecentAnomaliesResponseSchema = z.object({
  anomalies: z.array(RecentAnomalySchema),
  total: z.number(),
  filters: z.object({
    days: z.number(),
    severity: z.string().nullable(),
    tip: z.string().nullable(),
    status: z.string().nullable().optional(),
  }),
});

export type LeakageStats = z.infer<typeof LeakageStatsSchema>;
export type MaintenanceReasonCode = z.infer<typeof MaintenanceReasonCodeSchema>;
export type MaintenanceVehicle = z.infer<typeof MaintenanceVehicleSchema>;
export type MaintenanceStats = z.infer<typeof MaintenanceStatsSchema>;
export type FleetInsightsData = z.infer<typeof FleetInsightsDataSchema>;
export type RecentAnomaly = z.infer<typeof RecentAnomalySchema>;
export type RecentAnomaliesResponse = z.infer<
  typeof RecentAnomaliesResponseSchema
>;

export interface AnomalyCluster {
  cluster_id: number;
  size: number;
  dominant_tip: string;
  dominant_kaynak_tip: string;
  severity_dagilim: Record<string, number>;
  member_ids: number[];
  label: string;
  insight: string | null;
}

export const anomalyService = {
  /** Faz 8 — anomali kümeleri (pattern listesi). */
  getClusters: async (
    days = 30,
  ): Promise<{ clusters: AnomalyCluster[]; period_days: number }> => {
    const result = await getAnomalyClustersApiV1AnomaliesClustersGet({ days });
    return result as unknown as {
      clusters: AnomalyCluster[];
      period_days: number;
    };
  },

  getFleetInsights: async (days: number = 30): Promise<FleetInsightsData> => {
    const result = await getFleetInsightsApiV1AnomaliesFleetInsightsGet({
      days,
    });
    const envelope = result as unknown as {
      status: string;
      data: FleetInsightsData;
    };
    return envelope.data;
  },

  getRecentAnomalies: async (
    params: {
      days?: number;
      severity?: string;
      tip?: string;
      status?: "open" | "acknowledged" | "resolved";
      limit?: number;
    } = {},
  ): Promise<RecentAnomaliesResponse> => {
    const result = await getRecentAnomaliesApiV1AnomaliesGet(params);
    const envelope = result as unknown as {
      status: string;
      data: RecentAnomaliesResponse;
    };
    return envelope.data;
  },

  acknowledge: async (
    anomalyId: number,
  ): Promise<{ id: number; status: string }> => {
    const result =
      await acknowledgeAnomalyApiV1AnomaliesAnomalyIdAcknowledgePost(anomalyId);
    return result as unknown as { id: number; status: string };
  },

  resolve: async (
    anomalyId: number,
    notes?: string,
  ): Promise<{
    id: number;
    status: string;
    resolution_notes?: string | null;
  }> => {
    const result = await resolveAnomalyApiV1AnomaliesAnomalyIdResolvePost(
      anomalyId,
      {
        notes: notes ?? null,
      },
    );
    return result as unknown as {
      id: number;
      status: string;
      resolution_notes?: string | null;
    };
  },
};
