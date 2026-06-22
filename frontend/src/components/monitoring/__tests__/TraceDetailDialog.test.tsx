import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "../../../test/test-utils";

vi.mock("../../../services/api/error-service", () => ({
  errorService: { getTraceChain: vi.fn() },
}));

import { errorService } from "../../../services/api/error-service";
import { TraceDetailDialog } from "../TraceDetailDialog";

const sampleChain = {
  trace_id: "4e1df02e-31f5-4e03-829b-e8f02437823a",
  counts: { errors: 2, audit: 1 },
  errors: [
    {
      id: 1,
      layer: "db",
      category: "db_error",
      severity: "error",
      message: 'SQL syntax error near ":"',
      stack_trace: 'Traceback (most recent call last):\n  File "x.py"',
      path: "/api/v1/trips/",
      count: 1,
      first_seen: "2026-05-28T10:00:00Z",
      last_seen: "2026-05-28T10:00:01Z",
      resolved_at: null,
    },
    {
      id: 2,
      layer: "service",
      category: "domain_error",
      severity: "warning",
      message: "Invalid trip date",
      count: 1,
      first_seen: "2026-05-28T10:00:02Z",
      last_seen: "2026-05-28T10:00:02Z",
      resolved_at: null,
    },
  ],
  audit: [
    {
      id: 100,
      action: "CREATE",
      entity: "sefer",
      entity_id: 42,
      user_id: 7,
      status: "failure",
      duration_ms: 1234.5,
      created_at: "2026-05-28T10:00:00Z",
    },
  ],
};

describe("TraceDetailDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (!navigator.clipboard) {
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: vi.fn() },
        configurable: true,
      });
    }
  });

  it("traceId null → render etmez", () => {
    const { container } = render(
      <TraceDetailDialog traceId={null} onClose={() => {}} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("happy path: hata + audit zinciri görünür", async () => {
    (errorService.getTraceChain as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleChain,
    );

    render(
      <TraceDetailDialog
        traceId="4e1df02e-31f5-4e03-829b-e8f02437823a"
        onClose={() => {}}
      />,
    );

    // Veri yüklenmesini bekle — useQuery resolve sonrası error block'lar render
    await waitFor(() =>
      expect(screen.getByText("Invalid trip date")).toBeInTheDocument(),
    );

    // Header trace_id
    expect(
      screen.getByText(/4e1df02e-31f5-4e03-829b-e8f02437823a/),
    ).toBeInTheDocument();

    // İlk hata mesajı (SQL syntax)
    const sqlNodes = screen.queryAllByText(
      (_content, el) => el?.textContent?.includes("SQL syntax error") ?? false,
    );
    expect(sqlNodes.length).toBeGreaterThan(0);

    // Audit aksiyonu
    expect(screen.getByText("CREATE")).toBeInTheDocument();
    expect(screen.getByText(/sefer #42/)).toBeInTheDocument();

    // 2 hata + 1 audit block render edildi
    const errBlocks = screen.getAllByTestId("trace-error-block");
    expect(errBlocks).toHaveLength(2);
    const auditRows = screen.getAllByTestId("trace-audit-row");
    expect(auditRows).toHaveLength(1);
  });

  it("boş zincir → hint mesajı görünür", async () => {
    (errorService.getTraceChain as ReturnType<typeof vi.fn>).mockResolvedValue({
      trace_id: "empty-trace",
      counts: { errors: 0, audit: 0 },
      errors: [],
      audit: [],
      hint: "make trace TRACE=empty-trace ile container loglarında ara",
    });

    render(<TraceDetailDialog traceId="empty-trace" onClose={() => {}} />);

    await waitFor(() =>
      expect(screen.getByText(/make trace/)).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("trace-error-block")).not.toBeInTheDocument();
  });

  it('API hatası → "alınamadı" mesajı', async () => {
    (errorService.getTraceChain as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("boom"),
    );

    render(<TraceDetailDialog traceId="x" onClose={() => {}} />);
    await waitFor(() =>
      expect(screen.getByText(/alınamadı/i)).toBeInTheDocument(),
    );
  });

  it("Kapat butonu onClose çağırır", async () => {
    (errorService.getTraceChain as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleChain,
    );
    const onClose = vi.fn();
    render(<TraceDetailDialog traceId="x" onClose={onClose} />);
    await waitFor(() => screen.getByTestId("trace-close-btn"));
    fireEvent.click(screen.getByTestId("trace-close-btn"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Stack trace toggle expand eder", async () => {
    (errorService.getTraceChain as ReturnType<typeof vi.fn>).mockResolvedValue(
      sampleChain,
    );

    render(<TraceDetailDialog traceId="x" onClose={() => {}} />);
    await waitFor(() => screen.getByText(/SQL syntax error/));

    // Başlangıçta stack trace görünmüyor
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();

    // Toggle button
    const toggle = screen.getByText(/Stack trace/);
    fireEvent.click(toggle);

    expect(screen.getByText(/Traceback/)).toBeInTheDocument();
  });
});
