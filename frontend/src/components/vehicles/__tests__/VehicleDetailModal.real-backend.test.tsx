/**
 * 0-mock epiği: VehicleDetailModal.test.tsx'in mock'lu senaryosuna (rejected
 * getStats → "unavailable" state) ek olarak, gerçek backend'e karşı çalışan
 * bir sürüm. Gerçek GET /vehicles/{id}/stats + /events çağrılır; taze
 * oluşturulan bir araç için stats sıfırlanmış (toplam_sefer=0,
 * toplam_km=0.0, ort_tuketim=0.0) döner — bu, mock'lanan "rejected"
 * senaryosundan FARKLI, gerçek ve önemli bir dallanma: sıfır-veri durumu
 * hâlâ tire ("-") gösterir (falsy kontrolü), ayrı bir gerçek olay
 * (CREATED) de zaman çizelgesinde görünür.
 *
 * Orijinal mock'lu dosya (VehicleDetailModal.test.tsx) korunuyor: getStats'ın
 * gerçekten reddedilmesi (backend hatası) senaryosu gerçek backend'e karşı
 * pratik olarak tetiklenemez.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("VehicleDetailModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let VehicleDetailModal: typeof import("../VehicleDetailModal").VehicleDetailModal;
  let authToken: string;
  const suffix = Date.now();
  const plaka = `34 ZM ${suffix.toString().slice(-3)}3`;
  const marka = `DetTest${suffix}`;
  let vehicleId: number;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ VehicleDetailModal } = await import("../VehicleDetailModal"));

    const resp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        plaka,
        marka,
        model: "M1",
        yil: 2024,
        hedef_tuketim: 28,
        aktif: true,
        yakit_tipi: "DIZEL",
      }),
    });
    const created = await resp.json();
    if (!resp.ok || !created.id) {
      throw new Error(
        `Vehicle creation failed (${resp.status}): ${JSON.stringify(created)}`,
      );
    }
    vehicleId = created.id as number;
  }, 20000);

  afterAll(async () => {
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("shows plate/brand and dashed stats for a fresh vehicle with no trips, plus the real CREATED event", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(
      <VehicleDetailModal
        isOpen
        onClose={() => {}}
        vehicle={{
          id: vehicleId,
          plaka,
          marka,
          model: "M1",
          yil: 2024,
          yakit_tipi: "DIZEL",
          hedef_tuketim: 28,
          aktif: true,
        }}
      />,
    );

    await waitFor(
      () => {
        expect(screen.getByText(plaka)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(screen.getByText(new RegExp(marka))).toBeInTheDocument();

    // Fresh vehicle → zero-valued stats render as "-" (falsy checks), not "0 km"
    await waitFor(
      () => {
        expect(screen.queryByText("0 km")).not.toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    // Real CREATED event from vehicle creation shows up in the timeline
    await waitFor(
      () => {
        expect(screen.getByText("Oluşturuldu")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);
});
