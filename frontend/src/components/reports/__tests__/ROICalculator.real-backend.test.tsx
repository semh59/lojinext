/**
 * 0-mock epiği: ROICalculator.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı bir senaryo. Test DB'sinde kaynak-destekli
 * maliyet/sefer verisi olmadığından gerçek `/advanced-reports/cost/roi` ve
 * `/advanced-reports/cost/savings-potential` her ikisi de 409 döner (curl
 * ile doğrulandı: "Savings analysis requires source-backed trip and fuel
 * data.") — bu da bileşenin HER İKİ hata kutusunu da gerçek HTTP
 * round-trip'iyle egzersiz eder. Başarılı ROI/savings senaryoları seed
 * gerektirdiğinden mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ROICalculator (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let ROICalculator: typeof import("../ROICalculator").ROICalculator;
  let reportRoiText: typeof import("../../../resources/tr/reports").reportRoiText;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ ROICalculator } = await import("../ROICalculator"));
    ({ reportRoiText } = await import("../../../resources/tr/reports"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den 409 döner ve hem ROI hem savings hata kutularını gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<ROICalculator />);

    await waitFor(
      () => {
        expect(
          screen.getByText(reportRoiText.roiUnavailable),
        ).toBeInTheDocument();
        expect(
          screen.getByText(reportRoiText.savingsUnavailable),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    // Veri yokken metrik kutuları "-" göstermeli.
    expect(
      screen.getByText(reportRoiText.roiMetricUnavailable),
    ).toBeInTheDocument();
  }, 15000);
});
