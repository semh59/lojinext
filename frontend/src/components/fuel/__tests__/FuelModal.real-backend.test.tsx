/**
 * 0-mock epiği: FuelModal.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı bir senaryo. FuelModal kendisi bir create/update
 * endpoint'i çağırmıyor — `onSave` prop'u parent bileşen tarafından enjekte
 * edilir (bu yüzden `onSave` burada da bir vi.fn() kalıyor, gerçek bir
 * fuel-purchase endpoint'i yok). Ama modal, açıldığında `vehicleService.getAll`
 * ile GERÇEK bir React Query isteği atıp araç dropdown'unu dolduruyor —
 * mock'lu dosyada bu her zaman boş listeye sabitleniyordu. Burada gerçek bir
 * araç oluşturup dropdown'da göründüğünü doğruluyoruz (gerçek HTTP round-trip).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("FuelModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let FuelModal: typeof import("../FuelModal").FuelModal;
  let fuelModalText: typeof import("../../../resources/tr/fuel").fuelModalText;
  let authToken: string;
  let vehicleId: number;
  let plaka: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ FuelModal } = await import("../FuelModal"));
    ({ fuelModalText } = await import("../../../resources/tr/fuel"));

    const suffix = String(Date.now()).slice(-4);
    plaka = `34 ZM ${suffix}`;
    const createResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        plaka,
        marka: "Test Marka",
        aktif: true,
      }),
    });
    const created = await createResp.json();
    vehicleId = created.id;
  });

  afterAll(async () => {
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den gelen araç listesini dropdown'da gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(
      <FuelModal
        isOpen={true}
        onClose={vi.fn()}
        onSave={vi.fn().mockResolvedValue(undefined)}
        record={null}
      />,
    );

    await waitFor(
      () =>
        expect(screen.getByText(plaka, { exact: false })).toBeInTheDocument(),
      {
        timeout: 10000,
      },
    );
    expect(screen.getByText(fuelModalText.createTitle)).toBeInTheDocument();
  }, 15000);
});
