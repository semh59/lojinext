import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "../DashboardPage";

vi.mock("../../api/reports", () => ({
  reportService: {
    getDashboardStats: vi.fn().mockResolvedValue({
      toplam_sefer: 42,
      aktif_arac: 10,
      bugun_sefer: 5,
      toplam_km: 1000,
      toplam_yakit: 300,
      filo_ortalama: 30,
      aktif_sofor: 8,
      toplam_arac: 15,
      trends: { sefer: 0, km: 0, tuketim: 0 },
    }),
    getConsumptionTrend: vi.fn().mockResolvedValue([]),
  },
}));
vi.mock("../../api/anomalies", () => ({
  anomalyService: {
    getFleetInsights: vi.fn().mockResolvedValue({
      leakage: {
        route_deviation_km: 12,
        route_deviation_cost: 150,
        fuel_gap_liters: 45,
        fuel_gap_cost: 200,
      },
      maintenance: { urgent_count: 2, warning_count: 3, vehicles: [] },
    }),
  },
}));
vi.mock("../../api/predictions", () => ({
  predictionService: {
    getComparison: vi.fn().mockResolvedValue({
      mae: 1.2,
      rmse: 2.1,
      total_compared: 100,
      accuracy_distribution: {
        good: 80,
        warning: 15,
        error: 5,
        good_pct: 80,
        warning_pct: 15,
        error_pct: 5,
      },
      trend: [],
    }),
  },
}));

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("renders dashboard container", () => {
    wrap(<DashboardPage />);
    expect(screen.getByTestId("dashboard-page")).toBeTruthy();
  });
});
