import {
  enqueuePredictionApiV1PredictionsPost,
  predictFuelApiV1PredictionsPredictPost,
  getPredictionComparisonApiV1PredictionsComparisonGet,
  forecastConsumptionApiV1PredictionsTimeSeriesForecastPost,
  getTrendAnalysisApiV1PredictionsTimeSeriesTrendGet,
  getTimeSeriesStatusApiV1PredictionsTimeSeriesStatusGet,
  getEnsembleStatusApiV1PredictionsEnsembleStatusGet,
  explainFuelPredictionApiV1PredictionsExplainPost,
  predictionStatusApiV1PredictionsTaskIdGet,
} from "../generated/api/predictions/predictions";
import type { PredictionRequest } from "../generated/types";
import axiosInstance from "../services/api/axios-instance";

export interface PredictionComparisonResponse {
  mae: number;
  rmse: number;
  accuracy_distribution: {
    good: number;
    warning: number;
    error: number;
    good_pct: number;
    warning_pct: number;
    error_pct: number;
  };
  trend: Array<{
    date: string;
    actual: number;
    predicted: number;
  }>;
  total_compared: number;
}

export interface PredictionEnqueueResponse {
  task_id: string;
  status: string;
}

export interface PredictionStatusResponse {
  task_id: string;
  status: string;
  answer?: string;
  error?: string;
  finished_at?: string;
}

export interface EnsembleStatusResponse {
  models: Record<string, boolean>;
  weights: Record<string, number>;
  sklearn_available: boolean;
  lightgbm_available: boolean;
  xgboost_available: boolean;
  total_models: number;
}

export interface PredictionExplainRequest {
  arac_id: number;
  mesafe_km: number;
  ton?: number;
  ascent_m?: number;
  descent_m?: number;
  flat_distance_km?: number;
  sofor_id?: number;
}

export interface TimeSeriesStatus {
  success?: boolean;
  model_trained?: boolean;
  available?: boolean;
  method?: string;
  history_days?: number;
  [key: string]: unknown;
}

export interface TimeSeriesForecastPoint {
  date: string;
  value: number;
  confidence_low?: number;
  confidence_high?: number;
}

export interface TimeSeriesForecast {
  series: TimeSeriesForecastPoint[];
  trend: "increasing" | "stable" | "decreasing";
  summary?: string;
  method?: string;
}

export interface TimeSeriesTrend {
  success: boolean;
  trend?: "increasing" | "stable" | "decreasing";
  direction?: string;
  slope?: number;
  avg?: number;
  series?: Array<{ date: string; value: number }>;
  [key: string]: unknown;
}

export { PredictionRequest };

export const predictionService = {
  getComparison: async (
    days: number = 30,
    aracId?: number,
  ): Promise<PredictionComparisonResponse> => {
    const params: Record<string, number> = { days };
    if (aracId !== undefined && aracId !== null) {
      params.arac_id = aracId;
    }
    const result =
      await getPredictionComparisonApiV1PredictionsComparisonGet(params);
    return result as unknown as PredictionComparisonResponse;
  },

  predict: async (data: PredictionRequest) => {
    const result = await predictFuelApiV1PredictionsPredictPost(data);
    return result;
  },

  explain: async (data: PredictionRequest) => {
    const result = await explainFuelPredictionApiV1PredictionsExplainPost(data);
    return result;
  },

  enqueue: async (payload: { question: string; context?: string }) => {
    const result = await enqueuePredictionApiV1PredictionsPost(
      payload as unknown as Parameters<
        typeof enqueuePredictionApiV1PredictionsPost
      >[0],
    );
    return result as unknown as PredictionEnqueueResponse;
  },

  status: async (taskId: string) => {
    const result = await predictionStatusApiV1PredictionsTaskIdGet(taskId);
    return result as unknown as PredictionStatusResponse;
  },

  getEnsembleStatus: async (): Promise<EnsembleStatusResponse> => {
    const result = await getEnsembleStatusApiV1PredictionsEnsembleStatusGet();
    return result as unknown as EnsembleStatusResponse;
  },

  stream: (
    taskId: string,
    onMessage: (data: PredictionStatusResponse) => void,
  ) => {
    const source = new EventSource(
      `${axiosInstance.defaults.baseURL}/predictions/${taskId}/stream`,
      {
        withCredentials: true,
      },
    );
    source.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as PredictionStatusResponse;
        onMessage(parsed);
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };
    return () => source.close();
  },

  timeSeriesStatus: async (): Promise<TimeSeriesStatus> => {
    const result =
      await getTimeSeriesStatusApiV1PredictionsTimeSeriesStatusGet();
    return result as unknown as TimeSeriesStatus;
  },

  timeSeriesForecast: async (
    aracId?: number,
    days: number = 7,
  ): Promise<TimeSeriesForecast> => {
    const params: Record<string, number> = { days };
    if (aracId !== undefined && aracId !== null) params.arac_id = aracId;
    const result =
      await forecastConsumptionApiV1PredictionsTimeSeriesForecastPost(params);
    return result as unknown as TimeSeriesForecast;
  },

  timeSeriesTrend: async (
    aracId?: number,
    days: number = 30,
  ): Promise<TimeSeriesTrend> => {
    const params: Record<string, number> = { days };
    if (aracId !== undefined && aracId !== null) params.arac_id = aracId;
    const result =
      await getTrendAnalysisApiV1PredictionsTimeSeriesTrendGet(params);
    return result as unknown as TimeSeriesTrend;
  },
};
