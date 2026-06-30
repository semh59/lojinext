import {
  readAraclarApiV1VehiclesGet,
  createAracApiV1VehiclesPost,
  readAracApiV1VehiclesAracIdGet,
  updateAracApiV1VehiclesAracIdPut,
  deleteAracApiV1VehiclesAracIdDelete,
  getVehicleStatsApiV1VehiclesAracIdStatsGet,
  getVehicleEventsApiV1VehiclesAracIdEventsGet,
  uploadVehiclesApiV1VehiclesUploadPost,
  getFleetStatsApiV1VehiclesFleetStatsGet,
  getInspectionAlertsApiV1VehiclesInspectionAlertsGet,
} from "../generated/api/vehicles/vehicles";
import axiosInstance from "../services/api/axios-instance";
import type {
  Vehicle,
  VehicleStats,
  VehicleFleetStats,
  VehicleEvent,
  PaginatedResponse,
} from "../types";

export interface VehicleFilters {
  skip?: number;
  limit?: number;
  aktif_only?: boolean;
  search?: string;
  marka?: string;
  model?: string;
  min_yil?: number;
  max_yil?: number;
}

export interface InspectionAlertItem {
  id: number;
  plaka: string;
  marka: string | null;
  model: string | null;
  yil: number | null;
  muayene_tarihi: string | null;
  days_remaining: number | null;
}

export interface InspectionAlertsResponse {
  expiring: InspectionAlertItem[];
  overdue: InspectionAlertItem[];
  within_days: number;
}

export const vehicleService = {
  getAll: async (
    params: VehicleFilters = {},
  ): Promise<PaginatedResponse<Vehicle>> => {
    const resp = (await readAraclarApiV1VehiclesGet(params)) as unknown as {
      data?: Vehicle[] | null;
      meta?: { total?: number | null } | null;
    };
    return {
      items: resp.data ?? [],
      total: resp.meta?.total ?? resp.data?.length ?? 0,
    };
  },

  getById: (id: number): Promise<Vehicle> =>
    readAracApiV1VehiclesAracIdGet(id) as unknown as Promise<Vehicle>,

  create: (data: Vehicle): Promise<Vehicle> =>
    createAracApiV1VehiclesPost(
      data as unknown as import("../generated/types").AracCreate,
    ) as unknown as Promise<Vehicle>,

  update: (id: number, data: Partial<Vehicle>): Promise<Vehicle> =>
    updateAracApiV1VehiclesAracIdPut(
      id,
      data as unknown as import("../generated/types").AracUpdate,
    ) as unknown as Promise<Vehicle>,

  delete: (id: number): Promise<void> =>
    deleteAracApiV1VehiclesAracIdDelete(id) as unknown as Promise<void>,

  getStats: (id: number): Promise<VehicleStats> =>
    getVehicleStatsApiV1VehiclesAracIdStatsGet(
      id,
    ) as unknown as Promise<VehicleStats>,

  uploadExcel: async (
    file: File,
  ): Promise<{ success: boolean; message: string; errors: string[] }> => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadVehiclesApiV1VehiclesUploadPost({
      file,
    } as unknown as import("../generated/types").BodyUploadVehiclesApiV1VehiclesUploadPost) as unknown as Promise<{
      success: boolean;
      message: string;
      errors: string[];
    }>;
  },

  exportExcel: (
    params: Omit<VehicleFilters, "skip" | "limit"> = {},
  ): Promise<Blob> =>
    axiosInstance
      .get("/vehicles/export", { params, responseType: "blob" })
      .then((r) => r.data as Blob),

  downloadTemplate: (): Promise<Blob> =>
    axiosInstance
      .get("/vehicles/template", { responseType: "blob" })
      .then((r) => r.data as Blob),

  getFleetStats: (): Promise<VehicleFleetStats> =>
    getFleetStatsApiV1VehiclesFleetStatsGet() as unknown as Promise<VehicleFleetStats>,

  getInspectionAlerts: (withinDays = 30): Promise<InspectionAlertsResponse> =>
    getInspectionAlertsApiV1VehiclesInspectionAlertsGet({
      within_days: withinDays,
    }) as unknown as Promise<InspectionAlertsResponse>,

  getEvents: (id: number, limit = 20): Promise<VehicleEvent[]> =>
    getVehicleEventsApiV1VehiclesAracIdEventsGet(id, {
      limit,
    }) as unknown as Promise<VehicleEvent[]>,
};
