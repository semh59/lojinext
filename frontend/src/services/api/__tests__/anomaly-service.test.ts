import { describe, it, expect, vi, beforeEach } from "vitest";

const mockCustomAxios = vi.fn();
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));

describe("anomalyService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getFleetInsights calls correct endpoint and unwraps response", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      status: "success",
      data: {
        leakage: {
          route_deviation_km: 0,
          route_deviation_cost: 0,
          fuel_gap_liters: 0,
          fuel_gap_cost: 0,
        },
        maintenance: { urgent_count: 0, warning_count: 0, vehicles: [] },
      },
    });
    const { anomalyService } = await import("../../../api/anomalies");
    const result = await anomalyService.getFleetInsights(30);
    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/anomalies/fleet/insights",
      method: "GET",
    });
    expect(result.leakage.route_deviation_km).toBe(0);
    expect(result.maintenance.urgent_count).toBe(0);
  });
});
