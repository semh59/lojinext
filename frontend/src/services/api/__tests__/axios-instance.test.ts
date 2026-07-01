/**
 * 2026-07-01 prod-grade denetimi P2 (Dalga 4 madde 25): backend'in 429
 * rate-limit yanıtı hata zarfını (`{error:{...}}`) bypass ediyor
 * (`rate_limit_middleware.py`, `{"detail": "..."}` döner) — axios interceptor
 * bunu hiç ele almıyordu (400/403/422/5xx'in aksine), kullanıcı rate-limit'e
 * takılınca hiçbir geri bildirim almıyordu.
 */
import { AxiosError } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

vi.mock("../../error-tracker", () => ({
  errorTracker: {
    setLastTraceId: vi.fn(),
    captureApiError: vi.fn(),
    getLastTraceId: vi.fn(),
  },
}));

vi.mock("../../storage-service", () => ({
  storageService: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  },
}));

describe("axiosInstance response interceptor — 429 rate limit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a toast when the backend returns 429", async () => {
    const { toast } = await import("sonner");
    const axiosInstance = (await import("../axios-instance")).default;

    const rejectedHandler = (axiosInstance.interceptors.response as any)
      .handlers[0].rejected;

    const error = new AxiosError(
      "Request failed with status code 429",
      "ERR_BAD_REQUEST",
      { headers: {} } as any,
      {},
      {
        status: 429,
        statusText: "Too Many Requests",
        headers: { "retry-after": "60" },
        data: { detail: "Too many requests. Please try again later." },
        config: { headers: {} } as any,
      } as any,
    );

    await expect(rejectedHandler(error)).rejects.toBeTruthy();
    expect(toast.error).toHaveBeenCalled();
  });
});
