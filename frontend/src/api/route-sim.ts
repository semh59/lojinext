import {
  simulateRouteApiV1RoutesSimulatePost,
  getRouteSimulationApiV1RoutesSimulateSimulationIdGet,
} from "../generated/api/routes/routes";

/**
 * Faz 10 — Güzergah simülasyonu (Rota Lab). Backend POST /routes/simulate:
 * koordinat veya lokasyon_id + yük + araç → 500m segment çözünürlüğünde
 * fizik (tractive) + traffic tahmini.
 */

export interface RouteSimRequest {
  lokasyon_id?: number | null;
  cikis_lat?: number | null;
  cikis_lon?: number | null;
  varis_lat?: number | null;
  varis_lon?: number | null;
  ton: number;
  arac_yasi: number;
  segment_length_m: number;
}

export interface SegmentSim {
  seq: number;
  length_km: number;
  grade_pct: number;
  road_class: string;
  sim_speed_kmh: number;
  sim_l_per_100km: number;
  sim_l_total: number;
  eta_sec: number;
  mid_lon: number | null;
  mid_lat: number | null;
  maxspeed_kmh: number | null;
  traffic_speed_kmh: number | null;
  congestion: string;
  speed_source: string;
}

export interface RouteSimSummary {
  distance_km: number;
  duration_min: number;
  total_l: number;
  avg_l_per_100km: number;
  total_ascent_m: number;
  total_descent_m: number;
}

export interface RouteSimResponse {
  simulation_id: number;
  created_at: string;
  summary: RouteSimSummary;
  segments: SegmentSim[];
  raw_segment_count: number;
  resampled_segment_count: number;
  elevation_coverage_pct: number;
  meta: Record<string, unknown>;
}

export async function simulateRoute(
  req: RouteSimRequest,
): Promise<RouteSimResponse> {
  const data = await simulateRouteApiV1RoutesSimulatePost(
    req as unknown as Parameters<
      typeof simulateRouteApiV1RoutesSimulatePost
    >[0],
  );
  return data as unknown as RouteSimResponse;
}

export async function getRouteSimulation(
  simulationId: number,
): Promise<RouteSimResponse> {
  const data =
    await getRouteSimulationApiV1RoutesSimulateSimulationIdGet(simulationId);
  return data as unknown as RouteSimResponse;
}
