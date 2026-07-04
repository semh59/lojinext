/**
 * 0-mock epiği — son parti. sendFeedback gerçek backend'e karşı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("feedback-service (real backend)", () => {
  let sendFeedback: typeof import("../../../api/feedback").sendFeedback;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ sendFeedback } = await import("../../../api/feedback"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("POSTs feedback to the real /feedback/ endpoint and resolves", async () => {
    await expect(
      sendFeedback({ message: "Faz2 real-backend test", page: "/fuel" }),
    ).resolves.toBeUndefined();
  }, 15000);
});
