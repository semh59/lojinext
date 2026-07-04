/**
 * 0-mock epiği: BreakdownReportModal'ın gerçek backend'e karşı senaryoları.
 *
 * Bu component ÜÇ farklı axios çağrı biçimini aynı anda kullanıyor:
 *   1. `vehicleService.getAll` (@/api/vehicles) — orval-generated client,
 *      request url'i kendi içinde zaten "/api/v1/..." embed ediyor.
 *   2. `dorseService.getAll` (@/services/dorseService) — elle yazılmış,
 *      axiosInstance.get("/trailers/...") — "/api/v1" PREFIX'İ YOK.
 *   3. `axiosInstance.post("/maintenance/report-breakdown", ...)` — aynı
 *      şekilde elle yazılmış, prefix yok.
 *
 * Bu üçünü aynı paylaşılan axiosInstance.baseURL ile gerçek backend'e karşı
 * çalıştırmaya çalışırken GERÇEK bir prod bug bulundu: production'ın kendi
 * build config'i (docker-compose.yml + CI, VITE_API_URL=/api/v1) baseURL'i
 * "/api/v1" yapıyor; orval-generated client'lar url'lerine ZATEN "/api/v1"
 * embed ettiği için istek "/api/v1/api/v1/vehicles/" olarak double-prefix'e
 * çıkıp gerçek backend'den 404 dönüyordu (curl ile doğrulandı — bkz
 * src/lib/orval-mutator.ts değişikliği). Bu, `@/api/vehicles`'ı kullanan
 * TÜM sayfaları (VehiclesModule dahil) etkiliyordu. Fix `src/lib/
 * orval-mutator.ts`'e eklendi: baseURL zaten "/api/v1" ile bitiyorsa,
 * generated client'ın gömülü "/api/v1" prefix'ini istekten önce temizliyor.
 * Bu fix sonrası hem generated hem elle-yazılmış çağrılar aynı baseURL
 * (`REAL_BACKEND_URL` = origin+/api/v1, prod'un gerçek konfigürasyonuyla
 * birebir) altında doğru çalışıyor — bu dosyadaki testler onu doğruluyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: any) => <>{children}</>,
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("BreakdownReportModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let BreakdownReportModal: typeof import("../BreakdownReportModal").BreakdownReportModal;
  let NotificationProvider: typeof import("../../../context/NotificationContext").NotificationProvider;
  let authToken: string;
  let vehicleId: number;
  let vehiclePlaka: string;
  let dorseId: number;
  let dorsePlaka: string;

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
    ({ BreakdownReportModal } = await import("../BreakdownReportModal"));
    ({ NotificationProvider } = await import(
      "../../../context/NotificationContext"
    ));

    const suffix = Date.now();
    vehiclePlaka = `34 BD ${suffix % 10000}`;
    const vResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        plaka: vehiclePlaka,
        marka: "MAN",
        model: "TGX",
        yil: 2020,
        tank_kapasitesi: 600,
        hedef_tuketim: 30.0,
        aktif: true,
        muayene_tarihi: new Date(Date.now() + 200 * 86400 * 1000)
          .toISOString()
          .slice(0, 10),
      }),
    });
    const vCreated = await vResp.json();
    vehicleId = vCreated.id;

    dorsePlaka = `34 DZ ${suffix % 10000}`;
    const dResp = await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/trailers/`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        plaka: dorsePlaka,
        tipi: "Tenteli",
        bos_agirlik_kg: 7000.0,
        maks_yuk_kapasitesi_kg: 27000,
        lastik_sayisi: 6,
      }),
    });
    const dCreated = await dResp.json();
    dorseId = dCreated.data.id;
  });

  afterAll(async () => {
    if (vehicleId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/vehicles/${vehicleId}`, {
        method: "DELETE",
        headers: authHeaders(),
      }).catch(() => {});
    }
    if (dorseId) {
      await fetch(`${REAL_BACKEND_ORIGIN}/api/v1/trailers/${dorseId}`, {
        method: "DELETE",
        headers: authHeaders(),
      }).catch(() => {});
    }
    vi.unstubAllEnvs();
  });

  const renderModal = (onClose = vi.fn()) => {
    sessionStorage.setItem("access_token", authToken);
    return render(
      <NotificationProvider>
        <BreakdownReportModal isOpen onClose={onClose} />
      </NotificationProvider>,
    );
  };

  it("renders the breakdown form with target toggle", () => {
    renderModal();
    expect(screen.getByText("Arıza Bildir")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Araç" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dorse" })).toBeInTheDocument();
  });

  it("lists the real, just-created vehicle in the vehicle dropdown", async () => {
    renderModal();
    await waitFor(
      () => {
        expect(
          screen.getByRole("option", { name: new RegExp(vehiclePlaka) }),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("switches to the dorse dropdown and lists the real, just-created trailer", async () => {
    renderModal();
    fireEvent.click(screen.getByRole("button", { name: "Dorse" }));
    expect(await screen.findByText("Dorse seçiniz…")).toBeInTheDocument();
    await waitFor(
      () => {
        expect(
          screen.getByRole("option", { name: new RegExp(dorsePlaka) }),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("requires a target before submitting (client-side, no network)", () => {
    renderModal();
    fireEvent.click(screen.getByRole("button", { name: "Bildir" }));
    expect(screen.getByText("Araç seçiniz.")).toBeInTheDocument();
  });

  it("submits a real dorse breakdown report end-to-end and closes on success", async () => {
    const onClose = vi.fn();
    renderModal(onClose);
    fireEvent.click(screen.getByRole("button", { name: "Dorse" }));

    await waitFor(() => {
      expect(
        screen.getByRole("option", { name: new RegExp(dorsePlaka) }),
      ).toBeInTheDocument();
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: String(dorseId) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Acil" }));
    fireEvent.change(screen.getByPlaceholderText("Arıza nedir?"), {
      target: { value: "lastik patladı (real-backend test)" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Bildir" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled(), {
      timeout: 10000,
    });
  }, 15000);
});
