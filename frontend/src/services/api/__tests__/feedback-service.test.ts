import { describe, expect, it, vi, beforeEach } from "vitest";

const mockCustomAxios = vi.fn();
vi.mock("../../../lib/orval-mutator", () => ({
  customAxiosInstance: mockCustomAxios,
}));

describe("feedback-service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("POSTs feedback to /feedback/", async () => {
    mockCustomAxios.mockResolvedValueOnce(undefined);
    const { sendFeedback } = await import("../../../api/feedback");
    await sendFeedback({ message: "test", page: "/fuel" });
    expect(mockCustomAxios.mock.lastCall?.[0]).toMatchObject({
      url: "/api/v1/feedback/",
      method: "POST",
      data: { message: "test", page: "/fuel" },
    });
  });
});
