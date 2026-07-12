/**
 * Regression: the SSE error stream's URL embeds a one-time, 90s-TTL token
 * (deleted server-side on first read — see app/api/v1/endpoints/
 * error_stream.py's `redis.delete(key)`). useEventSource's built-in
 * reconnect-on-error just retries the SAME url, so once the token is
 * consumed every subsequent automatic reconnect attempt 401s forever —
 * confirmed live via network logs (5 requests, identical token, 403 then
 * 4x401). The old code's mount-only useEffect comment even said "reconnect
 * handles refresh", which was never true. Fix: wire onError to fetch a
 * fresh token (with capped exponential backoff — see second test) and
 * update sseUrl, so automatic reconnect actually works.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "../../../test/test-utils";

vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

vi.mock("../../../api/admin", () => ({
  adminHealthApi: {
    getHealth: vi.fn().mockResolvedValue({
      status: "healthy",
      components: {},
      circuit_breakers: [],
    }),
    resetCircuitBreaker: vi.fn(),
    triggerBackup: vi.fn(),
  },
}));

vi.mock("../../../services/api/error-service", () => ({
  errorService: {
    getSseToken: vi.fn(),
    getEvents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    getStats: vi.fn().mockResolvedValue({ stats: [] }),
    resolveEvent: vi.fn(),
  },
}));

let capturedOnError: (() => void) | undefined;
vi.mock("../../../hooks/use-event-source", () => ({
  useEventSource: (_url: string, options: { onError?: () => void }) => {
    capturedOnError = options.onError;
    return { status: "error", close: vi.fn() };
  },
}));

import { errorService } from "../../../services/api/error-service";
import SistemSaglikPage from "../SistemSaglikPage";

describe("SistemSaglikPage — SSE token refresh on reconnect", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    capturedOnError = undefined;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches a fresh SSE token when useEventSource reports an error, instead of only relying on manual Reconnect", async () => {
    (errorService.getSseToken as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(
        "http://localhost/api/v1/system/error-stream?token=first",
      )
      .mockResolvedValueOnce(
        "http://localhost/api/v1/system/error-stream?token=second",
      );

    render(<SistemSaglikPage />);
    fireEvent.click(screen.getByText("Hata Analizi"));

    await vi.waitFor(() =>
      expect(errorService.getSseToken).toHaveBeenCalledTimes(1),
    );
    expect(capturedOnError).toBeTypeOf("function");

    capturedOnError!();
    await vi.advanceTimersByTimeAsync(1000); // first backoff delay

    await vi.waitFor(() =>
      expect(errorService.getSseToken).toHaveBeenCalledTimes(2),
    );
  });

  it("stops auto-retrying after 5 attempts instead of hammering the backend forever", async () => {
    // Regression: a naive onError->refetch->reconnect loop with no cap
    // turned a permanently-failing connection (e.g. break-glass admin
    // whose id never resolves server-side) into an infinite tight retry
    // loop — 500+ requests observed live in a few seconds.
    (errorService.getSseToken as ReturnType<typeof vi.fn>).mockResolvedValue(
      "http://localhost/api/v1/system/error-stream?token=always-fails",
    );

    render(<SistemSaglikPage />);
    fireEvent.click(screen.getByText("Hata Analizi"));

    await vi.waitFor(() =>
      expect(errorService.getSseToken).toHaveBeenCalledTimes(1),
    );

    // Simulate 5 more consecutive connection errors, each triggering the
    // capped-backoff retry (delays: 1s, 2s, 4s, 8s, 16s).
    for (let i = 0; i < 5; i++) {
      capturedOnError!();
      await vi.advanceTimersByTimeAsync(30_000);
    }

    // 1 initial + 5 auto-retries = 6 total. A 6th error must NOT trigger
    // a 7th fetch — the cap has been reached.
    await vi.waitFor(() =>
      expect(errorService.getSseToken).toHaveBeenCalledTimes(6),
    );
    capturedOnError!();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(errorService.getSseToken).toHaveBeenCalledTimes(6);
  });
});
