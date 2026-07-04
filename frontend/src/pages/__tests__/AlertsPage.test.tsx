/**
 * 0-mock epiği: AlertsPage'in 3 gerçek endpoint'i (anomalies/fleet/insights,
 * anomalies/ recent list, admin/investigations list) gerçek backend'e karşı
 * cold-start/boş-state ile doğrulanıyor. Fine-grained senaryolar (fuel-gap
 * >0, bakım adayları, acknowledge/resolve akışı, RCA alanları) çapraz-tablo
 * sentetik veri seed'i gerektirdiğinden `AlertsPage.mocked.test.tsx`'te
 * mock'lu kalıyor — bkz. o dosyanın başlık yorumu.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

// framer-motion / recharts — UI kütüphanesi render'ı, dış sınır değil.
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: any) => <svg>{children}</svg>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

vi.mock("../../hooks/usePageTitle", () => ({ usePageTitle: vi.fn() }));

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("AlertsPage (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let AlertsPage: typeof import("../AlertsPage").default;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    const token = await loginAsAdmin();
    sessionStorage.setItem("access_token", token);
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ default: AlertsPage } = await import("../AlertsPage"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("renders heading, day-filters and KPI labels against a real, empty backend", async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
    render(<AlertsPage />);

    expect(screen.getByText("Anomaliler")).toBeInTheDocument();
    expect(screen.getByText("7 Gün")).toBeInTheDocument();
    expect(screen.getByText("30 Gün")).toBeInTheDocument();

    await waitFor(
      () => {
        const dashes = screen.getAllByText("—");
        expect(dashes.length).toBeGreaterThanOrEqual(1);
      },
      { timeout: 15000 },
    );

    expect(screen.getByText("Yakıt Açığı")).toBeInTheDocument();
    expect(screen.getByText("Güzergah Sapması")).toBeInTheDocument();
  }, 20000);

  it('shows "Bu filtreyle eşleşen anomali yok." when the real anomalies list is empty', async () => {
    sessionStorage.setItem("access_token", await loginAsAdmin());
    render(<AlertsPage />);
    await waitFor(
      () => {
        expect(
          screen.getByText("Bu filtreyle eşleşen anomali yok."),
        ).toBeInTheDocument();
      },
      { timeout: 15000 },
    );
  }, 20000);
});
