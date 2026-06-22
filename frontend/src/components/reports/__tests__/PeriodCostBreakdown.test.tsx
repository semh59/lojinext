import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/reports", () => ({
  reportService: {
    getPeriodCost: vi.fn(),
  },
}));

import { reportService } from "../../../api/reports";
import { PeriodCostBreakdown } from "../PeriodCostBreakdown";

describe("PeriodCostBreakdown", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("5 KPI kartını backend yanıtından doldurur", async () => {
    (reportService.getPeriodCost as ReturnType<typeof vi.fn>).mockResolvedValue(
      {
        fuel_cost: 125000,
        fuel_liters: 3000,
        avg_price_per_liter: 41.67,
        trip_count: 24,
        total_distance: 9500,
        cost_per_km: 13.16,
        period_start: "2026-04-22",
        period_end: "2026-05-22",
      },
    );

    render(<PeriodCostBreakdown />);

    await waitFor(() =>
      expect(screen.getByText(/41\.67 ₺/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/13\.16 ₺/)).toBeInTheDocument();
    expect(screen.getByText("24")).toBeInTheDocument();
    expect(screen.getByText(/9\.?500 km/)).toBeInTheDocument();
  });

  it("drill-down modunda plaka etiketi gösterir", async () => {
    (reportService.getPeriodCost as ReturnType<typeof vi.fn>).mockResolvedValue(
      {
        fuel_cost: 5000,
        fuel_liters: 120,
        avg_price_per_liter: 41.67,
        trip_count: 2,
        total_distance: 400,
        cost_per_km: 12.5,
        period_start: "2026-04-22",
        period_end: "2026-05-22",
      },
    );
    render(<PeriodCostBreakdown aracId={7} plakaLabel="34 ABC 123" />);
    await waitFor(() =>
      expect(screen.getByText("34 ABC 123")).toBeInTheDocument(),
    );
  });
});
