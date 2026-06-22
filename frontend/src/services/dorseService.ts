import { Dorse } from "../types";
import axiosInstance from "./api/axios-instance";

export interface StandardResponse<T> {
  data: T;
  meta?: {
    count?: number;
    offset?: number;
    limit?: number;
    total?: number;
  };
  errors?: any[];
}

export interface DorseFleetStats {
  total: number;
  active: number;
}

export const dorseService = {
  /**
   * Dorse filosu özeti — tek sorgu, total + active.
   */
  getFleetStats: async (): Promise<DorseFleetStats> => {
    const { data } = await axiosInstance.get<DorseFleetStats>(
      "/trailers/fleet-stats",
    );
    return data;
  },

  getAll: async (
    params: {
      skip?: number;
      limit?: number;
      aktif_only?: boolean;
      search?: string;
      marka?: string;
      model?: string;
      min_yil?: number;
      max_yil?: number;
    } = {},
  ) => {
    const searchParams = new URLSearchParams();
    if (params.skip !== undefined)
      searchParams.append("skip", params.skip.toString());
    if (params.limit !== undefined)
      searchParams.append("limit", params.limit.toString());
    if (params.aktif_only !== undefined)
      searchParams.append("aktif_only", params.aktif_only.toString());
    if (params.search) searchParams.append("search", params.search);
    if (params.marka) searchParams.append("marka", params.marka);
    if (params.model) searchParams.append("model", params.model);
    if (params.min_yil)
      searchParams.append("min_yil", params.min_yil.toString());
    if (params.max_yil)
      searchParams.append("max_yil", params.max_yil.toString());

    const { data } = await axiosInstance.get<StandardResponse<Dorse[]>>(
      `/trailers/?${searchParams.toString()}`,
    );
    return data.data;
  },

  create: async (body: Partial<Dorse>) => {
    const { data } = await axiosInstance.post<StandardResponse<Dorse>>(
      "/trailers/",
      body,
    );
    return data.data;
  },

  getById: async (id: number) => {
    const { data } = await axiosInstance.get<StandardResponse<Dorse>>(
      `/trailers/${id}`,
    );
    return data.data;
  },

  update: async (id: number, body: Partial<Dorse>) => {
    const { data } = await axiosInstance.put<StandardResponse<Dorse>>(
      `/trailers/${id}`,
      body,
    );
    return data.data;
  },

  delete: async (id: number) => {
    const { data } = await axiosInstance.delete<StandardResponse<any>>(
      `/trailers/${id}`,
    );
    return data.data;
  },

  exportExcel: async () => {
    const { data } = await axiosInstance.get("/trailers/export", {
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `dorseler_${new Date().toISOString().split("T")[0]}.xlsx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
  },

  downloadTemplate: async () => {
    const { data } = await axiosInstance.get("/trailers/template", {
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "dorse_sablonu.xlsx";
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
  },

  uploadExcel: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await axiosInstance.post<
      StandardResponse<{ imported: number; errors: any[] }>
    >("/trailers/import", formData);
    return data.data;
  },
};
