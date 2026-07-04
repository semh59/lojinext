/**
 * 0-mock epiği: InspectionAlertModal.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı çalışan bir sürüm. Gerçek
 * GET /vehicles/inspection-alerts endpoint'i çağrılır; expiring + overdue
 * araçlar benzersiz (Date.now() suffix'li) plaka/marka ile oluşturulup
 * afterAll'da silinir.
 *
 * Orijinal mock'lu dosya (InspectionAlertModal.test.tsx) korunuyor: isOpen=false
 * erken-return davranışı ve saf render/format testleri için mock hâlâ yeterli
 * ve daha hızlı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("InspectionAlertModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let InspectionAlertModal: typeof import("../InspectionAlertModal").InspectionAlertModal;
  let authToken: string;
  const suffix = Date.now();
  const plakaExpiring = `34 ZM ${suffix.toString().slice(-3)}1`;
  const plakaOverdue = `34 ZM ${suffix.toString().slice(-3)}2`;
  let expiringId: number;
  let overdueId: number;

  function futureDate(daysFromNow: number): string {
    const d = new Date();
    d.setDate(d.getDate() + daysFromNow);
    return d.toISOString().slice(0, 10);
  }

  async function createVehicle(
    plaka: string,
    marka: string,
    muayeneTarihi: string,
  ) {
    const resp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({
        plaka,
        marka,
        model: "TestModel",
        yil: 2022,
        hedef_tuketim: 30,
        aktif: true,
        yakit_tipi: "DIZEL",
        muayene_tarihi: muayeneTarihi,
      }),
    });
    const created = await resp.json();
    if (!resp.ok || !created.id) {
      throw new Error(
        `Vehicle creation failed (${resp.status}): ${JSON.stringify(created)}`,
      );
    }
    return created.id as number;
  }

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ InspectionAlertModal } = await import("../InspectionAlertModal"));

    expiringId = await createVehicle(
      plakaExpiring,
      `InspExpiring${suffix}`,
      futureDate(14),
    );
    overdueId = await createVehicle(
      plakaOverdue,
      `InspOverdue${suffix}`,
      futureDate(-10),
    );
  }, 20000);

  afterAll(async () => {
    for (const id of [expiringId, overdueId]) {
      if (id) {
        await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${id}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${authToken}` },
        }).catch(() => {});
      }
    }
    vi.unstubAllEnvs();
  });

  it("shows both expiring and overdue vehicles created against the real backend", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<InspectionAlertModal isOpen onClose={() => {}} />);
    await waitFor(
      () => {
        expect(screen.getByText(plakaExpiring)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(screen.getByText(plakaOverdue)).toBeInTheDocument();
  }, 15000);
});
