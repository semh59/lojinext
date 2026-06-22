import { describe, it, expect, vi, beforeEach } from "vitest";

const mockCustomAxios = vi.fn();
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));

describe("predictionService.getEnsembleStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls /predictions/ensemble/status", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      models: { physics: true, lightgbm: false },
      weights: { physics: 0.8, lightgbm: 0.05 },
      total_models: 1,
      sklearn_available: true,
      lightgbm_available: false,
      xgboost_available: false,
    });
    const { predictionService } = await import("../../../api/predictions");
    const result = await predictionService.getEnsembleStatus();
    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/predictions/ensemble/status",
      method: "GET",
    });
    expect(result.weights.physics).toBe(0.8);
  });
});
