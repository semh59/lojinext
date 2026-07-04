/**
 * 0-mock epiği: CostTrendChart.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı seed gerektirmeyen bir senaryo. Test DB'sinde henüz
 * yakıt alımı/sefer kaydı olmadığı için `GET /api/v1/advanced-reports/cost/trend`
 * boş dizi döner (curl ile doğrulandı) — bu da bileşenin "boş veri" mesajını
 * gösterdiği yolu gerçek HTTP round-trip'iyle egzersiz eder.
 *
 * "veri varken" senaryosu, aylara yayılan gerçek yakıt/sefer verisi seed
 * etmeyi gerektirdiğinden (bu efor dışında) mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("CostTrendChart (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let CostTrendChart: typeof import("../CostTrendChart").CostTrendChart;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ CostTrendChart } = await import("../CostTrendChart"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş test DB'sinde gerçek backend'den boş veri mesajı gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<CostTrendChart />);

    await waitFor(
      () =>
        expect(
          screen.getByText("Bu dönem için gösterilecek maliyet verisi yok"),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
