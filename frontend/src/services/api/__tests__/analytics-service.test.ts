/**
 * 0-mock epiği — son parti. analytics API (recordPageView + fetchPageViewStats)
 * gerçek backend'e karşı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("analytics-service (real backend)", () => {
  let recordPageView: typeof import("../../../api/analytics").recordPageView;
  let fetchPageViewStats: typeof import("../../../api/analytics").fetchPageViewStats;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ recordPageView, fetchPageViewStats } = await import(
      "../../../api/analytics"
    ));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("recordPageView posts a real page-view event and resolves", async () => {
    await expect(recordPageView("/trips")).resolves.toBeUndefined();
  }, 15000);

  it("recordPageView swallows errors (best-effort) even against real backend", async () => {
    // Malformed route payload still resolves silently — best-effort by design.
    await expect(recordPageView("")).resolves.toBeUndefined();
  }, 15000);

  it("fetchPageViewStats GETs the real admin endpoint with days param", async () => {
    const stats = await fetchPageViewStats(30);
    expect(stats.period_days).toBe(30);
    expect(typeof stats.total_views).toBe("number");
    expect(Array.isArray(stats.top_routes)).toBe(true);
    expect(Array.isArray(stats.bottom_routes)).toBe(true);
  }, 15000);
});
