/**
 * 0-mock epiği — son parti. predictionService.getEnsembleStatus gerçek
 * backend'e karşı.
 */
import { describe, it, expect, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)(
  "predictionService.getEnsembleStatus (real backend)",
  () => {
    let predictionService: typeof import("../../../api/predictions").predictionService;

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
      const token = await loginAsAdmin();
      sessionStorage.setItem("access_token", token);
      ({ predictionService } = await import("../../../api/predictions"));
    });

    afterAll(() => {
      vi.unstubAllEnvs();
    });

    it("calls /predictions/ensemble/status and returns real cold-start weights", async () => {
      const result = await predictionService.getEnsembleStatus();

      expect(result).toHaveProperty("models");
      expect(result).toHaveProperty("weights");
      // Physics is the dominant cold-start weight per ensemble_predictor.py
      // DEFAULT_WEIGHTS (physics=0.80) — real value, not a mock stand-in.
      expect(result.weights.physics).toBe(0.8);
      expect(typeof result.total_models).toBe("number");
    }, 15000);
  },
);
