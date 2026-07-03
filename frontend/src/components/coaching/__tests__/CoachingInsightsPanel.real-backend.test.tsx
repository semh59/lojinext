/**
 * 0-mock epiği (coaching domain): CoachingInsightsPanel.test.tsx'in
 * mock'lu senaryolarına ek olarak, gerçek backend'e karşı seed
 * gerektirmeyen 2 senaryo:
 * - "trip_count<5 + anomalisiz yeni şoför" → DriverCoachingEngine.
 *   generate_coaching (app/core/ai/driver_coaching_engine.py) LLM'e hiç
 *   gitmeden deterministik "fallback" + insights=[] döner (has_any=False
 *   ve trip_count<5 erken dönüş yolu) — gerçek, seed'siz, ucuz bir
 *   pozitif senaryo.
 * - "var olmayan sofor_id" → gerçek 404, seed gerektirmez.
 *
 * Ayrı dosyada tutuluyor çünkü aynı dosyada hem `vi.mock` (dosya-
 * seviyesi, hoisted) hem gerçek modül import'u tutmak modül-cache
 * çakışmasına yol açıyordu (bkz DriverRouteProfile.real-backend.test.tsx
 * emsali).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("CoachingInsightsPanel (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let CoachingInsightsPanel: typeof import("../CoachingInsightsPanel").CoachingInsightsPanel;
  let authToken: string;
  let driverId: number;
  let driverName: string; // backend title-case sanitize eder; oluşturma yanıtından okunur

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ CoachingInsightsPanel } = await import("../CoachingInsightsPanel"));

    // Yeni, anomalisiz, sıfır-sefer bir şoför oluştur — trip_count<5 +
    // anomalisiz olduğu için engine LLM'e hiç gitmeden deterministik
    // fallback+empty döner (bkz dosya başı yorumu).
    const createResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        ad_soyad: `zm coaching test ${Date.now()}`,
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

  it("yeni/anomalisiz şoför için gerçek backend fallback+empty döner", async () => {
    sessionStorage.setItem("access_token", authToken); // AuthProvider temizlemesine karşı
    render(<CoachingInsightsPanel soforId={driverId} />);

    await waitFor(
      () => expect(screen.getByText(driverName)).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(
      screen.getByText("Bu şoför için aktif öneri yok"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Kural tabanlı/)).toBeInTheDocument();
  }, 15000);

  it("var olmayan sofor_id için gerçek backend 404 → kırmızı hata banner'ı", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<CoachingInsightsPanel soforId={999999} />);

    await waitFor(
      () =>
        expect(screen.getByText("Öneriler yüklenemedi")).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
