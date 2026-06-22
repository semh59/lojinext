import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../test/test-utils";
import ReportsPage from "../ReportsPage";
import { reportPageText } from "../../resources/tr/reports";

// framer-motion passthrough
vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, layoutId, ...rest }: any) => (
      <div {...rest}>{children}</div>
    ),
  },
}));

// recharts stub
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

// usePageTitle
vi.mock("../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// ErrorBoundary passthrough
vi.mock("../../components/common/ErrorBoundary", () => ({
  default: ({ children }: any) => <>{children}</>,
}));

// NotificationContext
vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

// Sub-components — isolate page structure tests
vi.mock("../../components/reports/ReportCards", () => ({
  ReportCards: ({ onDownload }: any) => (
    <div>
      <span>ReportCards</span>
      <button onClick={() => onDownload("fleet_summary")}>PDF İndir</button>
    </div>
  ),
}));
vi.mock("../../components/reports/CostAnalysisChart", () => ({
  CostAnalysisChart: () => <div>CostAnalysisChart</div>,
}));
vi.mock("../../components/reports/SavingsPotentialCard", () => ({
  SavingsPotentialCard: () => <div>SavingsPotentialCard</div>,
}));
vi.mock("../../components/reports/PeriodCostBreakdown", () => ({
  PeriodCostBreakdown: () => <div>PeriodCostBreakdown</div>,
}));
vi.mock("../../components/reports/ROICalculator", () => ({
  ROICalculator: () => <div>ROICalculator</div>,
}));
vi.mock("../../components/shared/ExportDialog", () => ({
  ExportDialog: ({ isOpen, onClose }: any) =>
    isOpen ? (
      <div role="dialog">
        <button onClick={onClose}>Vazgeç</button>
      </div>
    ) : null,
}));

// reportsApi
vi.mock("../../services/api", () => ({
  reportsApi: {
    getCostAnalysis: vi.fn().mockResolvedValue([]),
    getVehicleComparison: vi.fn().mockResolvedValue([]),
    getRoiStats: vi.fn().mockResolvedValue(null),
    getSavingsPotential: vi.fn().mockResolvedValue(null),
    downloadPdf: vi.fn().mockResolvedValue(new Blob()),
    downloadExcel: vi.fn().mockResolvedValue(new Blob()),
  },
}));

describe("ReportsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the main page heading", () => {
    render(<ReportsPage />);
    expect(screen.getByText(reportPageText.heading)).toBeInTheDocument();
  });

  it("renders the page description", () => {
    render(<ReportsPage />);
    expect(screen.getByText(reportPageText.description)).toBeInTheDocument();
  });

  it("renders all four tab labels", () => {
    render(<ReportsPage />);
    expect(screen.getByText(reportPageText.tabs.pdf)).toBeInTheDocument();
    expect(screen.getByText(reportPageText.tabs.cost)).toBeInTheDocument();
    expect(screen.getByText(reportPageText.tabs.roi)).toBeInTheDocument();
    expect(screen.getByText(reportPageText.tabs.vehicle)).toBeInTheDocument();
  });

  it("shows ReportCards by default (pdf tab active)", () => {
    render(<ReportsPage />);
    expect(screen.getByText("ReportCards")).toBeInTheDocument();
  });

  it("switches to ROI tab and shows ROICalculator", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.roi));
    await waitFor(() => {
      expect(screen.getByText("ROICalculator")).toBeInTheDocument();
    });
  });

  it("switches to vehicle tab and shows empty state text when no data", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.vehicle));
    await waitFor(() => {
      expect(screen.getByText("Karşılaştırma verisi yok")).toBeInTheDocument();
    });
  });

  it("switches to cost tab and shows CostAnalysisChart when data loaded", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.cost));
    await waitFor(() => {
      expect(screen.getByText("CostAnalysisChart")).toBeInTheDocument();
    });
  });

  it("opens ExportDialog when ReportCards triggers onDownload", async () => {
    render(<ReportsPage />);
    // default pdf tab shows ReportCards stub with a PDF İndir button
    fireEvent.click(screen.getByText("PDF İndir"));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("closes ExportDialog when Vazgeç is clicked", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText("PDF İndir"));
    await waitFor(() => screen.getByRole("dialog"));
    fireEvent.click(screen.getByText("Vazgeç"));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
