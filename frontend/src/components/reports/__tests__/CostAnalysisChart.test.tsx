import { render, screen } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { CostAnalysisChart } from "../CostAnalysisChart";
import { reportChartText } from "../../../resources/tr/reports";
import type { MonthlyCostTrend } from "../../../api/reports";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, className, ...rest }: any) => (
      <div className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

// recharts stub
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Cell: () => null,
}));

const MOCK_DATA: MonthlyCostTrend[] = [
  {
    month: 1,
    year: 2026,
    label: "Oca 2026",
    fuel_cost: 50000,
    fuel_liters: 1800,
    trip_count: 30,
    total_distance: 15000,
    cost_per_km: 3.33,
    fuel: 50000,
    maintenance: 8000,
  },
  {
    month: 2,
    year: 2026,
    label: "Şub 2026",
    fuel_cost: 55000,
    fuel_liters: 1900,
    trip_count: 32,
    total_distance: 16000,
    cost_per_km: 3.44,
    fuel: 55000,
    maintenance: 9000,
  },
];

describe("CostAnalysisChart", () => {
  it("renders the chart title", () => {
    render(<CostAnalysisChart data={MOCK_DATA} />);
    expect(screen.getByText(reportChartText.title)).toBeInTheDocument();
  });

  it("renders the chart subtitle", () => {
    render(<CostAnalysisChart data={MOCK_DATA} />);
    expect(screen.getByText(reportChartText.subtitle)).toBeInTheDocument();
  });

  it("renders YAKIT legend label", () => {
    render(<CostAnalysisChart data={MOCK_DATA} />);
    // There may be multiple instances (legend + tooltip), so getAllByText is safe
    const fuelLabels = screen.getAllByText(reportChartText.fuel);
    expect(fuelLabels.length).toBeGreaterThan(0);
  });

  it("renders BAKIM legend label", () => {
    render(<CostAnalysisChart data={MOCK_DATA} />);
    const maintLabels = screen.getAllByText(reportChartText.maintenance);
    expect(maintLabels.length).toBeGreaterThan(0);
  });

  it("renders with empty data array without crashing", () => {
    render(<CostAnalysisChart data={[]} />);
    expect(screen.getByText(reportChartText.title)).toBeInTheDocument();
  });

  it("renders chart container element", () => {
    const { container } = render(<CostAnalysisChart data={MOCK_DATA} />);
    // The wrapping motion.div with class "flex h-[450px] w-full flex-col"
    const chartRoot = container.querySelector(".flex.w-full.flex-col");
    expect(chartRoot).not.toBeNull();
  });
});
