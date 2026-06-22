import {
  getWeatherForecastApiV1WeatherForecastPost,
  getTripWeatherImpactApiV1WeatherTripImpactPost,
  getDashboardWeatherSummaryApiV1WeatherDashboardSummaryGet,
} from "../generated/api/weather/weather";
import type {
  WeatherRequest,
  TripWeatherRequest,
  WeatherResponse,
  WeatherDashboardResponse,
} from "../generated/types";

export type {
  WeatherRequest,
  TripWeatherRequest,
  WeatherResponse,
  WeatherDashboardResponse,
};

export interface TripImpactResponse {
  fuel_impact_factor?: number | null;
  risk_level?: string | null;
  [key: string]: unknown;
}

export const weatherApi = {
  getForecast: async (lat: number, lon: number): Promise<WeatherResponse> => {
    const body: WeatherRequest = { lat, lon };
    return getWeatherForecastApiV1WeatherForecastPost(
      body,
    ) as unknown as Promise<WeatherResponse>;
  },

  getTripImpact: async (params: {
    cikis_lat: number;
    cikis_lon: number;
    varis_lat: number;
    varis_lon: number;
    trip_date?: string;
  }): Promise<TripImpactResponse> => {
    const body: TripWeatherRequest = {
      cikis_lat: params.cikis_lat,
      cikis_lon: params.cikis_lon,
      varis_lat: params.varis_lat,
      varis_lon: params.varis_lon,
      trip_date: params.trip_date,
    };
    return getTripWeatherImpactApiV1WeatherTripImpactPost(
      body,
    ) as unknown as Promise<TripImpactResponse>;
  },

  getDashboardSummary: async (): Promise<WeatherDashboardResponse> => {
    return getDashboardWeatherSummaryApiV1WeatherDashboardSummaryGet() as unknown as Promise<WeatherDashboardResponse>;
  },
};
