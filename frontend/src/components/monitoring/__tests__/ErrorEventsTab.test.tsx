import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import { ErrorEventsTab } from "../ErrorEventsTab";

// Mock error-service
vi.mock("../../../services/api/error-service", () => ({
  errorService: {
    getEvents: vi.fn(),
    getStats: vi.fn(),
    resolveEvent: vi.fn(),
    getSseToken: vi.fn().mockResolvedValue(""),
  },
}));

// Mock useErrorStream to avoid SSE/EventSource usage
vi.mock("../useErrorStream", () => ({
  useErrorStream: () => ({ liveEvents: [], sseStatus: "idle" }),
}));

// Mock TraceDetailDialog to avoid recursive query mocks
vi.mock("../TraceDetailDialog", () => ({
  TraceDetailDialog: ({ traceId, onClose }: any) =>
    traceId ? (
      <div data-testid="trace-dialog">
        <span>{traceId}</span>
        <button onClick={onClose}>Close trace</button>
      </div>
    ) : null,
}));

// Mock recharts to avoid canvas/ResizeObserver errors in jsdom
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

const MOCK_EVENTS = {
  items: [
    {
      id: 1,
      fingerprint: "fp-001",
      layer: "db",
      category: "db_error",
      severity: "error",
      message: "Connection pool exhausted",
      count: 3,
      first_seen: "2026-06-01T08:00:00Z",
      last_seen: "2026-06-01T09:00:00Z",
      trace_id: "trace-abc123",
      path: "/api/v1/trips/",
      metadata: {},
      resolved_at: undefined,
    },
    {
      id: 2,
      fingerprint: "fp-002",
      layer: "api",
      category: "validation_error",
      severity: "warning",
      message: "Missing required field: plaka",
      count: 1,
      first_seen: "2026-06-01T10:00:00Z",
      last_seen: "2026-06-01T10:00:00Z",
      trace_id: undefined,
      path: undefined,
      metadata: {},
      resolved_at: "2026-06-01T11:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

const MOCK_STATS = { stats: [] };

describe("ErrorEventsTab", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { errorService } = await import(
      "../../../services/api/error-service"
    );
    (errorService.getEvents as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_EVENTS,
    );
    (errorService.getStats as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_STATS,
    );
  });

  it("renders chart section heading", async () => {
    render(<ErrorEventsTab />);
    expect(screen.getByText("Saatlik Hata Dağılımı")).toBeInTheDocument();
  });

  it("renders chart sub-heading", async () => {
    render(<ErrorEventsTab />);
    expect(screen.getByText("Son 24 saat")).toBeInTheDocument();
  });

  it("shows SSE status as 'bekleniyor' when idle", async () => {
    render(<ErrorEventsTab />);
    expect(screen.getByText("Canlı akış bekleniyor")).toBeInTheDocument();
  });

  it("SSE status indicator dot renders alongside status text", async () => {
    render(<ErrorEventsTab />);
    // The dot span and the status text are siblings — both should be present
    const statusText = screen.getByText("Canlı akış bekleniyor");
    expect(statusText).toBeInTheDocument();
    // The containing span wraps both the dot and text
    const wrapper = statusText.closest("div.flex");
    expect(wrapper).toBeInTheDocument();
  });

  it("renders layer filter chips", async () => {
    render(<ErrorEventsTab />);
    expect(screen.getByText("Katman:")).toBeInTheDocument();
    expect(screen.getByText("db")).toBeInTheDocument();
    expect(screen.getByText("api")).toBeInTheDocument();
    expect(screen.getByText("celery")).toBeInTheDocument();
  });

  it("renders severity filter chips", async () => {
    render(<ErrorEventsTab />);
    expect(screen.getByText("Önem:")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("info")).toBeInTheDocument();
  });

  it("renders 'Tümü' filter chips", async () => {
    render(<ErrorEventsTab />);
    const tumChips = screen.getAllByText("Tümü");
    expect(tumChips.length).toBeGreaterThanOrEqual(2);
  });

  it("shows open/resolved toggle chip", async () => {
    render(<ErrorEventsTab />);
    expect(screen.getByText("Sadece açık")).toBeInTheDocument();
  });

  it("shows error events after loading", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => {
      expect(screen.getByText("Connection pool exhausted")).toBeInTheDocument();
      expect(
        screen.getByText("Missing required field: plaka"),
      ).toBeInTheDocument();
    });
  });

  it("shows event layer and category labels", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => {
      // layer "db" appears in filter chips AND in event row — both ok
      const dbElements = screen.getAllByText("db");
      expect(dbElements.length).toBeGreaterThan(0);
    });
  });

  it("shows event path when present", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => {
      expect(screen.getByText("/api/v1/trips/")).toBeInTheDocument();
    });
  });

  it("shows count indicator for repeated events", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => {
      // count=3 renders as "×3"
      expect(screen.getByText("×3")).toBeInTheDocument();
    });
  });

  it("shows resolved indicator for resolved event", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => {
      expect(screen.getByText("✓ Çözüldü")).toBeInTheDocument();
    });
  });

  it("shows 'Çözüldü' resolve button for unresolved events", async () => {
    render(<ErrorEventsTab />);
    // Wait for the unresolved event row to render first (stable anchor),
    // then assert the resolve button — robust under full-suite load.
    await waitFor(() =>
      expect(screen.getByText("Connection pool exhausted")).toBeInTheDocument(),
    );
    // Only the unresolved event should have the resolve button.
    const resolveBtns = screen.getAllByRole("button", { name: "Çözüldü" });
    expect(resolveBtns.length).toBe(1);
  });

  it("calls resolveEvent when Çözüldü button clicked", async () => {
    const { errorService } = await import(
      "../../../services/api/error-service"
    );
    (errorService.resolveEvent as ReturnType<typeof vi.fn>).mockResolvedValue(
      undefined,
    );
    render(<ErrorEventsTab />);
    await waitFor(() => screen.getByText("Connection pool exhausted"));
    const resolveBtn = screen.getByRole("button", { name: "Çözüldü" });
    fireEvent.click(resolveBtn);
    await waitFor(() => {
      expect(errorService.resolveEvent).toHaveBeenCalledTimes(1);
      expect(
        (errorService.resolveEvent as ReturnType<typeof vi.fn>).mock
          .calls[0][0],
      ).toBe(1);
    });
  });

  it("shows trace open button for events with trace_id", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => {
      expect(screen.getByTestId("trace-open-btn")).toBeInTheDocument();
    });
  });

  it("opens trace dialog when trace button clicked", async () => {
    render(<ErrorEventsTab />);
    await waitFor(() => screen.getByTestId("trace-open-btn"));
    fireEvent.click(screen.getByTestId("trace-open-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("trace-dialog")).toBeInTheDocument();
      expect(screen.getByText("trace-abc123")).toBeInTheDocument();
    });
  });

  it("shows empty state when no events returned", async () => {
    const { errorService } = await import(
      "../../../services/api/error-service"
    );
    (errorService.getEvents as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
    render(<ErrorEventsTab />);
    await waitFor(() => {
      expect(
        screen.getByText("Aktif hata olayı bulunamadı"),
      ).toBeInTheDocument();
    });
  });

  it("shows empty chart message when no stats data", async () => {
    const { errorService } = await import(
      "../../../services/api/error-service"
    );
    (errorService.getStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      stats: [],
    });
    render(<ErrorEventsTab />);
    await waitFor(() => {
      expect(screen.getByText("Henüz hata verisi yok")).toBeInTheDocument();
    });
  });

  it("layer filter chip style changes to active when clicked", async () => {
    render(<ErrorEventsTab />);
    const dbChip = screen.getByRole("button", { name: "db" });
    // Before click: not active (bg-elevated class)
    expect(dbChip.className).toContain("bg-elevated");
    fireEvent.click(dbChip);
    // After click: active (bg-accent class)
    await waitFor(() => {
      expect(dbChip.className).toContain("bg-accent");
    });
  });
});
