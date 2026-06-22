import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { PredictionSimulator } from "../PredictionSimulator";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

// recharts stub (used by PredictionResult / XaiExplainPanel if rendered)
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

// vehicle-service mock
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({
      items: [
        { id: 1, plaka: "06ABC001" },
        { id: 2, plaka: "34XYZ999" },
      ],
      total: 2,
    }),
  },
}));

// driver-service mock
vi.mock("../../../api/drivers", () => ({
  driverService: {
    getAll: vi.fn().mockResolvedValue({
      items: [{ id: 10, ad_soyad: "Ahmet Yılmaz" }],
      total: 1,
    }),
  },
}));

// prediction-service mock
vi.mock("../../../api/predictions", () => ({
  predictionService: {
    predict: vi.fn().mockResolvedValue({
      tahmini_tuketim: 32.5,
      prediction_liters: 32.5,
      model_used: "ensemble",
    }),
    explain: vi.fn().mockResolvedValue({
      tahmini_tuketim: 32.5,
      components: { mesafe: 0.5, ton: 0.3 },
    }),
  },
}));

// PredictionResult stub
vi.mock("../PredictionResult", () => ({
  PredictionResult: ({ result }: any) => (
    <div>Tahmin: {result.tahmini_tuketim}</div>
  ),
}));

// XaiExplainPanel stub
vi.mock("../XaiExplainPanel", () => ({
  XaiExplainPanel: () => <div>XAI Panel</div>,
}));

describe("PredictionSimulator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the section heading", () => {
    render(<PredictionSimulator />);
    expect(screen.getByText("Sefer Simülasyonu")).toBeInTheDocument();
  });

  it("renders the submit button", () => {
    render(<PredictionSimulator />);
    expect(
      screen.getByRole("button", { name: "Tahmini Hesapla" }),
    ).toBeInTheDocument();
  });

  it("submit button is disabled when no vehicle selected (aracId=0)", () => {
    render(<PredictionSimulator />);
    const btn = screen.getByRole("button", { name: "Tahmini Hesapla" });
    expect(btn).toBeDisabled();
  });

  it("renders vehicle options after data loads", async () => {
    render(<PredictionSimulator />);
    await waitFor(() => {
      expect(screen.getByText("06ABC001")).toBeInTheDocument();
      expect(screen.getByText("34XYZ999")).toBeInTheDocument();
    });
  });

  it("renders driver options after data loads", async () => {
    render(<PredictionSimulator />);
    await waitFor(() => {
      expect(screen.getByText("Ahmet Yılmaz")).toBeInTheDocument();
    });
  });

  it("enables submit button after selecting a vehicle", async () => {
    render(<PredictionSimulator />);
    await waitFor(() => screen.getByText("06ABC001"));

    const vehicleSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(vehicleSelect, { target: { value: "1" } });

    expect(
      screen.getByRole("button", { name: "Tahmini Hesapla" }),
    ).not.toBeDisabled();
  });

  it("calls predictionService.predict on submit and shows result", async () => {
    const { predictionService } = await import("../../../api/predictions");

    render(<PredictionSimulator />);
    await waitFor(() => screen.getByText("06ABC001"));

    const vehicleSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(vehicleSelect, { target: { value: "1" } });

    fireEvent.click(screen.getByRole("button", { name: "Tahmini Hesapla" }));

    await waitFor(() => {
      expect(predictionService.predict).toHaveBeenCalledTimes(1);
      expect(screen.getByText(/Tahmin:/)).toBeInTheDocument();
    });
  });

  it("shows Açıkla button after result and toggles XAI panel", async () => {
    render(<PredictionSimulator />);
    await waitFor(() => screen.getByText("06ABC001"));

    const vehicleSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(vehicleSelect, { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Tahmini Hesapla" }));

    await waitFor(() => screen.getByText(/Tahmin:/));

    const explainBtn = screen.getByRole("button", { name: "Açıkla" });
    fireEvent.click(explainBtn);

    await waitFor(() => {
      expect(screen.getByText("XAI Panel")).toBeInTheDocument();
    });
  });

  it("shows difficulty select with Normal/Orta/Zor options", () => {
    render(<PredictionSimulator />);
    // The zorluk select is the 3rd combobox (Araç, Şoför, Zorluk)
    expect(screen.getByText("Normal")).toBeInTheDocument();
    expect(screen.getByText("Orta")).toBeInTheDocument();
    expect(screen.getByText("Zor")).toBeInTheDocument();
  });
});
