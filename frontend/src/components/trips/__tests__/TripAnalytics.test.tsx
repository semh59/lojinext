import { render, screen } from "../../../test/test-utils";
import { describe, it, expect, vi } from "vitest";
import { TripAnalytics } from "../TripAnalytics";
import { tripAnalyticsText } from "../../../resources/tr/trips";
import type { FuelPerformanceAnalyticsResponse } from "../../../types";

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

// recharts stub — actual chart rendering is not meaningful in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  LineChart: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Cell: () => null,
}));

const MOCK_DATA: FuelPerformanceAnalyticsResponse = {
  kpis: {
    mae: 3.45,
    rmse: 5.12,
    total_compared: 12,
    high_deviation_ratio: 16.7,
  },
  trend: [
    { date: "2026-01-01", actual: 28.5, predicted: 27.8 },
    { date: "2026-02-01", actual: 30.1, predicted: 29.5 },
  ],
  distribution: {
    good: 8,
    warning: 3,
    error: 1,
    good_pct: 66.7,
    warning_pct: 25.0,
    error_pct: 8.3,
  },
  outliers: [
    {
      id: 42,
      plaka: "34XYZ999",
      sapma_pct: 22.4,
      reason_label: "Yüksek tüketim",
    },
  ],
  low_data: false,
};

describe("TripAnalytics", () => {
  it("shows loading skeletons when isLoading=true", () => {
    const { container } = render(<TripAnalytics isLoading={true} />);
    // Skeleton elements are rendered (h-28 and h-[350px] are both present)
    const skeletonElements = container.querySelectorAll(
      ".animate-pulse, [class*='h-28'], [class*='h-\\[350px\\]']",
    );
    expect(skeletonElements.length).toBeGreaterThan(0);
  });

  it("shows insufficient data message when data is undefined", () => {
    render(<TripAnalytics />);
    expect(
      screen.getByText(tripAnalyticsText.insufficientTitle),
    ).toBeInTheDocument();
  });

  it("shows insufficient data message when low_data=true", () => {
    render(<TripAnalytics data={{ ...MOCK_DATA, low_data: true }} />);
    expect(
      screen.getByText(tripAnalyticsText.insufficientTitle),
    ).toBeInTheDocument();
  });

  it("shows insufficient data message when total_compared < 3", () => {
    render(
      <TripAnalytics
        data={{ ...MOCK_DATA, kpis: { ...MOCK_DATA.kpis, total_compared: 2 } }}
      />,
    );
    expect(
      screen.getByText(tripAnalyticsText.insufficientTitle),
    ).toBeInTheDocument();
  });

  it("renders all four KPI labels with valid data", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(
      screen.getByText(tripAnalyticsText.kpis.mae.label),
    ).toBeInTheDocument();
    expect(
      screen.getByText(tripAnalyticsText.kpis.rmse.label),
    ).toBeInTheDocument();
    expect(
      screen.getByText(tripAnalyticsText.kpis.compared.label),
    ).toBeInTheDocument();
    expect(
      screen.getByText(tripAnalyticsText.kpis.highDeviation.label),
    ).toBeInTheDocument();
  });

  it("renders MAE value formatted to 2 decimal places", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(screen.getByText("3.45")).toBeInTheDocument();
  });

  it("renders high deviation as percentage string", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(screen.getByText("%16.7")).toBeInTheDocument();
  });

  it("renders trend chart section title", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(screen.getByText(tripAnalyticsText.trend.title)).toBeInTheDocument();
  });

  it("renders distribution chart section title", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(
      screen.getByText(tripAnalyticsText.distribution.title),
    ).toBeInTheDocument();
  });

  it("renders outlier row with plate and deviation", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(screen.getByText(/34XYZ999/)).toBeInTheDocument();
    expect(screen.getByText("%22.4")).toBeInTheDocument();
  });

  it("renders outliers section title", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    expect(
      screen.getByText(tripAnalyticsText.outliers.title),
    ).toBeInTheDocument();
  });

  it("shows total_compared count as number", () => {
    render(<TripAnalytics data={MOCK_DATA} />);
    // total_compared = 12, rendered directly as {kpi.value}
    expect(screen.getByText("12")).toBeInTheDocument();
  });
});
