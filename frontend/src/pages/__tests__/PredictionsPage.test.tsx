/**
 * 0-mock epiği: PredictionsPage'in overview sekmesi predictions/ensemble-status
 * ve predictions/comparison'ı gerçek backend'e karşı çağırır. Cold-start'ta
 * ensemble durumu her zaman mevcut (model dosyaları yoksa bile physics
 * fallback döner), comparison boş sefer verisiyle 0 sayımla döner —
 * ikisi de patlamadan render olmalı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("PredictionsPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let PredictionsPage: typeof import("../PredictionsPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ default: PredictionsPage } = await import("../PredictionsPage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("renders page container and loads ensemble+comparison from real backend", async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
    render(<PredictionsPage />);

    expect(screen.getByTestId("predictions-page")).toBeTruthy();

    await waitFor(
      () => {
        expect(
          screen.getAllByText(/Model|Ensemble|Mean Absolute/i)[0],
        ).toBeTruthy();
      },
      { timeout: 15000 },
    );
  }, 20000);
});
