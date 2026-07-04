/**
 * 0-mock epiği: FuelAnomalyWidget.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı seed gerektirmeyen bir senaryo. Test DB'sinde henüz
 * anomali kaydı olmadığı için `GET /api/v1/anomalies/?tip=tuketim&days=30&limit=5`
 * `{status:"success", data:{anomalies:[], total:0, ...}}` döner (curl ile
 * doğrulandı) — bu da bileşenin "anomali yok" pozitif mesajını gösterdiği
 * yolu gerçek HTTP round-trip'iyle egzersiz eder.
 *
 * Anomali-listesi render senaryosu ve "Tüm Anomaliler" linki, gerçek anomali
 * kaydı seed etmeyi (anomaly detection pipeline'ını tetiklemek) gerektirdiğinden
 * (bu efor dışında) mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("FuelAnomalyWidget (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let FuelAnomalyWidget: typeof import("../FuelAnomalyWidget").FuelAnomalyWidget;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ FuelAnomalyWidget } = await import("../FuelAnomalyWidget"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş test DB'sinde gerçek backend'den anomali-yok mesajı gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<FuelAnomalyWidget />);

    await waitFor(
      () =>
        expect(
          screen.getByText("Son 30 günde yakıt anomalisi tespit edilmedi"),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
