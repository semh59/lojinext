import { z } from "zod";
import {
  readSoforlerApiV1DriversGet,
  createSoforApiV1DriversPost,
  readSoforApiV1DriversSoforIdGet,
  updateSoforApiV1DriversSoforIdPut,
  deleteSoforApiV1DriversSoforIdDelete,
  bulkDeleteSoforlerApiV1DriversBulkDelete,
  updateDriverScoreApiV1DriversSoforIdScorePost,
  uploadDriversApiV1DriversExcelUploadPost,
  getDriverFleetStatsApiV1DriversFleetStatsGet,
  getDriverPerformanceApiV1DriversSoforIdPerformanceGet,
  getDriverScoreBreakdownApiV1DriversSoforIdScoreBreakdownGet,
  getDriverRouteProfileApiV1DriversSoforIdRouteProfileGet,
} from "../generated/api/drivers/drivers";
import axiosInstance from "../services/api/axios-instance";
import type { Driver } from "../types";

export interface DriverFilters {
  skip?: number;
  limit?: number;
  aktif_only?: boolean;
  search?: string;
  ehliyet_sinifi?: string;
  min_score?: number;
  max_score?: number;
}

export interface DriverFleetStats {
  total: number;
  active: number;
}

export const DriverScoreBreakdownSchema = z.object({
  sofor_id: z.number(),
  ad_soyad: z.string(),
  manual: z.number(),
  manual_weight: z.number(),
  auto: z.number(),
  auto_weight: z.number(),
  total: z.number(),
  trip_count: z.number(),
  avg_consumption: z.number(),
  target_reference: z.number(),
  has_trips: z.boolean(),
});
export type DriverScoreBreakdown = z.infer<typeof DriverScoreBreakdownSchema>;

export const DriverPerformanceSchema = z.record(z.string(), z.any());
export type DriverPerformance = z.infer<typeof DriverPerformanceSchema>;

const RouteTypeEnum = z.enum([
  "highway_dominant",
  "mountain",
  "urban",
  "mixed",
]);
export const DriverRouteProfileItemSchema = z.object({
  route_type: RouteTypeEnum,
  label: z.string(),
  trip_count: z.number(),
  avg_actual: z.number(),
  avg_predicted: z.number(),
  deviation_pct: z.number(),
});
export const DriverRouteProfileSchema = z.object({
  sofor_id: z.number(),
  ad_soyad: z.string(),
  profiles: z.array(DriverRouteProfileItemSchema),
  best_route_type: RouteTypeEnum.nullable(),
  min_trips_for_best: z.number(),
});
export type DriverRouteProfileItem = z.infer<
  typeof DriverRouteProfileItemSchema
>;
export type DriverRouteProfile = z.infer<typeof DriverRouteProfileSchema>;

export const driverService = {
  getFleetStats: (): Promise<DriverFleetStats> =>
    getDriverFleetStatsApiV1DriversFleetStatsGet() as unknown as Promise<DriverFleetStats>,

  getAll: (
    params: DriverFilters = {},
  ): Promise<{ items: Driver[]; total: number }> =>
    readSoforlerApiV1DriversGet(params) as unknown as Promise<{
      items: Driver[];
      total: number;
    }>,

  getById: (id: number): Promise<Driver> =>
    readSoforApiV1DriversSoforIdGet(id) as unknown as Promise<Driver>,

  create: (data: Partial<Driver>): Promise<Driver> =>
    createSoforApiV1DriversPost(
      data as unknown as import("../generated/types").SoforCreate,
    ) as unknown as Promise<Driver>,

  update: (id: number, data: Partial<Driver>): Promise<Driver> =>
    updateSoforApiV1DriversSoforIdPut(
      id,
      data as unknown as import("../generated/types").SoforUpdate,
    ) as unknown as Promise<Driver>,

  delete: (id: number): Promise<void> =>
    deleteSoforApiV1DriversSoforIdDelete(id) as unknown as Promise<void>,

  bulkDelete: (
    ids: number[],
  ): Promise<{ deleted: number; skipped?: number; errors?: unknown[] }> =>
    bulkDeleteSoforlerApiV1DriversBulkDelete(ids) as unknown as Promise<{
      deleted: number;
      skipped?: number;
      errors?: unknown[];
    }>,

  updateScore: (id: number, score: number): Promise<Driver> =>
    updateDriverScoreApiV1DriversSoforIdScorePost(id, {
      score,
    }) as unknown as Promise<Driver>,

  uploadExcel: async (
    file: File,
  ): Promise<{ success: boolean; message: string; errors: string[] }> => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadDriversApiV1DriversExcelUploadPost({
      file,
    } as unknown as import("../generated/types").BodyUploadDriversApiV1DriversExcelUploadPost) as unknown as Promise<{
      success: boolean;
      message: string;
      errors: string[];
    }>;
  },

  exportExcel: (
    params: Omit<DriverFilters, "skip" | "limit"> = {},
  ): Promise<Blob> =>
    axiosInstance
      .get("/drivers/excel/export", { params, responseType: "blob" })
      .then((r) => r.data as Blob),

  downloadTemplate: (): Promise<Blob> =>
    axiosInstance
      .get("/drivers/excel/template", { responseType: "blob" })
      .then((r) => r.data as Blob),

  getPerformance: (id: number): Promise<DriverPerformance> =>
    getDriverPerformanceApiV1DriversSoforIdPerformanceGet(
      id,
    ) as unknown as Promise<DriverPerformance>,

  getScoreBreakdown: (id: number): Promise<DriverScoreBreakdown> =>
    getDriverScoreBreakdownApiV1DriversSoforIdScoreBreakdownGet(
      id,
    ) as unknown as Promise<DriverScoreBreakdown>,

  getRouteProfile: (id: number): Promise<DriverRouteProfile> =>
    getDriverRouteProfileApiV1DriversSoforIdRouteProfileGet(
      id,
    ) as unknown as Promise<DriverRouteProfile>,
};
