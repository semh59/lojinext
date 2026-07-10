import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import SistemSaglikPage from "../SistemSaglikPage";
import { adminHealthText } from "../../../resources/tr/admin";

// Scenarios kept mocked because they require states not reproducible
// against the shared real test backend (an OPEN circuit breaker with a
// reset button, and a specific/controlled error-events payload) — see
// SistemSaglikPage.test.tsx for the real-backend coverage of this page.

vi.mock("../../../api/admin", () => ({
  adminHealthApi: {
    getHealth: vi.fn(),
    resetCircuitBreaker: vi.fn().mockResolvedValue({}),
    triggerBackup: vi.fn().mockResolvedValue({}),
  },
}));

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

vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/use-event-source", () => ({
  useEventSource: () => ({ status: "closed", close: vi.fn() }),
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

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

describe("SistemSaglikPage (mocked scenarios)", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminHealthApi } = await import("../../../api/admin");
    (adminHealthApi.getHealth as ReturnType<typeof vi.fn>).mockResolvedValue(
      HEALTH_DATA,
    );
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
      const resetBtns = screen.getAllByText(
        adminHealthText.circuitBreakers.reset,
      );
      expect(resetBtns.length).toBe(1);
    });
  });

  it("renders a half_open circuit breaker with the warning badge, not danger", async () => {
    // Regression test: backend's CircuitState.HALF_OPEN serializes as
    // "half_open" (app/infrastructure/resilience/circuit_breaker.py), but
    // the badge variant check used to compare against "half-open" (hyphen)
    // — a value the backend never sends — so every half_open breaker fell
    // through to the "danger" branch, indistinguishable from a fully open
    // one.
    const { adminHealthApi } = await import("../../../api/admin");
    (adminHealthApi.getHealth as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...HEALTH_DATA,
      circuit_breakers: [
        {
          service: "groq",
          status: "half_open",
          failure_count: 1,
          last_error: "Probe in flight",
        },
      ],
    });

    render(<SistemSaglikPage />);
    await waitFor(() => {
      const badge = screen.getByText("half_open");
      expect(badge).toBeInTheDocument();
      expect(badge.className).toContain("text-warning");
      expect(badge.className).not.toContain("text-danger");
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
    const dbTexts = screen.getAllByText("db");
    expect(dbTexts.length).toBeGreaterThanOrEqual(1);
  });
});
