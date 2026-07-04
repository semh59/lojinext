/**
 * 0-mock epiği: TripsTodaySummary.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı bir senaryo. Test DB'sinde bugüne ait
 * sefer kaydı olmadığından gerçek `GET /trips/stats` `total_count: 0` döner
 * (curl ile doğrulandı) — bileşenin "boş gün" mesajını gerçek HTTP
 * round-trip'iyle egzersiz eder. Dolu-gün / iptal-chip senaryoları seed
 * gerektirdiğinden mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TripsTodaySummary (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let TripsTodaySummary: typeof import("../TripsTodaySummary").TripsTodaySummary;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ TripsTodaySummary } = await import("../TripsTodaySummary"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den bugün için 0 sefer dönünce boş gün mesajı gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<TripsTodaySummary />);

    await waitFor(
      () =>
        expect(
          screen.getByText("Bugün için kayıtlı sefer yok."),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
