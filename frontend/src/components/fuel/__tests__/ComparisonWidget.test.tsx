import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";
import { ComparisonWidget } from "../ComparisonWidget";
import { fuelComparisonText } from "../../../resources/tr/fuel";
import { PredictionComparisonResponse } from "../../../types";

// Recharts JSDOM stub
vi.mock("recharts", () => ({
  AreaChart: ({ children }: any) => <div>{children}</div>,
  Area: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

const MOCK_DATA: PredictionComparisonResponse = {
  mae: 2.35,
  rmse: 3.12,
  total_compared: 18,
  accuracy_distribution: {
    good: 12,
    warning: 4,
    error: 2,
    good_pct: 66.7,
    warning_pct: 22.2,
    error_pct: 11.1,
  },
  trend: [
    { date: "2024-01-01", actual: 31.5, predicted: 29.8 },
    { date: "2024-01-02", actual: 33.0, predicted: 31.2 },
  ],
};

const EMPTY_DATA: PredictionComparisonResponse = {
  mae: 0,
  rmse: 0,
  total_compared: 0,
  accuracy_distribution: {
    good: 0,
    warning: 0,
    error: 0,
    good_pct: 0,
    warning_pct: 0,
    error_pct: 0,
  },
  trend: [],
};

describe("ComparisonWidget", () => {
  it("shows empty/unavailable state when total_compared=0", () => {
    render(<ComparisonWidget data={EMPTY_DATA} />);
    expect(
      screen.getByText(fuelComparisonText.unavailableTitle),
    ).toBeInTheDocument();
    expect(
      screen.getByText(fuelComparisonText.unavailableDescription),
    ).toBeInTheDocument();
  });

  it("shows loading skeleton when isLoading=true", () => {
    const { container } = render(
      <ComparisonWidget data={EMPTY_DATA} isLoading={true} />,
    );
    // Loading returns a pulse div, no content text
    expect(
      screen.queryByText(fuelComparisonText.unavailableTitle),
    ).not.toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders MAE value when data is present", () => {
    render(<ComparisonWidget data={MOCK_DATA} />);
    expect(screen.getByText("2.35")).toBeInTheDocument();
  });

  it("renders performance and accuracy section headings", () => {
    render(<ComparisonWidget data={MOCK_DATA} />);
    expect(
      screen.getByText(fuelComparisonText.performanceTitle),
    ).toBeInTheDocument();
    expect(
      screen.getByText(fuelComparisonText.accuracyTitle),
    ).toBeInTheDocument();
  });

  it("renders legend labels for predicted and actual", () => {
    render(<ComparisonWidget data={MOCK_DATA} />);
    // Legend labels appear multiple times (chart + legend) — just check at least one
    expect(
      screen.getAllByText(fuelComparisonText.legend.predicted).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(fuelComparisonText.legend.actual).length,
    ).toBeGreaterThan(0);
  });

  it("renders RMSE hint text", () => {
    render(<ComparisonWidget data={MOCK_DATA} />);
    expect(
      screen.getByText(fuelComparisonText.rmseValue(MOCK_DATA.rmse)),
    ).toBeInTheDocument();
  });

  it("renders summary line with total_compared count", () => {
    render(<ComparisonWidget data={MOCK_DATA} />);
    expect(
      screen.getByText(fuelComparisonText.summary(18)),
    ).toBeInTheDocument();
  });

  it("renders vehicle selector when vehicles and onVehicleChange provided", () => {
    const vehicles = [
      { id: 1, plaka: "34TEST01" },
      { id: 2, plaka: "06TEST02" },
    ];
    const onVehicleChange = vi.fn();
    render(
      <ComparisonWidget
        data={MOCK_DATA}
        vehicles={vehicles}
        selectedVehicleId={null}
        onVehicleChange={onVehicleChange}
      />,
    );
    // "Tüm Filo" is the default option in the select
    expect(screen.getAllByText("Tüm Filo").length).toBeGreaterThan(0);
    // Vehicle options
    expect(screen.getAllByText("34TEST01").length).toBeGreaterThan(0);
  });

  it("calls onVehicleChange when a vehicle is selected", () => {
    const vehicles = [
      { id: 1, plaka: "34TEST01" },
      { id: 2, plaka: "06TEST02" },
    ];
    const onVehicleChange = vi.fn();
    render(
      <ComparisonWidget
        data={MOCK_DATA}
        vehicles={vehicles}
        selectedVehicleId={null}
        onVehicleChange={onVehicleChange}
      />,
    );
    const select = screen.getByLabelText("Araç filtresi");
    fireEvent.change(select, { target: { value: "1" } });
    expect(onVehicleChange).toHaveBeenCalledWith(1);
  });
});
