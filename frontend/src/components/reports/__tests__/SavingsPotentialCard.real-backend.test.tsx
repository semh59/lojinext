/**
 * 0-mock epiği: SavingsPotentialCard.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı bir senaryo. Test DB'sinde kaynak-destekli
 * maliyet verisi olmadığından gerçek
 * `GET /advanced-reports/cost/savings-potential` 409 döner (curl ile
 * doğrulandı) — bu, bileşenin "409 conflict → yetersiz veri uyarısı"
 * dalını gerçek HTTP round-trip'iyle egzersiz eder (aynı senaryo, önceden
 * mock'ta elle enjekte ediliyordu). Slider/başarılı-veri senaryoları seed
 * gerektirdiğinden mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("SavingsPotentialCard (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let SavingsPotentialCard: typeof import("../SavingsPotentialCard").SavingsPotentialCard;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ SavingsPotentialCard } = await import("../SavingsPotentialCard"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den 409 döner ve yetersiz veri uyarısı gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<SavingsPotentialCard />);

    await waitFor(
      () =>
        expect(
          screen.getByText(/Gerçek maliyet verisi henüz yeterli değil/),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
