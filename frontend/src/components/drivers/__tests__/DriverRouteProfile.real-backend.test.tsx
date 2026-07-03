/**
 * 0-mock epiği Faz 2: DriverRouteProfile.test.tsx'in mock'lu 3 senaryosuna
 * ek olarak, gerçek backend'e karşı "istek başarısız" senaryosu (var
 * olmayan sofor_id → gerçek 404, seed gerektirmez). Ayrı dosyada tutuluyor
 * çünkü aynı dosyada hem `vi.mock` (dosya-seviyesi, hoisted) hem gerçek
 * modül import'u tutmak modül-cache çakışmasına yol açıyordu.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("DriverRouteProfile (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let DriverRouteProfile: typeof import("../DriverRouteProfile").DriverRouteProfile;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ DriverRouteProfile } = await import("../DriverRouteProfile"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("istek başarısız (gerçek 404, var olmayan sofor_id) → hata mesajı", async () => {
    // AuthProvider'ın initAuth() /auth/me denemesi (ayrı, ilgisiz bir
    // URL-konvansiyon sorunu) başarısız olup token'ı temizleyebilir —
    // render'dan hemen ÖNCE yeniden enjekte ediyoruz (bkz
    // LocationFormModal.test.tsx'teki aynı gotcha).
    sessionStorage.setItem("access_token", authToken);
    render(<DriverRouteProfile driverId={999999} />);
    await waitFor(
      () =>
        expect(
          screen.getByText("Güzergah profili alınamadı"),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
