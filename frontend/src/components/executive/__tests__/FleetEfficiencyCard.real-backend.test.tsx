/**
 * 0-mock epiği: FleetEfficiencyCard.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen senaryo — bu test
 * ortamının veritabanı boş (0 araç/şoför/anomali) olduğu için
 * `GET /reports/executive/kpi` gerçek, deterministik bir "cold-start"
 * yanıtı üretir: confidence=0.0 (curl ile doğrulandı) → bu, mock'lu
 * dosyadaki "low confidence → cold-start uyarısı" senaryosunun gerçek
 * karşılığı. fvi/alt-skorlar (75/75/75/75) da deterministik cold-start
 * default'ları (bkz app/core/ml/fleet_efficiency_index.py).
 *
 * "happy path" (fvi=78, trend +4.0) ve "503 devre dışı" senaryoları gerçek
 * fleet verisi seed'i / backend env-flag restart'ı gerektirir — mock'lu
 * dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("FleetEfficiencyCard (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let FleetEfficiencyCard: typeof import("../FleetEfficiencyCard").FleetEfficiencyCard;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ FleetEfficiencyCard } = await import("../FleetEfficiencyCard"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş filo → gerçek backend cold-start uyarısı + alt-skor başlıkları", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<FleetEfficiencyCard />);

    await waitFor(
      () =>
        expect(
          screen.getByText(
            "Düşük güven — bazı alt-skorlar veri yetersiz (cold-start)",
          ),
        ).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText("Yakıt")).toBeInTheDocument();
    expect(screen.getByText("Bakım")).toBeInTheDocument();
    expect(screen.getByText("Şoför")).toBeInTheDocument();
    expect(screen.getByText("Anomali Kalitesi")).toBeInTheDocument();
  }, 15000);
});
