import { describe, expect, it, vi, beforeEach } from "vitest";

const mockCustomAxios = vi.fn();
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));

describe("route-sim-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("simulateRoute POSTs request to /routes/simulate and returns data", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      simulation_id: 42,
      created_at: "2026-06-14T00:00:00Z",
      summary: {
        distance_km: 150,
        duration_min: 120,
        total_l: 48,
        avg_l_per_100km: 32,
        total_ascent_m: 300,
        total_descent_m: 280,
      },
      segments: [
        {
          seq: 0,
          length_km: 0.5,
          grade_pct: 1.2,
          road_class: "motorway",
          sim_speed_kmh: 82,
          sim_l_per_100km: 33.5,
          sim_l_total: 0.17,
          eta_sec: 22,
          mid_lon: 29.01,
          mid_lat: 40.98,
          maxspeed_kmh: 90,
          traffic_speed_kmh: 78,
          congestion: "moderate",
          speed_source: "traffic",
        },
      ],
      raw_segment_count: 900,
      resampled_segment_count: 300,
      elevation_coverage_pct: 100,
      meta: { ton: 20, arac_yasi: 5 },
    });
    const { simulateRoute } = await import("../../../api/route-sim");
    const res = await simulateRoute({
      lokasyon_id: 1,
      ton: 20,
      arac_yasi: 5,
      segment_length_m: 500,
    });
    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/routes/simulate",
      method: "POST",
    });
    expect(res.simulation_id).toBe(42);
    expect(res.segments[0].mid_lon).toBe(29.01);
    expect(res.segments[0].speed_source).toBe("traffic");
  });

  it("simulateRoute propagates errors", async () => {
    mockCustomAxios.mockRejectedValueOnce(new Error("502"));
    const { simulateRoute } = await import("../../../api/route-sim");
    await expect(
      simulateRoute({ ton: 15, arac_yasi: 5, segment_length_m: 500 }),
    ).rejects.toThrow("502");
  });
});
