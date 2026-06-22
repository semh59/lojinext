import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";
import { ROICalculator } from "../ROICalculator";
import { reportRoiText } from "../../../resources/tr/reports";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

// reportsApi mock
vi.mock("../../../services/api", () => ({
  reportsApi: {
    getRoiStats: vi.fn().mockResolvedValue({
      annual_roi_percentage: 120,
      payback_months: 10.5,
      net_annual_savings: 60000,
      total_investment: 50000,
    }),
    getSavingsPotential: vi.fn().mockResolvedValue({
      current_consumption: 35.2,
      target_consumption: 28,
      current_cost: 200000,
      target_cost: 160000,
      potential_savings: 120000,
      savings_percentage: 20,
      annual_projection: 40000,
    }),
  },
}));

describe("ROICalculator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the main heading Yatırım Analizi", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(screen.getByText(reportRoiText.title)).toBeInTheDocument();
    });
  });

  it("renders the description text", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(screen.getByText(reportRoiText.description)).toBeInTheDocument();
    });
  });

  it("renders investment amount label", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(
        screen.getByText(reportRoiText.investmentAmount),
      ).toBeInTheDocument();
    });
  });

  it("renders range slider", () => {
    render(<ROICalculator />);
    const slider = screen.getByRole("slider");
    expect(slider).toBeInTheDocument();
  });

  it("shows monthly potential label", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(
        screen.getByText(reportRoiText.monthlyPotential),
      ).toBeInTheDocument();
    });
  });

  it("shows annual savings label", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(screen.getByText(reportRoiText.annualSavings)).toBeInTheDocument();
    });
  });

  it("shows ROI metric label", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(
        screen.getByText(reportRoiText.roiMetricTitle),
      ).toBeInTheDocument();
    });
  });

  it("shows strong impact message when ROI > 100%", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      // ROI=120% > 100, payback_months=10.5
      expect(
        screen.getByText(/geri ödeme süresi 10\.5 ay/),
      ).toBeInTheDocument();
    });
  });

  it("shows ROI percentage formatted with % sign", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      expect(screen.getByText("%120")).toBeInTheDocument();
    });
  });

  it("shows consumption info from savings data", async () => {
    render(<ROICalculator />);
    await waitFor(() => {
      // The savings text contains current_consumption from mocked value
      expect(screen.getByText(/35\.2 L\/100km/)).toBeInTheDocument();
    });
  });

  it("shows ROI error box when getRoiStats fails", async () => {
    const { reportsApi } = await import("../../../services/api");
    (reportsApi.getRoiStats as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("server error"),
    );

    render(<ROICalculator />);
    await waitFor(() => {
      expect(
        screen.getByText(reportRoiText.roiUnavailable),
      ).toBeInTheDocument();
    });
  });

  it("shows savings error box when getSavingsPotential fails", async () => {
    const { reportsApi } = await import("../../../services/api");
    (
      reportsApi.getSavingsPotential as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce(new Error("server error"));

    render(<ROICalculator />);
    await waitFor(() => {
      expect(
        screen.getByText(reportRoiText.savingsUnavailable),
      ).toBeInTheDocument();
    });
  });
});
