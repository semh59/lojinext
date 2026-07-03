/**
 * 0-mock epiği: CashflowProjectionChart.test.tsx'in mock'lu senaryosuna ek
 * olarak, gerçek backend'e karşı seed gerektirmeyen senaryo — boş DB'de
 * `GET /reports/executive/cashflow` deterministik olarak grand_total_tl=0
 * (13 haftalık tüm kalemler sıfır) döner (curl ile doğrulandı); grafik ve
 * "Toplam" etiketi veri miktarından bağımsız her zaman render edilir.
 *
 * Recharts JSDOM uyumsuzluğu için stub korunuyor (bkz dosya başı yorumu,
 * mock'lu dosyadaki emsal).
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("CashflowProjectionChart (real backend)", () => {
  let render: typeof import("../../../test/test-utils").render;
  let screen: typeof import("../../../test/test-utils").screen;
  let waitFor: typeof import("../../../test/test-utils").waitFor;
  let CashflowProjectionChart: typeof import("../CashflowProjectionChart").CashflowProjectionChart;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    ({ CashflowProjectionChart } = await import("../CashflowProjectionChart"));
  });

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("boş filo → gerçek backend sıfır toplam + grafik render edilir", async () => {
    sessionStorage.setItem("access_token", authToken);
    render(<CashflowProjectionChart />);

    await waitFor(
      () => expect(screen.getByText(/Toplam/)).toBeInTheDocument(),
      {
        timeout: 10000,
      },
    );
    expect(screen.getByText("₺0")).toBeInTheDocument();
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
  }, 15000);
});
