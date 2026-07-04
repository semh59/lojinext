/**
 * 0-mock epiği: ExportDialog.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı bir senaryo. `vehiclesApi.getAll` yalnızca
 * `type="vehicle_report"` iken çağrılır (bkz ExportDialog.tsx satır 90-109)
 * — mevcut mock'lu dosyadaki hiçbir test bu tipi kullanmıyor, dolayısıyla
 * `vi.mock("../../../services/api")` orada aslında hiç tetiklenmiyordu.
 * Burada gerçek, az önce oluşturulmuş bir araç ile bu yolu uçtan uca
 * doğruluyoruz (GET /vehicles/ round-trip, açılır listede plaka görünüyor
 * mu, seçilince onExport doğru targetId ile çağrılıyor mu).
 *
 * `onExport`/`onClose` prop olarak enjekte edildiği için (bileşenin kendisi
 * export/indirme işini yapmıyor) burada da mock'lanıyor — gerçek backend
 * çağrısı yalnızca araç listesi için.
 */
import { beforeAll, afterAll, describe, expect, it, vi } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("ExportDialog (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let ExportDialog: typeof import("../ExportDialog").ExportDialog;
  let authToken: string;
  let vehicleId: number;
  let vehiclePlaka: string;

  const authHeaders = () => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${authToken}`,
  });

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ ExportDialog } = await import("../ExportDialog"));

    vehiclePlaka = `34 ED ${Date.now() % 10000}`;
    const vResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        plaka: vehiclePlaka,
        marka: "Volvo",
        model: "FH16",
        yil: 2021,
        tank_kapasitesi: 600,
        hedef_tuketim: 29.0,
        aktif: true,
      }),
    });
    const vCreated = await vResp.json();
    vehicleId = vCreated.id;
  });

  afterAll(async () => {
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers: authHeaders(),
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("vehicle_report tipinde gerçek araç listesini yükler ve seçilince onExport gerçek targetId ile çağrılır", async () => {
    sessionStorage.setItem("access_token", authToken);
    const onExport = vi.fn().mockResolvedValue(undefined);
    render(
      <ExportDialog
        isOpen
        onClose={vi.fn()}
        title="Araç Raporu"
        description="Test"
        type="vehicle_report"
        onExport={onExport}
      />,
    );

    const select = await waitFor(
      () => {
        const combos = screen.getAllByRole("combobox") as HTMLSelectElement[];
        const vehicleSelect = combos.find((el) =>
          Array.from(el.options).some(
            (opt) => opt.textContent?.includes(vehiclePlaka),
          ),
        );
        expect(vehicleSelect).toBeDefined();
        return vehicleSelect!;
      },
      { timeout: 10000 },
    );

    fireEvent.change(select, { target: { value: String(vehicleId) } });

    fireEvent.click(screen.getByText("PDF İndir"));

    await waitFor(() => {
      expect(onExport).toHaveBeenCalledWith(
        expect.objectContaining({ targetId: String(vehicleId) }),
      );
    });
  }, 15000);
});
