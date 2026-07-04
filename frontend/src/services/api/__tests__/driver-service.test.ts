/**
 * T8-A: driverService.updateScore response type — real backend conversion.
 *
 * The original file (`services/api/driver-service.ts` does not exist —
 * this suite actually documents an intent, not a real module) was 100%
 * commented-out placeholder assertions. The real update-score API lives in
 * `api/drivers.ts` (driverService.updateScore, backed by the orval-generated
 * `updateDriverScoreApiV1DriversSoforIdScorePost`). Verified against the
 * live backend (POST /api/v1/drivers/{id}/score?score=0.95) that the T8-A
 * bug this file used to merely describe is already fixed: the endpoint
 * returns a full SoforResponse/Driver object (id, score, ad_soyad, ...),
 * not the legacy {success, new_score} shape.
 */
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)(
  "driverService.updateScore — T8-A response type (real backend)",
  () => {
    let driverService: typeof import("../../../api/drivers").driverService;
    let driverId: number;

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
      const token = await loginAsAdmin();
      sessionStorage.setItem("access_token", token);
      ({ driverService } = await import("../../../api/drivers"));

      const runTag = Date.now();
      driverId = (
        await driverService.create({
          ad_soyad: `Faz2ScoreDriver${runTag}`,
          ehliyet_sinifi: "E",
        } as any)
      ).id as number;
    });

    afterAll(async () => {
      if (driverId) {
        await driverService.delete(driverId).catch(() => undefined);
        await driverService.delete(driverId).catch(() => undefined);
      }
      vi.unstubAllEnvs();
    });

    it("updateScore returns a full Driver object with the updated score, not {success, new_score}", async () => {
      const result = await driverService.updateScore(driverId, 0.95);

      expect(result).toHaveProperty("id", driverId);
      expect(result).toHaveProperty("score", 0.95);
      expect(result).not.toHaveProperty("new_score");
      expect(result).not.toHaveProperty("success");
      expect(typeof (result as any).ad_soyad).toBe("string");
    }, 15000);
  },
);
