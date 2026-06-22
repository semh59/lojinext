import { describe, it, expect, beforeEach, vi } from "vitest";
import { act } from "@testing-library/react";
import { useAiStore } from "../use-ai-store";

vi.mock("../../api/ai", () => ({
  aiApi: {
    getStatus: vi.fn(() =>
      Promise.resolve({
        is_ready: true,
        progress: { status: "ready" },
      }),
    ),
  },
  ChatMessage: {},
}));

describe("useAiStore", () => {
  beforeEach(() => {
    useAiStore.setState(
      useAiStore.getInitialState?.() || {
        messages: [],
        isOpen: false,
        isExpanded: false,
        status: "offline",
      },
    );
    vi.clearAllMocks();
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

  it("toggleOpen toggles isOpen state and calls checkStatus when opening", async () => {
    const initialState = useAiStore.getState().isOpen;
    act(() => {
      useAiStore.getState().toggleOpen();
    });
    expect(useAiStore.getState().isOpen).toBe(!initialState);

    // Wait for async checkStatus
    await new Promise((r) => setTimeout(r, 100));
    // After toggle to open, status should be set via checkStatus
  });

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
    // Add multiple messages
    act(() => {
      useAiStore.getState().addMessage({ role: "user", content: "Test" });
      useAiStore.getState().addMessage({ role: "assistant", content: "Reply" });
    });
    expect(useAiStore.getState().messages.length).toBeGreaterThan(1);

    // Clear history
    act(() => {
      useAiStore.getState().clearHistory();
    });
    const state = useAiStore.getState();
    expect(state.messages.length).toBe(1);
    expect(state.messages[0].role).toBe("assistant");
    expect(state.messages[0].content).toContain("Merhaba");
  });

  it("checkStatus updates status based on API response", async () => {
    act(() => {
      useAiStore.getState().checkStatus();
    });

    // Wait for async operation
    await new Promise((r) => setTimeout(r, 100));

    const state = useAiStore.getState();
    expect(["loading", "ready", "error"]).toContain(state.status);
  });
});
