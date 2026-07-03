/**
 * 0-mock epiği: DriverScoreBreakdown.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen 2 senaryo:
 * - taze (sıfır-sefer) bir şoför → `get_score_breakdown` deterministik
 *   olarak has_trips=false + manual==auto==total (bkz
 *   app/core/services/sofor_service.py:298) döner — "henüz yeterli sefer
 *   verisi yok" senaryosunun gerçek karşılığı.
 * - var olmayan sofor_id → gerçek 404, seed gerektirmez.
 *
 * "yeterli sefer verisi varken" senaryosu (avg_consumption=27.8, trip_count
 * =12) gerçek sefer geçmişi seed'i gerektirir — bu, Driver/Sefer domain
 * seed altyapısının kapsamı dışında; mock'lu dosyada kalıyor (bkz
 * DriverRouteProfile.real-backend.test.tsx emsali — aynı ayrım gerekçesi).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("DriverScoreBreakdown (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let DriverScoreBreakdown: typeof import("../DriverScoreBreakdown").DriverScoreBreakdown;
  let authToken: string;
  let driverId: number;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ DriverScoreBreakdown } = await import("../DriverScoreBreakdown"));

    const createResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        ad_soyad: `zm score breakdown test ${Date.now()}`,
        aktif: true,
      }),
    });
    const created = await createResp.json();
    driverId = created.id;
  });

  afterAll(async () => {
    if (driverId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/${driverId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("taze şoför için gerçek backend has_trips=false + manuel puana eşitlenme", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<DriverScoreBreakdown driverId={driverId} />);

    await waitFor(
      () => expect(screen.getByText("Toplam Hibrit Skor")).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText("Manuel Puan")).toBeInTheDocument();
    expect(screen.getByText("Otomatik Puan")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Yeterli geçmiş sefer biriktiğinde otomatik puan ayrışacak ve toplam değişebilir.",
      ),
    ).toBeInTheDocument();
  }, 15000);

  it("var olmayan sofor_id için gerçek 404 → hata mesajı", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<DriverScoreBreakdown driverId={999999} />);
    await waitFor(
      () =>
        expect(screen.getByText("Skor kırılımı alınamadı")).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
