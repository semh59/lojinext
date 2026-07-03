/**
 * 0-mock epiği Faz 2: gerçek backend'e karşı gerçek POST /routes/simulate
 * round-trip (RouteSimulator gerçek çalışır, MapboxClient gerçek api_stub'a
 * gider — bkz location-service.test.ts'in başındaki desen açıklaması).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("route-sim-service (real backend)", () => {
  let simulateRoute: typeof import("../../../api/route-sim").simulateRoute;
  let getRouteSimulation: typeof import("../../../api/route-sim").getRouteSimulation;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ simulateRoute, getRouteSimulation } = await import(
      "../../../api/route-sim"
    ));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("simulateRoute persists a real simulation and returns real segments", async () => {
    const res = await simulateRoute({
      cikis_lat: 41.0,
      cikis_lon: 28.9,
      varis_lat: 39.9,
      varis_lon: 32.8,
      ton: 20,
      arac_yasi: 5,
      segment_length_m: 500,
    });

    expect(res.simulation_id).toBeGreaterThan(0);
    expect(res.summary.distance_km).toBe(450.0); // api_stub's canned Mapbox route
    expect(Array.isArray(res.segments)).toBe(true);
    expect(res.segments.length).toBeGreaterThan(0);
    expect(res.segments[0]).toHaveProperty("road_class");

    // Real round-trip: GET /simulate/{id} returns the same persisted row.
    const fetched = await getRouteSimulation(res.simulation_id);
    expect(fetched.simulation_id).toBe(res.simulation_id);
    expect(fetched.summary.distance_km).toBe(res.summary.distance_km);
  }, 20000); // Real Mapbox+Open-Meteo+segment-simulation pipeline is slower than vitest's 5s default.

  it("simulateRoute surfaces a real 422 for missing coords/lokasyon_id", async () => {
    await expect(
      simulateRoute({ ton: 15, arac_yasi: 5, segment_length_m: 500 }),
    ).rejects.toThrow();
  });
});
