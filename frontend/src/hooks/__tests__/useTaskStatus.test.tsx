import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "../../test/test-utils";

vi.mock("../../api/trips", () => ({
  tripService: {
    getTaskStatus: vi.fn(),
  },
}));

import { tripService } from "../../api/trips";
import { useTaskStatus } from "../useTaskStatus";

describe("useTaskStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("taskId yoksa IDLE", () => {
    const { result } = renderHook(() => useTaskStatus(null));
    expect(result.current.status).toBe("IDLE");
    expect(tripService.getTaskStatus).not.toHaveBeenCalled();
  });

  it("SUCCESS sonrası isTerminal=true ve result döner", async () => {
    (tripService.getTaskStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
      task_id: "t1",
      status: "SUCCESS",
      result: { total_cost: 5000 },
    });
    const { result } = renderHook(() => useTaskStatus("t1"));
    await waitFor(() => expect(result.current.status).toBe("SUCCESS"));
    expect(result.current.isTerminal).toBe(true);
    expect((result.current.result as { total_cost: number }).total_cost).toBe(
      5000,
    );
  });

  it("FAILED isTerminal=true, error mesajı görünür", async () => {
    (tripService.getTaskStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
      task_id: "t2",
      status: "FAILED",
      error: "boom",
    });
    const { result } = renderHook(() => useTaskStatus("t2"));
    await waitFor(() => expect(result.current.status).toBe("FAILED"));
    expect(result.current.isTerminal).toBe(true);
    expect(result.current.error).toBe("boom");
  });
});
