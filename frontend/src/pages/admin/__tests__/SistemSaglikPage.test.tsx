import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import SistemSaglikPage from "../SistemSaglikPage";
import { adminHealthText } from "../../../resources/tr/admin";

// Mock admin-service
vi.mock("../../../api/admin", () => ({
  adminHealthApi: {
    getHealth: vi.fn(),
    resetCircuitBreaker: vi.fn().mockResolvedValue({}),
    triggerBackup: vi.fn().mockResolvedValue({}),
  },
}));

// Mock error-service
vi.mock("../../../services/api/error-service", () => ({
  errorService: {
    getEvents: vi
      .fn()
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 25 }),
    getStats: vi.fn().mockResolvedValue({ stats: [] }),
    resolveEvent: vi.fn().mockResolvedValue(undefined),
    getSseToken: vi.fn().mockResolvedValue(""),
  },
}));

// Mock notification context
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

// Mock useEventSource to avoid EventSource usage in tests
vi.mock("../../../hooks/use-event-source", () => ({
  useEventSource: () => ({ status: "closed", close: vi.fn() }),
}));

// Mock usePageTitle
vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// Mock recharts to avoid canvas errors in jsdom
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

const HEALTH_DATA = {
  status: "healthy",
  components: {
    database: { status: "healthy" },
    redis: { status: "healthy" },
  },
  circuit_breakers: [
    {
      service: "mapbox",
      status: "closed",
      failure_count: 0,
      last_error: null,
    },
    {
      service: "openmeteo",
      status: "open",
      failure_count: 3,
      last_error: "Connection timeout",
    },
  ],
};

describe("SistemSaglikPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminHealthApi } = await import("../../../api/admin");
    (adminHealthApi.getHealth as ReturnType<typeof vi.fn>).mockResolvedValue(
      HEALTH_DATA,
    );
  });

  it("renders page heading and description", async () => {
    render(<SistemSaglikPage />);
    expect(screen.getByText(adminHealthText.heading)).toBeInTheDocument();
    expect(screen.getByText(adminHealthText.description)).toBeInTheDocument();
  });

  it("renders tab buttons", async () => {
    render(<SistemSaglikPage />);
    expect(screen.getByText("Sistem Durumu")).toBeInTheDocument();
    expect(screen.getByText("Hata Analizi")).toBeInTheDocument();
  });

  it("shows health cards after data loads", async () => {
    render(<SistemSaglikPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminHealthText.cards.overallStatus),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminHealthText.cards.database),
      ).toBeInTheDocument();
      expect(screen.getByText(adminHealthText.cards.cache)).toBeInTheDocument();
    });
  });

  it("shows status labels from health data", async () => {
    render(<SistemSaglikPage />);
    await waitFor(() => {
      // "Sağlıklı" should appear multiple times (overall + db + redis)
      const sağlıklıElements = screen.getAllByText("Sağlıklı");
      expect(sağlıklıElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows circuit breaker table with data", async () => {
    render(<SistemSaglikPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminHealthText.circuitBreakers.title),
      ).toBeInTheDocument();
      expect(screen.getByText("mapbox")).toBeInTheDocument();
      expect(screen.getByText("openmeteo")).toBeInTheDocument();
    });
  });

  it("shows reset button only for non-closed circuit breakers", async () => {
    render(<SistemSaglikPage />);
    await waitFor(() => {
      // openmeteo is "open" so reset should appear
      const resetBtns = screen.getAllByText(
        adminHealthText.circuitBreakers.reset,
      );
      expect(resetBtns.length).toBe(1);
    });
  });

  it("refresh button is present when on health tab", async () => {
    render(<SistemSaglikPage />);
    const refreshBtn = screen.getByText(adminHealthText.refresh);
    expect(refreshBtn).toBeInTheDocument();
  });

  it("backup button triggers mutation", async () => {
    const { adminHealthApi } = await import("../../../api/admin");
    render(<SistemSaglikPage />);
    const backupBtn = screen.getByText(adminHealthText.backup);
    fireEvent.click(backupBtn);
    await waitFor(() => {
      expect(adminHealthApi.triggerBackup).toHaveBeenCalled();
    });
  });

  it("switches to error analysis tab", async () => {
    render(<SistemSaglikPage />);
    const errTab = screen.getByText("Hata Analizi");
    fireEvent.click(errTab);
    await waitFor(() => {
      expect(screen.getByText("Hata Olayları")).toBeInTheDocument();
    });
  });

  it("shows empty state in error events table when no errors", async () => {
    render(<SistemSaglikPage />);
    fireEvent.click(screen.getByText("Hata Analizi"));
    await waitFor(() => {
      expect(
        screen.getByText("Bu filtre için hata bulunamadı"),
      ).toBeInTheDocument();
    });
  });

  it("shows error events when data is present", async () => {
    const { errorService } = await import(
      "../../../services/api/error-service"
    );
    (errorService.getEvents as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: 1,
          fingerprint: "abc",
          layer: "db",
          category: "query",
          severity: "error",
          message: "DB connection failed",
          count: 5,
          first_seen: "2026-06-01T10:00:00",
          last_seen: "2026-06-01T11:00:00",
          metadata: {},
        },
      ],
      total: 1,
      page: 1,
      page_size: 25,
    });
    render(<SistemSaglikPage />);
    fireEvent.click(screen.getByText("Hata Analizi"));
    await waitFor(() => {
      expect(screen.getByText("DB connection failed")).toBeInTheDocument();
    });
    // "db" text also appears in layer filter buttons, use getAllByText
    const dbTexts = screen.getAllByText("db");
    expect(dbTexts.length).toBeGreaterThanOrEqual(1);
  });
});
