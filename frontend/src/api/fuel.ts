import {
  getFuelStatsApiV1FuelStatsGet,
  readYakitAlimlariApiV1FuelGet,
  createYakitApiV1FuelPost,
  updateYakitApiV1FuelYakitIdPut,
  deleteYakitApiV1FuelYakitIdDelete,
  uploadYakitExcelApiV1FuelExcelUploadPost,
  ocrPreviewApiV1FuelOcrPreviewPost,
} from "../generated/api/fuel/fuel";
import axiosInstance from "../services/api/axios-instance";
import type { FuelRecord, FuelStats } from "../types";

export interface FuelFilters {
  skip?: number;
  limit?: number;
  arac_id?: number;
  baslangic_tarih?: string;
  bitis_tarih?: string;
  durum?: string;
}

export interface OcrPreview {
  ham_metin: string | null;
  yapilandirilmis: {
    litre: number | null;
    tutar: number | null;
    km: number | null;
    tarih: string | null;
    istasyon: string | null;
  };
}

export const fuelService = {
  ocrPreview: async (file: File): Promise<OcrPreview> => {
    const form = new FormData();
    form.append("file", file);
    return ocrPreviewApiV1FuelOcrPreviewPost({
      file,
    } as unknown as import("../generated/types").BodyOcrPreviewApiV1FuelOcrPreviewPost) as unknown as Promise<OcrPreview>;
  },

  getAll: (
    params: FuelFilters = {},
  ): Promise<{ items: FuelRecord[]; total: number }> =>
    readYakitAlimlariApiV1FuelGet(params) as unknown as Promise<{
      items: FuelRecord[];
      total: number;
    }>,

  create: (data: Partial<FuelRecord>): Promise<FuelRecord> =>
    createYakitApiV1FuelPost(
      data as unknown as import("../generated/types").YakitCreate,
    ) as unknown as Promise<FuelRecord>,

  update: (id: number, data: Partial<FuelRecord>): Promise<FuelRecord> =>
    updateYakitApiV1FuelYakitIdPut(
      id,
      data as unknown as import("../generated/types").YakitUpdate,
    ) as unknown as Promise<FuelRecord>,

  delete: (id: number): Promise<void> =>
    deleteYakitApiV1FuelYakitIdDelete(id) as unknown as Promise<void>,

  exportExcel: (
    params: Omit<FuelFilters, "skip" | "limit"> = {},
  ): Promise<Blob> =>
    axiosInstance
      .get("/fuel/excel/export", { params, responseType: "blob" })
      .then((r) => r.data as Blob),

  downloadTemplate: (): Promise<Blob> =>
    axiosInstance
      .get("/fuel/excel/template", { responseType: "blob" })
      .then((r) => r.data as Blob),

  getStats: (
    params: Omit<FuelFilters, "skip" | "limit"> = {},
  ): Promise<FuelStats> =>
    getFuelStatsApiV1FuelStatsGet(params) as unknown as Promise<FuelStats>,

  uploadExcel: async (
    file: File,
  ): Promise<{
    status: "success" | "partial_success";
    processed: number;
    saved: number;
    failed: number;
    errors: unknown[];
  }> => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadYakitExcelApiV1FuelExcelUploadPost({
      file,
    } as unknown as import("../generated/types").BodyUploadYakitExcelApiV1FuelExcelUploadPost) as unknown as Promise<{
      status: "success" | "partial_success";
      processed: number;
      saved: number;
      failed: number;
      errors: unknown[];
    }>;
  },
};
