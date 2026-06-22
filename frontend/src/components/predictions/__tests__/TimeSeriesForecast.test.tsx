import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { TimeSeriesForecast } from "../TimeSeriesForecast";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

// recharts stub
vi.mock("recharts", () => ({
  AreaChart: ({ children }: any) => <div>{children}</div>,
  Area: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  Line: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

// chart-theme stub
vi.mock("../../../lib/chart-theme", () => ({
  chartTheme: {
    grid: {},
    tick: {},
    tickSmall: {},
    tooltip: {},
    colors: { accent: "#6366f1" },
  },
}));

// vehicle-service mock
vi.mock("../../../api/vehicles", () => ({
  vehicleService: {
    getAll: vi.fn().mockResolvedValue({
      items: [
        { id: 1, plaka: "06TS001" },
        { id: 2, plaka: "34TS002" },
      ],
      total: 2,
    }),
  },
}));

// prediction-service mock
vi.mock("../../../api/predictions", () => ({
  predictionService: {
    timeSeriesForecast: vi.fn().mockResolvedValue({
      series: [
        {
          date: "2026-06-05",
          value: 120.5,
          confidence_low: 110,
          confidence_high: 130,
        },
        {
          date: "2026-06-06",
          value: 118.2,
          confidence_low: 108,
          confidence_high: 128,
        },
      ],
      trend: "stable",
      summary: "Tüketim stabil seyretmektedir.",
      method: "arima",
    }),
    timeSeriesTrend: vi.fn().mockResolvedValue({
      success: true,
      trend: "stable",
    }),
  },
}));

describe("TimeSeriesForecast", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the section heading Haftalık Tahmin", () => {
    render(<TimeSeriesForecast />);
    expect(screen.getByText("Haftalık Tahmin")).toBeInTheDocument();
  });

  it("renders the description text", () => {
    render(<TimeSeriesForecast />);
    expect(
      screen.getByText("7 günlük tüketim projeksiyonu + güven aralığı"),
    ).toBeInTheDocument();
  });

  it("renders Tahmin Et button", () => {
    render(<TimeSeriesForecast />);
    expect(
      screen.getByRole("button", { name: "Tahmin Et" }),
    ).toBeInTheDocument();
  });

  it("renders Tüm Filo option in vehicle select", () => {
    render(<TimeSeriesForecast />);
    expect(screen.getByText("Tüm Filo")).toBeInTheDocument();
  });

  it("renders vehicle options after load", async () => {
    render(<TimeSeriesForecast />);
    await waitFor(() => {
      expect(screen.getByText("06TS001")).toBeInTheDocument();
      expect(screen.getByText("34TS002")).toBeInTheDocument();
    });
  });

  it("shows initial prompt text before forecast is run", () => {
    render(<TimeSeriesForecast />);
    // Component uses Unicode curly quotes U+201C / U+201D
    expect(screen.getByText(/butonuyla projeksiyonu olu/)).toBeInTheDocument();
  });

  it("calls timeSeriesForecast on button click and shows summary text", async () => {
    const { predictionService } = await import("../../../api/predictions");

    render(<TimeSeriesForecast />);
    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et" }));

    await waitFor(() => {
      expect(predictionService.timeSeriesForecast).toHaveBeenCalledTimes(1);
      expect(
        screen.getByText("Tüketim stabil seyretmektedir."),
      ).toBeInTheDocument();
    });
  });

  it("shows trend badge Stabil after forecast", async () => {
    render(<TimeSeriesForecast />);
    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et" }));

    await waitFor(() => {
      expect(screen.getByText("Stabil")).toBeInTheDocument();
    });
  });

  it("shows error message when forecast call fails", async () => {
    const { predictionService } = await import("../../../api/predictions");
    (
      predictionService.timeSeriesForecast as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce(new Error("network error"));

    render(<TimeSeriesForecast />);
    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et" }));

    await waitFor(() => {
      expect(screen.getByText(/Tahmin oluşturulamadı/)).toBeInTheDocument();
    });
  });
});
