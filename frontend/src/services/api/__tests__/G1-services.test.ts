/**
 * 0-mock epiği — son parti (G1). coachingService + fleetInsightsService
 * gerçek backend'e karşı. Diğer G-serisi dosyalar (G2-G6-G10) tamamen
 * `expect(true).toBe(true)` placeholder'ları olduğu için (hiçbir servis
 * çağrısı yok) dönüştürme kapsamı dışında bırakıldı — bkz. final rapor.
 */
import axios from "axios";
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("Coaching Service (real backend)", () => {
  let coachingService: typeof import("../../../api/coaching").coachingService;
  let driverId: number;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ coachingService } = await import("../../../api/coaching"));

    const runTag = Date.now();
    const created = await axios.post(
      `${REAL_BACKEND_URL}/drivers/`,
      { ad_soyad: `Faz2CoachDriver${runTag}`, ehliyet_sinifi: "E" },
      { headers: { Authorization: `Bearer ${token}` } },
    );
    driverId = created.data.id;
  });

  afterAll(async () => {
    if (driverId) {
      const token = await loginAsAdmin();
      const headers = { Authorization: `Bearer ${token}` };
      await axios
        .delete(`${REAL_BACKEND_URL}/drivers/${driverId}`, { headers })
        .catch(() => undefined);
      await axios
        .delete(`${REAL_BACKEND_URL}/drivers/${driverId}`, { headers })
        .catch(() => undefined);
    }
    vi.unstubAllEnvs();
  });

  it("getInsights returns real coaching insights shape for driver", async () => {
    const result = await coachingService.getInsights(driverId);

    expect(result.sofor_id).toBe(driverId);
    expect(Array.isArray(result.insights)).toBe(true);
    expect(["llm", "fallback"]).toContain(result.source);
  }, 15000);

  it("getInsights rejects for a non-existent driver", async () => {
    await expect(coachingService.getInsights(999999999)).rejects.toThrow();
  }, 15000);

  it("getEffectiveness returns real coaching impact metrics", async () => {
    const result = await coachingService.getEffectiveness(30);

    expect(result.window_days).toBe(30);
    expect(typeof result.total_sent).toBe("number");
    expect(typeof result.caveat).toBe("string");
  }, 15000);
});

describe.skipIf(!backendUp)("Fleet Insights Service (real backend)", () => {
  let fleetInsightsService: typeof import("../../../api/fleet-insights").fleetInsightsService;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ fleetInsightsService } = await import("../../../api/fleet-insights"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("getComparison returns real month period comparison data", async () => {
    const result = await fleetInsightsService.getComparison("month");

    expect(result.period).toBe("month");
    expect(result.current).toHaveProperty("fuel_l");
    expect(result.previous).toHaveProperty("fuel_l");
    expect(result).toHaveProperty("current_start");
    expect(result).toHaveProperty("current_end");
  }, 15000);

  it("getComparison defaults to month period", async () => {
    const result = await fleetInsightsService.getComparison();
    expect(result.period).toBe("month");
  }, 15000);

  it("getComparison returns real week comparison", async () => {
    const result = await fleetInsightsService.getComparison("week");
    expect(result.period).toBe("week");
  }, 15000);
});
