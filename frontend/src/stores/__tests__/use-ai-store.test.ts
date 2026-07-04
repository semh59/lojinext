import {
  describe,
  it,
  expect,
  beforeEach,
  beforeAll,
  afterAll,
  vi,
} from "vitest";
import { act } from "@testing-library/react";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

// checkStatus is the one action in this store that makes a REAL HTTP call
// (GET /ai/status) — everything else is pure Zustand state, no mocking
// needed either way. Per this epic's established pattern, we point the
// whole store at the real backend rather than mocking `aiApi` module.
describe.skipIf(!backendUp)("useAiStore (real backend)", () => {
  let useAiStore: typeof import("../use-ai-store").useAiStore;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ useAiStore } = await import("../use-ai-store"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  beforeEach(() => {
    useAiStore.setState(
      useAiStore.getInitialState?.() || {
        messages: [],
        isOpen: false,
        isExpanded: false,
        status: "offline",
      },
    );
  });

  it("initializes with default state", () => {
    const state = useAiStore.getState();
    expect(state.isOpen).toBe(false);
    expect(state.isExpanded).toBe(false);
    expect(state.status).toBe("offline");
    expect(state.messages.length).toBeGreaterThan(0);
    expect(state.messages[0].role).toBe("assistant");
  });

  it("addMessage appends message to history", () => {
    const newMessage = { role: "user" as const, content: "Merhaba" };
    act(() => {
      useAiStore.getState().addMessage(newMessage);
    });
    const state = useAiStore.getState();
    expect(state.messages).toContainEqual(newMessage);
    expect(state.messages[state.messages.length - 1]).toEqual(newMessage);
  });

  it("setIsOpen updates isOpen state", () => {
    act(() => {
      useAiStore.getState().setIsOpen(true);
    });
    expect(useAiStore.getState().isOpen).toBe(true);

    act(() => {
      useAiStore.getState().setIsOpen(false);
    });
    expect(useAiStore.getState().isOpen).toBe(false);
  });

  it("toggleOpen toggles isOpen state and calls real checkStatus when opening", async () => {
    const initialState = useAiStore.getState().isOpen;
    act(() => {
      useAiStore.getState().toggleOpen();
    });
    expect(useAiStore.getState().isOpen).toBe(!initialState);

    await vi.waitUntil(() => useAiStore.getState().status !== "offline", {
      timeout: 10000,
      interval: 100,
    });

    const status = useAiStore.getState().status;
    expect(["loading", "ready", "error"]).toContain(status);
  }, 15000);

  it("setIsExpanded updates isExpanded state", () => {
    act(() => {
      useAiStore.getState().setIsExpanded(true);
    });
    expect(useAiStore.getState().isExpanded).toBe(true);

    act(() => {
      useAiStore.getState().setIsExpanded(false);
    });
    expect(useAiStore.getState().isExpanded).toBe(false);
  });

  it("toggleExpanded toggles isExpanded state", () => {
    const initial = useAiStore.getState().isExpanded;
    act(() => {
      useAiStore.getState().toggleExpanded();
    });
    expect(useAiStore.getState().isExpanded).toBe(!initial);
  });

  it("clearHistory resets messages to initial greeting", () => {
    act(() => {
      useAiStore.getState().addMessage({ role: "user", content: "Test" });
      useAiStore.getState().addMessage({ role: "assistant", content: "Reply" });
    });
    expect(useAiStore.getState().messages.length).toBeGreaterThan(1);

    act(() => {
      useAiStore.getState().clearHistory();
    });
    const state = useAiStore.getState();
    expect(state.messages.length).toBe(1);
    expect(state.messages[0].role).toBe("assistant");
    expect(state.messages[0].content).toContain("Merhaba");
  });

  it("checkStatus updates status based on the real /ai/status response", async () => {
    act(() => {
      useAiStore.getState().checkStatus();
    });

    await vi.waitUntil(() => useAiStore.getState().status !== "offline", {
      timeout: 10000,
      interval: 100,
    });

    const state = useAiStore.getState();
    expect(["loading", "ready", "error"]).toContain(state.status);
  }, 15000);
});
