import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";
import AdminOverviewPage from "../OverviewPage";
import { adminOverviewText } from "../../../resources/tr/admin";

// recharts stub
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="line-chart-container">{children}</div>
  ),
  LineChart: ({ children }: any) => <svg>{children}</svg>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));

// usePageTitle
vi.mock("../../../hooks/usePageTitle", () => ({ usePageTitle: vi.fn() }));

// TelegramOnayPanel — isolated, heavy dependency
vi.mock("../../../components/admin/TelegramOnayPanel", () => ({
  TelegramOnayPanel: () => (
    <div data-testid="telegram-onay-panel">TelegramOnayPanel</div>
  ),
}));

// Card — passthrough
vi.mock("../../../components/ui/Card", () => ({
  Card: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
}));

// reportService
vi.mock("../../../api/reports", () => ({
  reportService: {
    getDashboardStats: vi.fn(),
    getConsumptionTrend: vi.fn(),
  },
}));

// adminHealthApi
vi.mock("../../../api/admin", () => ({
  adminHealthApi: {
    getHealth: vi.fn(),
  },
  adminUsersApi: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  adminRolesApi: { getAll: vi.fn() },
}));

const MOCK_DASHBOARD = {
  toplam_sefer: 42,
  aktif_arac: 7,
  toplam_arac: 10,
};

const MOCK_HEALTH = {
  status: "healthy",
  components: {
    database: { status: "healthy" },
    cache: { status: "healthy" },
  },
  circuit_breakers: [],
  backups: {
    status: "success",
    last_backup: "2026-06-01T02:00:00Z",
  },
};

const MOCK_TREND = [
  { month: "Oca", consumption: 5000 },
  { month: "Şub", consumption: 5200 },
];

async function setupMocks(
  dashboard = MOCK_DASHBOARD,
  health = MOCK_HEALTH,
  trend = MOCK_TREND,
) {
  const { reportService } = await import("../../../api/reports");
  const { adminHealthApi } = await import("../../../api/admin");
  (
    reportService.getDashboardStats as ReturnType<typeof vi.fn>
  ).mockResolvedValue(dashboard);
  (
    reportService.getConsumptionTrend as ReturnType<typeof vi.fn>
  ).mockResolvedValue(trend);
  (adminHealthApi.getHealth as ReturnType<typeof vi.fn>).mockResolvedValue(
    health,
  );
}

describe("AdminOverviewPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await setupMocks();
  });

  it("renders the main heading", () => {
    render(<AdminOverviewPage />);
    expect(screen.getByText(adminOverviewText.heading)).toBeInTheDocument();
  });

  it("renders the description subtitle", () => {
    render(<AdminOverviewPage />);
    expect(screen.getByText(adminOverviewText.description)).toBeInTheDocument();
  });

  it("renders Toplam Sefer KPI card label", () => {
    render(<AdminOverviewPage />);
    expect(
      screen.getByText(adminOverviewText.cards.totalTrips),
    ).toBeInTheDocument();
  });

  it("renders Aktif Araç KPI card label", () => {
    render(<AdminOverviewPage />);
    expect(
      screen.getByText(adminOverviewText.cards.activeVehicles),
    ).toBeInTheDocument();
  });

  it("renders Sistem Durumu card label", () => {
    render(<AdminOverviewPage />);
    expect(
      screen.getByText(adminOverviewText.cards.systemStatus),
    ).toBeInTheDocument();
  });

  it("renders Veritabanı card label", () => {
    render(<AdminOverviewPage />);
    expect(
      screen.getByText(adminOverviewText.cards.database),
    ).toBeInTheDocument();
  });

  it("shows dashboard stats after loading — toplam_sefer", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
  });

  it("shows active vehicle count after loading", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(screen.getByText("7")).toBeInTheDocument();
    });
  });

  it('shows "Sağlıklı" for healthy system status', async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      const saglikliEls = screen.getAllByText("Sağlıklı");
      expect(saglikliEls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders TelegramOnayPanel placeholder", () => {
    render(<AdminOverviewPage />);
    expect(screen.getByTestId("telegram-onay-panel")).toBeInTheDocument();
  });

  it("renders Yakıt Tüketim Trendi section title", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.consumptionTrend.title),
      ).toBeInTheDocument();
    });
  });

  it("renders Operasyonel Sağlık Özeti section title", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.operationalHealth.title),
      ).toBeInTheDocument();
    });
  });

  it("renders chart container when trend data present", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(screen.getByTestId("line-chart-container")).toBeInTheDocument();
    });
  });

  it("shows empty trend message when no data", async () => {
    const { reportService } = await import("../../../api/reports");
    (
      reportService.getConsumptionTrend as ReturnType<typeof vi.fn>
    ).mockResolvedValue([]);
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.consumptionTrend.empty),
      ).toBeInTheDocument();
    });
  });

  it("renders Devre Kesiciler label", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.operationalHealth.circuitBreakers),
      ).toBeInTheDocument();
    });
  });

  it("renders Son Yedekleme label", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.operationalHealth.lastBackup),
      ).toBeInTheDocument();
    });
  });

  it('shows "Sorunlu" for unhealthy status', async () => {
    const { adminHealthApi } = await import("../../../api/admin");
    (adminHealthApi.getHealth as ReturnType<typeof vi.fn>).mockResolvedValue({
      status: "unhealthy",
      components: { database: { status: "unhealthy" } },
      circuit_breakers: [],
      backups: { status: "error" },
    });
    render(<AdminOverviewPage />);
    await waitFor(() => {
      const sorunluEls = screen.getAllByText("Sorunlu");
      expect(sorunluEls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows zero circuit breakers when health returns empty array", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(screen.getByText("0")).toBeInTheDocument();
    });
  });
});
