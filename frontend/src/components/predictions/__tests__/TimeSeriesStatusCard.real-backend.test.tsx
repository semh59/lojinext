/**
 * 0-mock epiği: TimeSeriesStatusCard.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı bir senaryo. Test DB'sinde deep-learning
 * modeli eğitilmediği için `/predictions/time-series/status` gerçekten
 * `is_trained: false` döner (curl ile doğrulandı) — bileşen bunu
 * `available` alanı yokmuş gibi yorumlayıp "Yeterli veri yok" gösterir.
 * "Hazır" (available=true) senaryosu eğitilmiş model gerektirdiğinden
 * mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TimeSeriesStatusCard (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let TimeSeriesStatusCard: typeof import("../TimeSeriesStatusCard").TimeSeriesStatusCard;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ TimeSeriesStatusCard } = await import("../TimeSeriesStatusCard"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den eğitilmemiş model durumunu gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<TimeSeriesStatusCard />);

    await waitFor(
      () => expect(screen.getByText("Yeterli veri yok")).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
