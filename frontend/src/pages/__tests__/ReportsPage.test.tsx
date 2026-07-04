/**
 * 0-mock epiği: ReportsPage'in kendi API çağrıları (reportsApi ==
 * reportService, cost/trend + cost/vehicle-comparison) artık gerçek
 * backend'e karşı çalışıyor — `vi.mock("../../services/api")` kaldırıldı.
 * Alt bileşenler (ReportCards, CostAnalysisChart, ROICalculator, vb.) hâlâ
 * stub'lı kalıyor — orijinal test niyeti zaten "sayfa yapısı/tab
 * geçişleri", alt bileşen davranışı değil.
 *
 * NOT: Bu dosyada 3 test ("switches to ROI tab", "switches to vehicle tab",
 * "switches to cost tab") ÖNCEDEN BİLİNEN, bu session'ın çalışmasından
 * BAĞIMSIZ bir flake içeriyordu (git stash karşılaştırmasıyla defalarca
 * doğrulandı — mock'lu haliyle de aralıklı başarısız oluyordu). Gerçek
 * backend'e geçiş bu flake'i gidermeyi hedeflemiyor, sadece mock→gerçek
 * API dönüşümünü yapıyor.
 */
import {
  beforeAll,
  afterAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

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

vi.mock("../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("../../components/common/ErrorBoundary", () => ({
  default: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

// Alt bileşenleri stub'la — sayfa yapısı/tab geçişleri test ediliyor
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

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ReportsPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let fireEvent: typeof import("../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let ReportsPage: typeof import("../ReportsPage").default;
  let reportPageText: typeof import("../../resources/tr/reports").reportPageText;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../test/test-utils"
    ));
    ({ default: ReportsPage } = await import("../ReportsPage"));
    ({ reportPageText } = await import("../../resources/tr/reports"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
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
    await waitFor(
      () => {
        expect(screen.getByText("ROICalculator")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("switches to vehicle tab and shows empty state text when no real comparison data", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.vehicle));
    await waitFor(
      () => {
        expect(
          screen.getByText("Karşılaştırma verisi yok"),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("switches to cost tab and shows CostAnalysisChart once real cost data resolves", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.cost));
    await waitFor(
      () => {
        expect(screen.getByText("CostAnalysisChart")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

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
