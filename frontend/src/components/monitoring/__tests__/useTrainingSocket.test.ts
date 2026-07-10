import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTrainingSocket } from "../useTrainingSocket";
import { tokenStorage } from "../../../services/api/auth-service";

// Regression test for a real bug: the hook expected
// {type: "training_progress", data: {model_id, epoch, total_epochs, loss,
// status: "running"|"completed"|"failed"}} — a shape the backend never
// sends. training_ws_manager.broadcast() (app/api/v1/endpoints/admin_ws.py)
// does a plain json.dumps() of whatever ml_service.py's update_progress()
// constructs: a FLAT {type: "progress", task_id, arac_id, ilerleme, durum,
// error, detail}. Since msg.type never matched, setProgress() was never
// called and the live training panel never rendered anything.

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  readyState = MockWebSocket.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }
  simulateMessage(data: unknown) {
    this.onmessage?.(
      new MessageEvent("message", { data: JSON.stringify(data) }),
    );
  }
}

let mockWs: MockWebSocket;

vi.stubGlobal(
  "WebSocket",
  vi.fn(() => {
    mockWs = new MockWebSocket();
    return mockWs;
  }),
);

vi.mock("../../../services/api/auth-service", () => ({
  tokenStorage: { get: vi.fn().mockReturnValue("test-jwt-token") },
}));

describe("useTrainingSocket", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.mocked(tokenStorage.get).mockReturnValue("test-jwt-token");
  });

  it("sets progress from the real backend wire shape (flat, type: 'progress')", () => {
    const { result } = renderHook(() => useTrainingSocket());
    act(() => mockWs.simulateOpen());
    act(() =>
      mockWs.simulateMessage({
        type: "progress",
        task_id: 42,
        arac_id: 7,
        ilerleme: 63.5,
        durum: "RUNNING",
        error: false,
        detail: null,
      }),
    );

    expect(result.current.progress).toEqual({
      type: "progress",
      task_id: 42,
      arac_id: 7,
      ilerleme: 63.5,
      durum: "RUNNING",
      error: false,
      detail: null,
    });
    expect(result.current.wsStatus).toBe("training");
  });

  it("ignores the old imagined shape (nested data, training_progress type) — proves the old contract never worked", () => {
    const { result } = renderHook(() => useTrainingSocket());
    act(() => mockWs.simulateOpen());
    act(() =>
      mockWs.simulateMessage({
        type: "training_progress",
        data: {
          model_id: "abc",
          epoch: 3,
          total_epochs: 10,
          loss: 0.5,
          status: "running",
        },
      }),
    );

    expect(result.current.progress).toBeNull();
  });

  it("goes back to idle once durum is no longer RUNNING", () => {
    const { result } = renderHook(() => useTrainingSocket());
    act(() => mockWs.simulateOpen());
    act(() =>
      mockWs.simulateMessage({
        type: "progress",
        task_id: 42,
        arac_id: 7,
        ilerleme: 100,
        durum: "COMPLETED",
        error: false,
        detail: null,
      }),
    );

    expect(result.current.wsStatus).toBe("idle");
  });

  it("logs the error detail when a training task fails", () => {
    const { result } = renderHook(() => useTrainingSocket());
    act(() => mockWs.simulateOpen());
    act(() =>
      mockWs.simulateMessage({
        type: "progress",
        task_id: 42,
        arac_id: 7,
        ilerleme: 40,
        durum: "FAILED",
        error: true,
        detail: "CUDA out of memory",
      }),
    );

    expect(result.current.logs).toContain("CUDA out of memory");
  });
});
