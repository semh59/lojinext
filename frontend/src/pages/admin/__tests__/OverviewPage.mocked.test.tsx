import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "../../../test/test-utils";
import AdminOverviewPage from "../OverviewPage";
import { adminOverviewText } from "../../../resources/tr/admin";

// Scenarios kept mocked because they require states not reproducible
// against the shared real test backend (unhealthy system status, a
// populated consumption trend chart) — see OverviewPage.test.tsx for the
// real-backend cold-start coverage of this page.

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

describe("AdminOverviewPage (mocked scenarios)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await setupMocks();
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

  it("renders chart container when trend data present", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(screen.getByTestId("line-chart-container")).toBeInTheDocument();
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
});
