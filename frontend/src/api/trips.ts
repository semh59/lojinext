import {
  readSeferlerApiV1TripsGet,
  readBugununSeferleriApiV1TripsTodayGet,
  getTripStatsApiV1TripsStatsGet,
  getFuelPerformanceAnalyticsApiV1TripsAnalyticsFuelPerformanceGet,
  createReturnTripApiV1TripsSeferIdReturnPost,
  beklemedeSeferlerApiV1TripsBeklemedeGet,
  readSeferApiV1TripsSeferIdGet,
  updateSeferApiV1TripsSeferIdPatch,
  deleteSeferApiV1TripsSeferIdDelete,
  analyzeTripCostsApiV1TripsSeferIdCostAnalysisGet,
  uploadSeferExcelApiV1TripsUploadPost,
  bulkUpdateTripStatusApiV1TripsBulkStatusPatch,
  bulkCancelTripsApiV1TripsBulkCancelPatch,
  bulkDeleteTripsApiV1TripsBulkDeletePost,
  getTaskStatusApiV1TripsTasksTaskIdStatusGet,
  getSeferTimelineApiV1TripsSeferIdTimelineGet,
  seferOnaylaApiV1TripsSeferIdOnaylaPost,
  seferReddetApiV1TripsSeferIdReddetPost,
} from "../generated/api/trips/trips";
import axiosInstance from "../services/api/axios-instance";
import type {
  Trip,
  SeferTimelineItem,
  FuelPerformanceAnalyticsResponse,
  TripStatsResponse,
} from "../types";
import type { TripAssignableStatus, TripStatus } from "../lib/trip-status";

export interface TripFilters {
  skip?: number;
  limit?: number;
  baslangic_tarih?: string;
  bitis_tarih?: string;
  arac_id?: number;
  sofor_id?: number;
  durum?: TripStatus | "";
  onay_durumu?: "beklemede" | "onaylandi" | "reddedildi" | "";
  search?: string;
}

export interface TripListResponse {
  items: Trip[];
  meta: { total: number; skip: number; limit: number };
}

export interface TripUploadResponse {
  success: boolean;
  total_rows: number;
  success_count: number;
  failed_count: number;
  errors: unknown[];
}

export interface TripBulkActionError {
  id: number;
  reason: string;
}
export interface TripBulkActionResponse {
  success_count: number;
  failed_count: number;
  failed: TripBulkActionError[];
}
export interface FuelPerformanceFilters extends TripFilters {}

const clean = (p: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(p).filter(([, v]) => v != null && v !== ""),
  );

export const tripService = {
  getAll: (params: TripFilters = {}): Promise<TripListResponse> =>
    readSeferlerApiV1TripsGet(
      clean(params as Record<string, unknown>) as TripFilters,
    ) as unknown as Promise<TripListResponse>,

  getStats: (
    params: {
      durum?: string;
      baslangic_tarih?: string;
      bitis_tarih?: string;
    } = {},
  ): Promise<TripStatsResponse> =>
    getTripStatsApiV1TripsStatsGet(
      clean(params as Record<string, unknown>),
    ) as unknown as Promise<TripStatsResponse>,

  getById: (id: number): Promise<Trip> =>
    readSeferApiV1TripsSeferIdGet(id) as unknown as Promise<Trip>,

  create: (
    data: Omit<Trip, "id" | "created_at" | "ton">,
    idempotencyKey?: string,
  ): Promise<Trip> => {
    const key = idempotencyKey ?? crypto.randomUUID();
    return axiosInstance
      .post<Trip>("/trips/", data, { headers: { "X-Idempotency-Key": key } })
      .then((r) => r.data);
  },

  createReturn: (id: number): Promise<Trip> =>
    createReturnTripApiV1TripsSeferIdReturnPost(id) as unknown as Promise<Trip>,

  update: (id: number, data: Partial<Trip>): Promise<Trip> =>
    updateSeferApiV1TripsSeferIdPatch(
      id,
      data as Record<string, unknown>,
    ) as unknown as Promise<Trip>,

  delete: (id: number): Promise<void> =>
    deleteSeferApiV1TripsSeferIdDelete(id) as unknown as Promise<void>,

  getTimeline: (id: number): Promise<SeferTimelineItem[]> =>
    getSeferTimelineApiV1TripsSeferIdTimelineGet(id) as unknown as Promise<
      SeferTimelineItem[]
    >,

  getFuelPerformance: (
    params: FuelPerformanceFilters = {},
  ): Promise<FuelPerformanceAnalyticsResponse> =>
    getFuelPerformanceAnalyticsApiV1TripsAnalyticsFuelPerformanceGet(
      clean(params as Record<string, unknown>) as FuelPerformanceFilters,
    ) as unknown as Promise<FuelPerformanceAnalyticsResponse>,

  exportExcel: (
    params: Omit<TripFilters, "skip" | "limit"> = {},
  ): Promise<Blob> =>
    axiosInstance
      .get("/trips/export", { params, responseType: "blob" })
      .then((r) => r.data as Blob),

  uploadExcel: async (file: File): Promise<TripUploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadSeferExcelApiV1TripsUploadPost({
      file,
    } as unknown as import("../generated/types").BodyUploadSeferExcelApiV1TripsUploadPost) as unknown as Promise<TripUploadResponse>;
  },

  uploadExcelAsync: async (
    file: File,
  ): Promise<{ status: string; task_id: string; message?: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await axiosInstance.post<{
      status: string;
      task_id: string;
      message?: string;
    }>("/trips/upload", formData, {
      params: { async_mode: true },
      timeout: 120000,
      headers: {
        "Content-Type": "multipart/form-data",
        "X-Idempotency-Key": crypto.randomUUID(),
      },
    });
    return response.data;
  },

  downloadTemplate: (): Promise<Blob> =>
    axiosInstance
      .get("/trips/excel/template", { responseType: "blob" })
      .then((r) => r.data as Blob),

  bulkDelete: (ids: number[]): Promise<TripBulkActionResponse> =>
    bulkDeleteTripsApiV1TripsBulkDeletePost({
      sefer_ids: ids,
    }) as unknown as Promise<TripBulkActionResponse>,

  bulkUpdateStatus: (
    ids: number[],
    newStatus: TripAssignableStatus,
  ): Promise<TripBulkActionResponse> =>
    bulkUpdateTripStatusApiV1TripsBulkStatusPatch({
      sefer_ids: ids,
      new_status:
        newStatus as unknown as import("../generated/types").TripStatus,
    }) as unknown as Promise<TripBulkActionResponse>,

  bulkCancel: (
    ids: number[],
    reason: string,
  ): Promise<TripBulkActionResponse> =>
    bulkCancelTripsApiV1TripsBulkCancelPatch({
      sefer_ids: ids,
      iptal_nedeni: reason,
    }) as unknown as Promise<TripBulkActionResponse>,

  getBeklemede: (skip = 0, limit = 50): Promise<Trip[]> =>
    beklemedeSeferlerApiV1TripsBeklemedeGet({
      skip,
      limit,
    }) as unknown as Promise<Trip[]>,

  onayla: (id: number, onay_notu?: string): Promise<Trip> =>
    seferOnaylaApiV1TripsSeferIdOnaylaPost(id, {
      onay_notu,
    }) as unknown as Promise<Trip>,

  reddet: (id: number, onay_notu?: string): Promise<Trip> =>
    seferReddetApiV1TripsSeferIdReddetPost(id, {
      onay_notu,
    }) as unknown as Promise<Trip>,

  startCostAnalysis: (
    seferId: number,
  ): Promise<{ status: string; task_id: string; message?: string }> =>
    analyzeTripCostsApiV1TripsSeferIdCostAnalysisGet(
      seferId,
    ) as unknown as Promise<{
      status: string;
      task_id: string;
      message?: string;
    }>,

  getTaskStatus: (
    taskId: string,
  ): Promise<{
    task_id: string;
    status: "PROCESSING" | "SUCCESS" | "FAILED";
    result?: unknown;
    error?: string;
    timestamp?: string;
  }> =>
    getTaskStatusApiV1TripsTasksTaskIdStatusGet(taskId) as unknown as Promise<{
      task_id: string;
      status: "PROCESSING" | "SUCCESS" | "FAILED";
      result?: unknown;
      error?: string;
      timestamp?: string;
    }>,

  getTodayTrips: async (): Promise<{ items: Trip[]; total: number }> => {
    try {
      const data =
        (await readBugununSeferleriApiV1TripsTodayGet()) as unknown as TripListResponse;
      return {
        items: data.items,
        total: data.meta?.total ?? data.items.length,
      };
    } catch {
      const today = new Date().toISOString().split("T")[0];
      const data = await tripService.getAll({
        baslangic_tarih: today,
        bitis_tarih: today,
      });
      return { items: data.items, total: data.meta.total };
    }
  },
};
