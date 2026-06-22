import {
  getAllPredictionsApiV1AdminMaintenancePredictionsGet,
  getPredictionForAracApiV1AdminMaintenancePredictionsAracIdGet,
} from "../generated/api/admin-maintenance/admin-maintenance";
import type { MaintenancePrediction as GeneratedMaintenancePrediction } from "../generated/types/index";
import axiosInstance from "../services/api/axios-instance";

export type RiskLevel = "overdue" | "soon" | "normal" | "low";

export type MaintenancePrediction = GeneratedMaintenancePrediction;

export const maintenancePredictionsService = {
  getAll: async (): Promise<MaintenancePrediction[]> => {
    return (await getAllPredictionsApiV1AdminMaintenancePredictionsGet()) as unknown as MaintenancePrediction[];
  },

  getForArac: async (aracId: number): Promise<MaintenancePrediction> => {
    return (await getPredictionForAracApiV1AdminMaintenancePredictionsAracIdGet(
      aracId,
    )) as unknown as MaintenancePrediction;
  },

  /** `.ics` URL'ini döndürür — frontend `window.location.assign` ile indirir.
   *  Backend auth header'ı browser otomatik geçirmez (yeni navigation) bu yüzden
   *  axiosInstance üzerinden binary fetch + Blob URL kullanılır. */
  downloadIcs: async (bakimId: number): Promise<void> => {
    const r = await axiosInstance.get(`/admin/maintenance/${bakimId}/ics`, {
      responseType: "blob",
    });
    const blob = new Blob([r.data], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `bakim-${bakimId}.ics`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
