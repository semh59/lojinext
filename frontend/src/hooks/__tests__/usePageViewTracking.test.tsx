import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

vi.mock("../../api/analytics", () => ({
  recordPageView: vi.fn().mockResolvedValue(undefined),
}));

describe("usePageViewTracking", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("records the current route on mount", async () => {
    const { recordPageView } = await import("../../api/analytics");
    const { usePageViewTracking } = await import("../usePageViewTracking");
    renderHook(() => usePageViewTracking(), {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <MemoryRouter
          initialEntries={["/trips"]}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          {children}
        </MemoryRouter>
      ),
    });
    expect(recordPageView).toHaveBeenCalledWith("/trips");
  });
});
