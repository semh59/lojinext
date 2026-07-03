/**
 * 0-mock epiği: DriverPerformanceModal.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen senaryolar. Taze
 * (sıfır-sefer) bir şoför için `get_performance_details` deterministik bir
 * sonuç üretir (bkz app/core/services/sofor_service.py:496) — trip_count=0,
 * avg_consumption=0 → safety=100, eco=90, compliance=100, total=96,
 * trend="increasing". Bu, gerçek DB durumundan bağımsız, kod yoluyla
 * garanti edilen bir sonuç (curl ile doğrulandı).
 *
 * "loading" senaryosu (never-resolving promise) gerçek ağ isteğiyle
 * deterministik biçimde tetiklenemediği için mock'lu dosyada kalıyor.
 * Ayrı dosyada tutuluyor çünkü aynı dosyada hem `vi.mock` hem gerçek modül
 * import'u modül-cache çakışmasına yol açıyor (bkz DriverRouteProfile emsali).
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
    div: ({ children, className, ...rest }: any) => (
      <div className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("DriverPerformanceModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let DriverPerformanceModal: typeof import("../DriverPerformanceModal").DriverPerformanceModal;
  let driverPerformanceText: typeof import("../../../resources/tr/drivers").driverPerformanceText;
  let authToken: string;
  let driverId: number;
  let driverName: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ DriverPerformanceModal } = await import("../DriverPerformanceModal"));
    ({ driverPerformanceText } = await import("../../../resources/tr/drivers"));

    const createResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        ad_soyad: `zm perf modal test ${Date.now()}`,
        aktif: true,
      }),
    });
    const created = await createResp.json();
    driverId = created.id;
    driverName = created.ad_soyad;
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

  it("taze şoför için gerçek backend deterministik skorları döner", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={{ id: driverId, ad_soyad: driverName } as any}
      />,
    );

    expect(screen.getByText(driverPerformanceText.title)).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.subtitle(driverName)),
    ).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText("96")).toBeInTheDocument(), {
      timeout: 10000,
    });
    expect(
      screen.getByText(driverPerformanceText.trends.increasing),
    ).toBeInTheDocument();
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(2); // total_trips + total_km
    expect(
      screen.getByText(driverPerformanceText.stats.trips),
    ).toBeInTheDocument();
    expect(
      screen.getByText(driverPerformanceText.stats.distance),
    ).toBeInTheDocument();
  }, 15000);

  it("var olmayan sofor_id için gerçek 404 → hata mesajı", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(
      <DriverPerformanceModal
        isOpen={true}
        onClose={vi.fn()}
        driver={{ id: 999999, ad_soyad: "Hayalet" } as any}
      />,
    );
    await waitFor(
      () => expect(screen.getByText("Şoför bulunamadı")).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
