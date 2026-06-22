import { renderHook } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";

vi.mock("../../services/error-tracker", () => ({
  errorTracker: { captureMessage: vi.fn() },
}));

import { useRenderGuard } from "../use-render-guard";
import { errorTracker } from "../../services/error-tracker";

describe("useRenderGuard", () => {
  it("does not emit on normal render count", () => {
    const { rerender } = renderHook(() => useRenderGuard("TestComponent", 5));
    rerender();
    rerender();
    expect(errorTracker.captureMessage).not.toHaveBeenCalled();
  });
});
