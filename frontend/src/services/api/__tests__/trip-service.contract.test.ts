import { beforeEach, describe, expect, it, vi } from "vitest";

const mockCustomAxios = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));
vi.mock("../axios-instance", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { tripService } from "../../../api/trips";

describe("tripService contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("bulkDelete sends only body contract { sefer_ids }", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      success_count: 2,
      failed_count: 0,
      failed: [],
    });

    await tripService.bulkDelete([11, 12]);

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/trips/bulk-delete",
      method: "POST",
      data: { sefer_ids: [11, 12] },
    });
  });

  it("uploadExcel returns canonical upload response fields", async () => {
    const payload = {
      success: true,
      total_rows: 2,
      success_count: 2,
      failed_count: 0,
      errors: [],
    };
    mockCustomAxios.mockResolvedValueOnce(payload);

    const result = await tripService.uploadExcel(new File(["a"], "trips.xlsx"));

    expect(result).toEqual(payload);
  });

  it("getFuelPerformance passes cleaned filters and returns API payload", async () => {
    const payload = {
      kpis: { mae: 1, rmse: 2, total_compared: 3, high_deviation_ratio: 4 },
      trend: [],
      distribution: {
        good: 0,
        warning: 0,
        error: 0,
        good_pct: 0,
        warning_pct: 0,
        error_pct: 0,
      },
      outliers: [],
      low_data: true,
    };
    mockCustomAxios.mockResolvedValueOnce(payload);

    const result = await tripService.getFuelPerformance({
      durum: "",
      baslangic_tarih: "2026-01-01",
      bitis_tarih: "2026-01-31",
    });

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/trips/analytics/fuel-performance",
      method: "GET",
    });
    expect(result).toEqual(payload);
  });

  it("getTimeline returns timeline array from API", async () => {
    const items = [{ id: 1, tip: "UPDATE" }];
    mockCustomAxios.mockResolvedValueOnce(items);

    const result = await tripService.getTimeline(7);
    expect(result).toEqual(items);
  });
});
