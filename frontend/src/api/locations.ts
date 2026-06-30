import {
  listLokasyonlarApiV1LocationsGet,
  createLokasyonApiV1LocationsPost,
  getLokasyonApiV1LocationsLokasyonIdGet,
  updateLokasyonApiV1LocationsLokasyonIdPut,
  deleteLokasyonApiV1LocationsLokasyonIdDelete,
  getLocationStatsApiV1LocationsStatsGet,
  getStaleLocationsApiV1LocationsStaleGet,
  getRouteInfoApiV1LocationsRouteInfoGet,
  geocodeLocationApiV1LocationsGeocodeGet,
  searchByRouteApiV1LocationsSearchByRouteGet,
  analyzeWithOpenrouteApiV1LocationsLokasyonIdAnalyzePost,
  getUniqueNamesApiV1LocationsUniqueNamesGet,
} from "../generated/api/locations/locations";
import type { GeocodeSuggestion, RouteInfoResponse } from "../generated/types";
import axiosInstance from "../services/api/axios-instance";
import type {
  Location,
  LocationCreate,
  LocationUpdate,
  AnalysisResponse,
} from "../types/location";

export type { RouteInfoResponse, GeocodeSuggestion };

export interface LocationFilters {
  skip?: number;
  limit?: number;
  zorluk?: string;
  search?: string;
}

export interface LocationStats {
  total: number;
  analyzed: number;
  stale: number;
  avg_distance_km: number;
  high_difficulty: number;
}

export interface StaleLocation {
  id: number;
  cikis_yeri: string;
  varis_yeri: string;
  mesafe_km: number;
  zorluk: string;
  last_api_call: string | null;
}

export const locationService = {
  /**
   * Tüm güzergahları filtreler ile getirir
   */
  getAll: async (
    params: LocationFilters = {},
  ): Promise<{ items: Location[]; total: number }> => {
    const result = await listLokasyonlarApiV1LocationsGet(params);
    return result as unknown as { items: Location[]; total: number };
  },

  getStats: async (): Promise<LocationStats> => {
    const result = await getLocationStatsApiV1LocationsStatsGet();
    const wrapped = result as unknown as {
      status: string;
      data: LocationStats;
    };
    return (
      wrapped.data ?? {
        total: 0,
        analyzed: 0,
        stale: 0,
        avg_distance_km: 0,
        high_difficulty: 0,
      }
    );
  },

  getStale: async (days = 90): Promise<StaleLocation[]> => {
    const result = await getStaleLocationsApiV1LocationsStaleGet({ days });
    const wrapped = result as unknown as {
      status: string;
      data: StaleLocation[];
    };
    return Array.isArray(wrapped.data) ? wrapped.data : [];
  },

  /**
   * Tek bir güzergah detayı getirir
   */
  getById: async (id: number): Promise<Location> => {
    const result = await getLokasyonApiV1LocationsLokasyonIdGet(id);
    return result as unknown as Location;
  },

  /**
   * Yeni güzergah oluşturur
   */
  create: async (data: LocationCreate): Promise<Location> => {
    const result = await createLokasyonApiV1LocationsPost(
      data as unknown as import("../generated/types").LokasyonCreate,
    );
    return result as unknown as Location;
  },

  /**
   * Güzergah günceller
   */
  update: async (id: number, data: LocationUpdate): Promise<Location> => {
    const result = await updateLokasyonApiV1LocationsLokasyonIdPut(
      id,
      data as unknown as import("../generated/types").LokasyonUpdate,
    );
    return result as unknown as Location;
  },

  /**
   * Güzergah siler
   */
  delete: async (id: number): Promise<void> => {
    await deleteLokasyonApiV1LocationsLokasyonIdDelete(id);
  },

  /**
   * Güzergah Analizi (OpenRouteService)
   */
  analyze: async (id: number): Promise<AnalysisResponse> => {
    const result =
      await analyzeWithOpenrouteApiV1LocationsLokasyonIdAnalyzePost(id);
    return result as unknown as AnalysisResponse;
  },

  /**
   * Benzersiz lokasyon isimlerini getirir (Autocomplete için)
   */
  getUniqueNames: async (): Promise<string[]> => {
    const result = await getUniqueNamesApiV1LocationsUniqueNamesGet();
    return result as unknown as string[];
  },

  /**
   * Rota ile arama (Sefer formu için)
   */
  searchByRoute: async (
    cikis: string,
    varis: string,
  ): Promise<{ found: boolean; location: Location | null }> => {
    const result = await searchByRouteApiV1LocationsSearchByRouteGet({
      cikis,
      varis,
    });
    return result as unknown as { found: boolean; location: Location | null };
  },

  /**
   * Rota bilgilerini koordinatlara göre çeker
   */
  getRouteInfo: async (params: {
    cikis_lat: number;
    cikis_lon: number;
    varis_lat: number;
    varis_lon: number;
  }): Promise<RouteInfoResponse> => {
    const result = await getRouteInfoApiV1LocationsRouteInfoGet(params);
    return result as unknown as RouteInfoResponse;
  },

  geocode: async (q: string, limit = 5): Promise<GeocodeSuggestion[]> => {
    const result = await geocodeLocationApiV1LocationsGeocodeGet({ q, limit });
    return result as unknown as GeocodeSuggestion[];
  },

  /**
   * Excel şablonu indirir
   */
  downloadTemplate: async (): Promise<Blob> => {
    const response = await axiosInstance.get("/locations/excel/template", {
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Excel ile toplu güzergah yükler
   */
  uploadExcel: async (
    file: File,
  ): Promise<{ count: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await axiosInstance.post<{
      count: number;
      errors: string[];
    }>("/locations/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  /**
   * Excel olarak dışa aktar
   */
  exportExcel: async (): Promise<Blob> => {
    const response = await axiosInstance.get("/locations/excel/export", {
      responseType: "blob",
    });
    return response.data;
  },

  /**
   * Verilen seferin GPS verisinden güzergahın "Golden Path"ini kalibre et.
   * Admin yetkisi (kalibrasyon_duzenle) gerekir.
   */
  calibrateFromTrip: async (
    seferId: number,
  ): Promise<{ success: boolean; message: string }> => {
    const response = await axiosInstance.post<{
      success: boolean;
      message: string;
    }>(`/admin/calibration/calibrate/${seferId}`);
    return response.data;
  },
};
