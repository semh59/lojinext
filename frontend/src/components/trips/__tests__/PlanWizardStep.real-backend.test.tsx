/**
 * 0-mock epiği: PlanWizardStep.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı bir senaryo. Gerçek bir araç + şoför oluşturup
 * gerçek `POST /trips/plan-wizard` çağrısıyla dönen önerileri, seçim akışını
 * ve `onSelectAndContinue` çağrısını uçtan uca doğruluyoruz. 503/boş-sonuç
 * hata-enjeksiyonu senaryoları backend'de gerçekten tetiklenemediğinden
 * mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("PlanWizardStep (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let PlanWizardStep: typeof import("../PlanWizardStep").PlanWizardStep;
  let authToken: string;
  let vehicleId: number;
  let plaka: string;
  let driverId: number;
  let driverName: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ PlanWizardStep } = await import("../PlanWizardStep"));

    const suffix = String(Date.now()).slice(-4);
    plaka = `34 PW ${suffix}`;
    driverName = `Test Sofor Pw ${suffix}`;

    const vResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ plaka, marka: "Test Marka", aktif: true }),
    });
    vehicleId = (await vResp.json()).id;

    const dResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ ad_soyad: driverName, aktif: true }),
    });
    driverId = (await dResp.json()).id;
  });

  afterAll(async () => {
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    if (driverId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/drivers/${driverId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  it("gerçek plan-wizard yanıtından öneri kartlarını gösterir, seçim yapınca onSelectAndContinue gerçek id'lerle çağrılır", async () => {
    sessionStorage.setItem("access_token", authToken);

    // MIRROR-STATE deseni: wizard top_n<=5 (server-side cap) ve skor,
    // ADAYLAR-ARASI min-max yakıt normalizasyonuna bağlı — "kendi seed'lediğim
    // araç listede olmalı" varsayımı 10+ araçlı herhangi bir DB'de
    // deterministik DEĞİL (2026-07-07 seri koşumda canlı yakalandı). Bunun
    // yerine backend'in AYNI payload için gerçekten döndürdüğünü al (cache_hit
    // sayesinde component çağrısıyla birebir aynı liste) ve UI'ın o gerçeği
    // gösterdiğini + seçimin o gerçek id'leri taşıdığını assert et.
    const payload = {
      tarih: "2026-07-20",
      cikis_yeri: "Ankara",
      varis_yeri: "İstanbul",
      mesafe_km: 450,
      top_n: 5,
    };
    const apiResp = await fetch(
      `${REAL_BACKEND_ORIGIN}/api/v1/trips/plan-wizard`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify(payload),
      },
    );
    expect(apiResp.status).toBe(200);
    const expected = (await apiResp.json()) as {
      vehicles: Array<{ arac_id: number; plaka: string }>;
      drivers: Array<{ sofor_id: number; ad_soyad: string }>;
    };
    // beforeAll'da aktif araç seed'lendiği için hard-filter en az 1 araç
    // döndürmek zorunda (boş liste = gerçek regresyon, maskelenmez).
    expect(expected.vehicles.length).toBeGreaterThan(0);

    const onSelect = vi.fn();
    render(<PlanWizardStep payload={payload} onSelectAndContinue={onSelect} />);

    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByRole("button", { name: /Önerileri Getir/ }));

    const v0 = expected.vehicles[0];
    await waitFor(
      () => expect(screen.getByText(v0.plaka)).toBeInTheDocument(),
      { timeout: 15000 },
    );

    const continueBtn = screen.getByRole("button", { name: /Seç ve Devam/ });
    expect(continueBtn).toBeDisabled();
    fireEvent.click(screen.getByText(v0.plaka));

    if (expected.drivers.length > 0) {
      const d0 = expected.drivers[0];
      expect(screen.getByText(d0.ad_soyad)).toBeInTheDocument();
      fireEvent.click(screen.getByText(d0.ad_soyad));
      await waitFor(() => expect(continueBtn).toBeEnabled());
      fireEvent.click(continueBtn);
      expect(onSelect).toHaveBeenCalledWith(
        expect.objectContaining({
          arac_id: v0.arac_id,
          sofor_id: d0.sofor_id,
          plaka: v0.plaka,
        }),
      );
    } else {
      // Gerçek "önerilebilir şoför yok" durumu (ör. hepsinin o tarihte
      // Planned seferi var): şoför seçilemediği için devam butonu disabled
      // kalmalı — UI bu gerçeği de doğru yansıtmalı.
      expect(continueBtn).toBeDisabled();
    }
  }, 30000);
});
