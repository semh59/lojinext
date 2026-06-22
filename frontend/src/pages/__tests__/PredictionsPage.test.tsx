import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import PredictionsPage from "../PredictionsPage";

vi.mock("../../api/predictions", () => ({
  predictionService: {
    getEnsembleStatus: vi.fn().mockResolvedValue({
      models: {
        physics: true,
        lightgbm: false,
        xgboost: false,
        gradient_boosting: true,
        random_forest: true,
      },
      weights: {
        physics: 0.8,
        lightgbm: 0.05,
        xgboost: 0.05,
        gradient_boosting: 0.05,
        random_forest: 0.05,
      },
      total_models: 3,
      sklearn_available: true,
      lightgbm_available: false,
      xgboost_available: false,
    }),
    getComparison: vi.fn().mockResolvedValue({
      mae: 1.2,
      rmse: 2.1,
      total_compared: 50,
      accuracy_distribution: {
        good: 40,
        warning: 7,
        error: 3,
        good_pct: 80,
        warning_pct: 14,
        error_pct: 6,
      },
      trend: [{ date: "2026-01-01", actual: 28, predicted: 27.5 }],
    }),
    explain: vi
      .fn()
      .mockResolvedValue({ tahmini_tuketim: 29.5, components: {} }),
  },
}));
vi.mock("../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({ items: [], total: 0 }),
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

describe("PredictionsPage", () => {
  it("renders page container", () => {
    wrap(<PredictionsPage />);
    expect(screen.getByTestId("predictions-page")).toBeTruthy();
  });
});
