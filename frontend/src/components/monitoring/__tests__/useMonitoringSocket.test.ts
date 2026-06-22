import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useMonitoringSocket } from "../useMonitoringSocket";
import { tokenStorage } from "../../../services/api/auth-service";

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
  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
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

describe("useMonitoringSocket", () => {
  beforeEach(() => {
    vi.mocked(tokenStorage.get).mockReturnValue("test-jwt-token");
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts as connecting", () => {
    const { result } = renderHook(() => useMonitoringSocket());
    expect(result.current.status).toBe("connecting");
  });

  it("becomes connected after open", () => {
    const { result } = renderHook(() => useMonitoringSocket());
    act(() => mockWs.simulateOpen());
    expect(result.current.status).toBe("connected");
  });

  it("appends notification on message", () => {
    const { result } = renderHook(() => useMonitoringSocket());
    act(() => mockWs.simulateOpen());
    act(() =>
      mockWs.simulateMessage({
        type: "notification",
        data: {
          id: 1,
          baslik: "Test",
          icerik: "İçerik",
          olay_tipi: "fuel",
          olusturma_tarihi: "2026-05-17T10:00:00",
        },
      }),
    );
    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0].baslik).toBe("Test");
  });
});
