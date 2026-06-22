import { describe, it, expect, beforeEach, vi } from "vitest";

const mockCustomAxios = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));

import { coachingService } from "../../../api/coaching";
import { fleetInsightsService } from "../../../api/fleet-insights";

describe("Coaching Service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getInsights returns coaching insights for driver", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      sofor_id: 1,
      ad_soyad: "Ahmet Yilmaz",
      headline: "Yakıt tasarrufu potansiyeli",
      priority: "high",
      insights: [
        {
          category: "yakit_yonetimi",
          pattern: "Hızlı ivmelenme",
          evidence: ["trip1", "trip2"],
          suggestion: "Düzgün hızlanma yapın",
          impact_score: 0.85,
        },
      ],
      generated_at: "2026-06-01T08:00:00Z",
      source: "llm",
    });

    const result = await coachingService.getInsights(1);

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/coaching/1/insights",
      method: "GET",
    });
    expect(result.sofor_id).toBe(1);
    expect(result.insights.length).toBe(1);
  });

  it("getInsights handles API error", async () => {
    mockCustomAxios.mockRejectedValueOnce(new Error("API error"));
    await expect(coachingService.getInsights(1)).rejects.toThrow("API error");
  });

  it("send delivers coaching message to driver", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      sent: true,
      delivery_id: 123,
      channel: "telegram",
      sent_at: "2026-06-01T08:00:00Z",
    });

    const result = await coachingService.send(
      1,
      "Test mesaj",
      "yakit_yonetimi",
    );

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/coaching/1/send",
      method: "POST",
    });
    expect(result.sent).toBe(true);
    expect(result.delivery_id).toBe(123);
  });

  it("send handles missing category", async () => {
    mockCustomAxios.mockResolvedValueOnce({ sent: true, delivery_id: null });
    const result = await coachingService.send(1, "Message");
    expect(mockCustomAxios).toHaveBeenCalled();
    expect(result.sent).toBe(true);
  });

  it("getEffectiveness returns coaching impact metrics", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      window_days: 30,
      total_sent: 5,
      total_evaluated: 4,
      improved: 3,
      worsened: 1,
      improve_rate: 0.75,
      avg_score_delta_pct: 8.5,
      caveat:
        "Results may include confounding factors such as seasonal weather changes",
    });

    const result = await coachingService.getEffectiveness(30);

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/coaching/effectiveness",
      method: "GET",
    });
    expect(result.improve_rate).toBe(0.75);
  });
});

describe("Fleet Insights Service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getComparison returns period comparison data", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      period: "month",
      current: {
        fuel_l: 1000,
        fuel_cost_tl: 25000,
        anomaly_count: 5,
        trip_count: 25,
      },
      previous: {
        fuel_l: 1050,
        fuel_cost_tl: 26250,
        anomaly_count: 8,
        trip_count: 23,
      },
      fuel_l_delta_pct: -4.76,
      fuel_cost_delta_pct: -4.76,
      anomaly_delta_pct: -37.5,
      trip_delta_pct: 8.7,
      current_start: "2026-06-01",
      current_end: "2026-06-30",
      previous_start: "2026-05-01",
      previous_end: "2026-05-31",
    });

    const result = await fleetInsightsService.getComparison("month");

    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/reports/insights/fleet/comparison",
      method: "GET",
    });
    expect(result.period).toBe("month");
    expect(result.fuel_l_delta_pct).toBe(-4.76);
  });

  it("getComparison defaults to month period", async () => {
    mockCustomAxios.mockResolvedValueOnce({ period: "month" });
    await fleetInsightsService.getComparison();
    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/reports/insights/fleet/comparison",
      method: "GET",
    });
  });

  it("getComparison returns week comparison", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      period: "week",
      current: { fuel_l: 150, fuel_cost_tl: 3750 },
      previous: { fuel_l: 160, fuel_cost_tl: 4000 },
    });

    const result = await fleetInsightsService.getComparison("week");
    expect(result.period).toBe("week");
  });

  it("getComparison handles null deltas", async () => {
    mockCustomAxios.mockResolvedValueOnce({
      period: "month",
      current: { fuel_l: 1000 },
      previous: { fuel_l: 1000 },
      fuel_l_delta_pct: null,
    });

    const result = await fleetInsightsService.getComparison("month");
    expect(result.fuel_l_delta_pct).toBeNull();
  });

  it("getComparison handles API errors", async () => {
    mockCustomAxios.mockRejectedValueOnce(new Error("Network error"));
    await expect(fleetInsightsService.getComparison()).rejects.toThrow(
      "Network error",
    );
  });
});
