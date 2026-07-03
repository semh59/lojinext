/**
 * 0-mock epiği: CarbonReportCard.test.tsx'in mock'lu senaryosuna ek olarak,
 * gerçek backend'e karşı seed gerektirmeyen senaryo — boş DB'de
 * `GET /reports/executive/carbon` deterministik olarak total_co2_kg=0,
 * vehicle_count=0, delta_pct=-100.0 (co2_per_km 0 < benchmark 0.72) döner
 * (curl ile doğrulandı) → success tonu (benchmark altı).
 *
 * "happy path" (breakdown by_euro_class'lı) senaryosu gerçek araç+yakıt
 * verisi seed'i gerektirir — mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("CarbonReportCard (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let CarbonReportCard: typeof import("../CarbonReportCard").CarbonReportCard;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ CarbonReportCard } = await import("../CarbonReportCard"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş filo → gerçek backend sıfır CO2 + benchmark altı (-100%)", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<CarbonReportCard />);

    await waitFor(
      () => expect(screen.getByText(/-100\.0%/)).toBeInTheDocument(),
      { timeout: 10000 },
    );
    expect(screen.getByText("Toplam CO2 (kg)")).toBeInTheDocument();
    expect(screen.getByText("CO2/km")).toBeInTheDocument();
    expect(screen.getByText(/Benchmark altı/)).toBeInTheDocument();
  }, 15000);
});
