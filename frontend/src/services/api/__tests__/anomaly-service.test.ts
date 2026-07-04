/**
 * 0-mock epiği — son parti. anomalyService.getFleetInsights gerçek backend'e
 * karşı.
 */
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("anomalyService (real backend)", () => {
  let anomalyService: typeof import("../../../api/anomalies").anomalyService;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ anomalyService } = await import("../../../api/anomalies"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("getFleetInsights calls the real endpoint and unwraps the shape", async () => {
    const result = await anomalyService.getFleetInsights(30);

    expect(result).toHaveProperty("leakage");
    expect(result).toHaveProperty("maintenance");
    expect(typeof result.leakage.route_deviation_km).toBe("number");
    expect(typeof result.maintenance.urgent_count).toBe("number");
    expect(Array.isArray(result.maintenance.vehicles)).toBe(true);
  }, 15000);
});
