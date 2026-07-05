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
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
  REAL_BACKEND_URL,
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

// recharts stub — ResponsiveContainer'a test-id veriyoruz: araç sekmesi
// testinde "grafik dalı render edildi" kanıtı, plaka/eksen metni yerine bu
// (recharts stub'lı olduğu için eksen/etiket metinleri DOM'a hiç basılmaz).
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="vehicle-comparison-chart">{children}</div>
  ),
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
  let token = "";
  let vehicleId: number | undefined;
  const tag = Date.now();

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../test/test-utils"
    ));
    ({ default: ReportsPage } = await import("../ReportsPage"));
    ({ reportPageText } = await import("../../resources/tr/reports"));

    // Hermetiklik: araç sekmesi testi "en az bir araç" ister —
    // /advanced-reports/cost/vehicle-comparison sıfır-seferli araçları da
    // listeler (canlı curl ile doğrulandı), bu yüzden tek bir araç kaydı
    // yeterli. Boş CI DB'sinde de kirli dev DB'sinde de deterministik.
    const vehicleRes = await axios.post(
      `${REAL_BACKEND_URL}/vehicles/`,
      { plaka: `34 RPT${tag % 900}`, marka: "ReportsPageTestMarka" },
      { headers: { Authorization: `Bearer ${token}` } },
    );
    vehicleId = vehicleRes.data.id;
  }, 20000);

  afterAll(async () => {
    if (vehicleId) {
      await axios
        .delete(`${REAL_BACKEND_URL}/vehicles/${vehicleId}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        .catch(() => {});
    }
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

  // NOT: sayfanın varsayılan sekmesi artık "overview" (bkz. ReportsPage.tsx
  // `useState<ReportTabId>("overview")`) — eski "pdf tab varsayılan" varsayımı
  // stale'di. PDF sekmesine tıklayınca ReportCards render edilir.
  it("shows ReportCards after switching to the pdf tab", async () => {
    render(<ReportsPage />);
    expect(screen.queryByText("ReportCards")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText(reportPageText.tabs.pdf));
    await waitFor(() => {
      expect(screen.getByText("ReportCards")).toBeInTheDocument();
    });
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

  // beforeAll kendi aracını yarattığı için karşılaştırma listesi asla boş
  // değildir → grafik dalı render edilir (recharts stub'ının test-id'li
  // ResponsiveContainer'ı). "Karşılaştırma verisi yok" boş-durum metnine
  // assert etmek boş-DB'ye bağımlıydı; kirli bir DB'de her zaman kırılırdı.
  it("switches to vehicle tab and renders the comparison chart once real data resolves", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.vehicle));
    await waitFor(
      () => {
        expect(
          screen.getByTestId("vehicle-comparison-chart"),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(
      screen.queryByText("Karşılaştırma verisi yok"),
    ).not.toBeInTheDocument();
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
    // pdf sekmesi varsayılan değil — önce sekmeye geç, ReportCards stub'ı
    // PDF İndir butonunu render etsin.
    fireEvent.click(screen.getByText(reportPageText.tabs.pdf));
    fireEvent.click(await screen.findByText("PDF İndir"));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("closes ExportDialog when Vazgeç is clicked", async () => {
    render(<ReportsPage />);
    fireEvent.click(screen.getByText(reportPageText.tabs.pdf));
    fireEvent.click(await screen.findByText("PDF İndir"));
    await waitFor(() => screen.getByRole("dialog"));
    fireEvent.click(screen.getByText("Vazgeç"));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
