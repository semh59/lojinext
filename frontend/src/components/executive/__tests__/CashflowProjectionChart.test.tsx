import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";

vi.mock("../../../api/executive", () => ({
  executiveService: { getCashflow: vi.fn() },
}));

// Recharts JSDOM uyumsuzluğu için stub
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

import { executiveService } from "../../../api/executive";
import { CashflowProjectionChart } from "../CashflowProjectionChart";

describe("CashflowProjectionChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("grand_total + chart render edilir", async () => {
    (
      executiveService.getCashflow as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      horizon_days: 84,
      weeks: [
        {
          week_start: "2026-05-27",
          fuel_tl: 10_000,
          maintenance_tl: 5_000,
          penalty_tl: 0,
          total_tl: 15_000,
        },
      ],
      total_fuel_tl: 10_000,
      total_maintenance_tl: 5_000,
      total_penalty_tl: 0,
      grand_total_tl: 15_000,
      confidence: 0.65,
      assumptions: {
        diesel_price_tl: 50,
        avg_bakim_cost_tl: 5_000,
        upcoming_bakim_count: 1,
      },
    });
    render(<CashflowProjectionChart />);
    await waitFor(() => expect(screen.getByText(/Toplam/)).toBeInTheDocument());
    expect(screen.getByText(/₺15\.000/)).toBeInTheDocument();
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  });
});
