/**
 * 0-mock epiği: PeriodCostBreakdown.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı bir senaryo. Test DB'sinde seçilen tarih
 * aralığında yakıt/sefer verisi olmadığından gerçek
 * `GET /advanced-reports/cost/period` sıfır değerli bir obje döner (curl ile
 * doğrulandı) — bu da bileşenin "0" değerli KPI kartlarını gerçek HTTP
 * round-trip'iyle egzersiz eder. Dolu veri senaryosu (41.67 ₺ gibi belirli
 * değerler) seed gerektirdiğinden mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("PeriodCostBreakdown (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let PeriodCostBreakdown: typeof import("../PeriodCostBreakdown").PeriodCostBreakdown;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ PeriodCostBreakdown } = await import("../PeriodCostBreakdown"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den sıfır maliyet verisi döner ve KPI kartlarını sıfır ile gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<PeriodCostBreakdown />);

    await waitFor(
      () => expect(screen.getByText("Toplam Sefer")).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText(/0 km/)).toBeInTheDocument();
  }, 15000);
});
