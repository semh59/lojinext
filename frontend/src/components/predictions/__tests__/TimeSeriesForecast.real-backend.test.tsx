/**
 * 0-mock epiği: TimeSeriesForecast.test.tsx'in mock'lu senaryolarına ek
 * olarak, gerçek backend'e karşı bir senaryo. Test DB'sinde henüz günlük
 * agregasyon oluşturacak kadar sefer/yakıt verisi yok — backend gerçekten
 * `409 PRECONDITION_NOT_MET` döner (curl ile doğrulandı: "At least 3 daily
 * aggregates are required for forecasting, received 0."), bu da bileşenin
 * gerçek hata yolunu HTTP round-trip'iyle egzersiz eder. "Başarılı tahmin"
 * senaryosu günlere yayılan seed gerektirdiğinden mock'lu dosyada kalıyor.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("recharts", () => ({
  AreaChart: ({ children }: any) => <div>{children}</div>,
  Area: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  Line: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("TimeSeriesForecast (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let fireEvent: typeof import("../../../test/test-utils").fireEvent;
  let TimeSeriesForecast: typeof import("../TimeSeriesForecast").TimeSeriesForecast;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    ({ TimeSeriesForecast } = await import("../TimeSeriesForecast"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("gerçek backend'den 409 (yetersiz veri) döner ve hata mesajı gösterir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<TimeSeriesForecast />);

    sessionStorage.setItem("access_token", authToken);
    fireEvent.click(screen.getByRole("button", { name: "Tahmin Et" }));

    await waitFor(
      () =>
        expect(screen.getByText(/Tahmin oluşturulamadı/)).toBeInTheDocument(),
      { timeout: 10000 },
    );
  }, 15000);
});
