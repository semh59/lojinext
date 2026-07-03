/**
 * 0-mock epiği Faz 2: `render/routeLabel/disabled-button` testleri zaten
 * `locationService`'e dokunmuyordu (pure UI mantığı) — değişiklik yok.
 * "400 detail" testi gerçek backend'e çevrildi (var olmayan sefer_id —
 * seed gerektirmeyen, ucuz, gerçek bir 400 tetikleyici). "Başarılı
 * kalibrasyon" testi DOKÜMANTE mock'lu kalıyor: gerçek bir başarı, GPS
 * rota verisi (rota_detay.coordinates) + guzergah_id bağlı gerçek bir
 * Sefer seed'i gerektirir — bu, sefer/trip domain'inin kendi seed
 * altyapısı (app/tests/_helpers/seed.py'deki gibi), frontend'in kendi API
 * yüzeyinden erişilebilir değil ve bu epiğin Route/Location kapsamı
 * dışında (sefer-oluşturma ayrı bir domain). Backend tarafında zaten
 * gerçek DB'ye karşı kapsanıyor: test_route_calibration_coverage.py.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("CalibrationModal (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let CalibrationModal: typeof import("../CalibrationModal").CalibrationModal;
  let authToken: string;

  beforeAll(async () => {
    // NOT: locationService.calibrateFromTrip diğer locationService
    // metodlarının aksine orval-generated client'i DEĞİL, doğrudan
    // axiosInstance.post(relative-path) kullanıyor — bu yüzden baseURL'in
    // /api/v1'i İÇERMESİ gerekiyor (REAL_BACKEND_ORIGIN değil,
    // REAL_BACKEND_URL). Bu ikisinin farklı konvansiyon beklemesi
    // (orval client'lar origin-only baseURL, ham axiosInstance çağrıları
    // /api/v1'li baseURL) bu epikte bulunan, önceden var olan bir
    // tutarsızlık — bu dosyanın kapsamı dışı, sadece doğru değeri seçiyoruz.
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, fireEvent, waitFor } = await import(
      "../../../test/test-utils"
    ));
    ({ CalibrationModal } = await import("../CalibrationModal"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("isOpen=false ise hiçbir şey render edilmez", () => {
    const { container } = render(
      <CalibrationModal isOpen={false} onClose={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("routeLabel başlık altında gösterilir", () => {
    render(
      <CalibrationModal
        isOpen
        onClose={() => {}}
        routeLabel="Istanbul → Ankara"
      />,
    );
    expect(screen.getByText("Istanbul → Ankara")).toBeInTheDocument();
  });

  it("Sefer ID boş veya negatif iken Kalibre Et disabled", () => {
    render(<CalibrationModal isOpen onClose={() => {}} />);
    const button = screen.getByRole("button", { name: /Kalibre Et/ });
    expect(button).toBeDisabled();
  });

  it("var olmayan sefer_id için gerçek backend 400 detail mesajını kırmızı banner olarak gösterir", async () => {
    render(<CalibrationModal isOpen onClose={() => {}} />);
    sessionStorage.setItem("access_token", authToken); // AuthContext'in olası temizlemesine karşı
    fireEvent.change(screen.getByLabelText("Sefer ID"), {
      target: { value: "999999" },
    });
    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByRole("button", { name: /Kalibre Et/ }));

    await waitFor(
      () =>
        expect(screen.getByText(/Kalibrasyon yapılamadı/i)).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
