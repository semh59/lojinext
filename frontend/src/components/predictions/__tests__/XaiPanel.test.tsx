import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { XaiPanel, EnsembleWeightsPanel } from "../XaiPanel";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

// vehicle-service mock
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({
      items: [
        { id: 5, plaka: "06VEH005" },
        { id: 6, plaka: "34VEH006" },
      ],
      total: 2,
    }),
  },
}));

// prediction-service mock
vi.mock("../../../api/predictions", () => ({
  predictionService: {
    explain: vi.fn().mockResolvedValue({
      tahmini_tuketim: 29.8,
      components: { mesafe: 0.6, ton: 0.25, yol_tipi: 0.15 },
    }),
    getEnsembleStatus: vi.fn().mockResolvedValue({
      weights: { physics: 0.8, lightgbm: 0.05, xgboost: 0.05 },
      total_models: 3,
      lightgbm_available: true,
      xgboost_available: true,
      sklearn_available: true,
      models: {},
    }),
  },
}));

describe("XaiPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders heading XAI — Tahmin Açıklama", () => {
    render(<XaiPanel />);
    expect(screen.getByText("XAI — Tahmin Açıklama")).toBeInTheDocument();
  });

  it("renders the description text", () => {
    render(<XaiPanel />);
    expect(
      screen.getByText("Tüketim tahmininin faktörlerini görün"),
    ).toBeInTheDocument();
  });

  it("shows vehicle options after load", async () => {
    render(<XaiPanel />);
    await waitFor(() => {
      expect(screen.getByText("06VEH005")).toBeInTheDocument();
      expect(screen.getByText("34VEH006")).toBeInTheDocument();
    });
  });

  it("submit button is disabled when no vehicle selected", () => {
    render(<XaiPanel />);
    const btn = screen.getByRole("button", { name: "Tahmin Et + Açıkla" });
    expect(btn).toBeDisabled();
  });

  it("enables submit button after selecting a vehicle", async () => {
    render(<XaiPanel />);
    await waitFor(() => screen.getByText("06VEH005"));

    const vehicleSelect = screen.getByRole("combobox");
    fireEvent.change(vehicleSelect, { target: { value: "5" } });

    expect(
      screen.getByRole("button", { name: "Tahmin Et + Açıkla" }),
    ).not.toBeDisabled();
  });

  it("calls predict explain on submit and shows result", async () => {
    const { predictionService } = await import("../../../api/predictions");

    render(<XaiPanel />);
    await waitFor(() => screen.getByText("06VEH005"));

    const vehicleSelect = screen.getByRole("combobox");
    fireEvent.change(vehicleSelect, { target: { value: "5" } });

    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et + Açıkla" }));

    await waitFor(() => {
      expect(predictionService.explain).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Tahmini Tüketim:/)).toBeInTheDocument();
    });
  });

  it("shows Etki Faktörleri section and factor names after result", async () => {
    render(<XaiPanel />);
    await waitFor(() => screen.getByText("06VEH005"));

    const vehicleSelect = screen.getByRole("combobox");
    fireEvent.change(vehicleSelect, { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et + Açıkla" }));

    await waitFor(() => {
      expect(screen.getByText("Etki Faktörleri")).toBeInTheDocument();
      expect(screen.getByText("mesafe")).toBeInTheDocument();
      expect(screen.getByText("ton")).toBeInTheDocument();
    });
  });
});

describe("EnsembleWeightsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders heading Ensemble Model Ağırlıkları", async () => {
    render(<EnsembleWeightsPanel />);
    await waitFor(() => {
      expect(
        screen.getByText("Ensemble Model Ağırlıkları"),
      ).toBeInTheDocument();
    });
  });

  it("renders weights sorted by value", async () => {
    render(<EnsembleWeightsPanel />);
    await waitFor(() => {
      // physics=0.8 → 80.0%, sorted first
      expect(screen.getByText("80.0%")).toBeInTheDocument();
    });
  });

  it("shows total_models count and availability indicators", async () => {
    render(<EnsembleWeightsPanel />);
    await waitFor(() => {
      expect(screen.getByText(/Toplam model: 3/)).toBeInTheDocument();
    });
  });

  it("shows Henüz eğitim verisi yok when weights are empty", async () => {
    const { predictionService } = await import("../../../api/predictions");
    (
      predictionService.getEnsembleStatus as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce({
      weights: {},
      total_models: 0,
      lightgbm_available: false,
      xgboost_available: false,
      sklearn_available: false,
      models: {},
    });

    render(<EnsembleWeightsPanel />);
    await waitFor(() => {
      expect(screen.getByText("Henüz eğitim verisi yok.")).toBeInTheDocument();
    });
  });
});
