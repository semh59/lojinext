import { describe, expect, it, vi, beforeEach } from "vitest";

const mockCustomAxios = vi.fn();
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));
vi.mock("../axios-instance", () => ({
  default: { get: vi.fn() },
}));

describe("analytics-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("recordPageView calls analytics page-view endpoint", async () => {
    mockCustomAxios.mockResolvedValueOnce(undefined);
    const { recordPageView } = await import("../../../api/analytics");
    await recordPageView("/trips");
    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/analytics/page-view",
      method: "POST",
    });
  });

  it("recordPageView swallows errors (best-effort)", async () => {
    mockCustomAxios.mockRejectedValueOnce(new Error("network"));
    const { recordPageView } = await import("../../../api/analytics");
    await expect(recordPageView("/fuel")).resolves.toBeUndefined();
  });

  it("fetchPageViewStats GETs the admin endpoint with days param", async () => {
    const axiosInstance = (await import("../axios-instance")).default;
    (axiosInstance.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: {
        period_days: 30,
        total_views: 0,
        top_routes: [],
        bottom_routes: [],
      },
    });
    const { fetchPageViewStats } = await import("../../../api/analytics");
    const stats = await fetchPageViewStats(30);
    expect(axiosInstance.get).toHaveBeenCalledWith(
      "/admin/analytics/page-views",
      { params: { days: 30 } },
    );
    expect(stats.period_days).toBe(30);
  });
});
