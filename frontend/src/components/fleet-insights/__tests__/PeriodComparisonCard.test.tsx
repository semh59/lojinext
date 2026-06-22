import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/fleet-insights", () => ({
  fleetInsightsService: { getComparison: vi.fn() },
}));

import { fleetInsightsService } from "../../../api/fleet-insights";
import { PeriodComparisonCard } from "../PeriodComparisonCard";

describe("PeriodComparisonCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("happy path: 4 metrik ve delta degerleri gorunur", async () => {
    (
      fleetInsightsService.getComparison as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      period: "month",
      current: {
        fuel_l: 1000,
        fuel_cost_tl: 50_000,
        anomaly_count: 5,
        trip_count: 30,
      },
      previous: {
        fuel_l: 1100,
        fuel_cost_tl: 55_000,
        anomaly_count: 7,
        trip_count: 28,
      },
      fuel_l_delta_pct: -9.1,
      fuel_cost_delta_pct: -9.1,
      anomaly_delta_pct: -28.6,
      trip_delta_pct: 7.1,
      current_start: "2026-04-27",
      current_end: "2026-05-27",
      previous_start: "2026-03-28",
      previous_end: "2026-04-27",
    });
    render(<PeriodComparisonCard period="month" />);
    await waitFor(() =>
      expect(screen.getByText(/Bu Ay vs Geçen/)).toBeInTheDocument(),
    );
    // 4 metrik etiketi
    expect(screen.getByText("Yakıt")).toBeInTheDocument();
    expect(screen.getByText("Yakıt Maliyeti")).toBeInTheDocument();
    expect(screen.getByText("Tamamlanan Sefer")).toBeInTheDocument();
    expect(screen.getByText("Anomali (öncelikli)")).toBeInTheDocument();
    // Yakıt -%9.1 → success tone (lower is better) — hem fuel_l hem fuel_cost
    expect(screen.getAllByText("-9.1%").length).toBeGreaterThanOrEqual(1);
  });

  it('delta_pct null → "veri yok" göstergesi', async () => {
    (
      fleetInsightsService.getComparison as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      period: "week",
      current: {
        fuel_l: 100,
        fuel_cost_tl: 5000,
        anomaly_count: 0,
        trip_count: 3,
      },
      previous: {
        fuel_l: 0,
        fuel_cost_tl: 0,
        anomaly_count: 0,
        trip_count: 0,
      },
      fuel_l_delta_pct: null,
      fuel_cost_delta_pct: null,
      anomaly_delta_pct: null,
      trip_delta_pct: null,
      current_start: "2026-05-20",
      current_end: "2026-05-27",
      previous_start: "2026-05-13",
      previous_end: "2026-05-20",
    });
    render(<PeriodComparisonCard period="week" />);
    await waitFor(() => screen.getByText(/Bu Hafta vs Geçen/));
    // "veri yok" tüm metriklerde
    expect(screen.getAllByText("veri yok").length).toBeGreaterThanOrEqual(4);
  });

  it('hata durumu → "yüklenemedi" mesajı', async () => {
    (
      fleetInsightsService.getComparison as ReturnType<typeof vi.fn>
    ).mockRejectedValue(new Error("network"));
    render(<PeriodComparisonCard period="month" />);
    await waitFor(() =>
      expect(screen.getByText(/Karşılaştırma yüklenemedi/)).toBeInTheDocument(),
    );
  });
});
