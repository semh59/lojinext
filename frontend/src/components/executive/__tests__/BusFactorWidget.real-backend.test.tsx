/**
 * 0-mock epiği: BusFactorWidget.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı seed gerektirmeyen senaryo — boş DB'de
 * `GET /reports/executive/bus-factor` deterministik olarak risk_level="low"
 * + top_n_drivers=[] + top_n_drivers_loss_tl=0 döner (curl ile doğrulandı).
 *
 * "high risk" ve "PII koruması" senaryoları (seeded top-N şoför verisi)
 * gerçek şoför+sefer geçmişi seed'i gerektirir — mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("BusFactorWidget (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let BusFactorWidget: typeof import("../BusFactorWidget").BusFactorWidget;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ BusFactorWidget } = await import("../BusFactorWidget"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş filo → gerçek backend düşük risk rozeti + KVKK notu", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<BusFactorWidget />);

    await waitFor(
      () => expect(screen.getByText("Düşük Risk")).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText(/KVKK koruması/)).toBeInTheDocument();
    expect(screen.getByText("₺0")).toBeInTheDocument();
  }, 15000);
});
