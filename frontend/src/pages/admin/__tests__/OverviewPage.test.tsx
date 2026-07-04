import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../../test/real-backend";

// recharts stub — pure rendering library, not part of the backend contract.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: any) => (
    <div data-testid="line-chart-container">{children}</div>
  ),
  LineChart: ({ children }: any) => <svg>{children}</svg>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));

// TelegramOnayPanel — isolated, heavy dependency unrelated to this page's
// own queries.
vi.mock("../../../components/admin/TelegramOnayPanel", () => ({
  TelegramOnayPanel: () => (
    <div data-testid="telegram-onay-panel">TelegramOnayPanel</div>
  ),
}));

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let waitFor: typeof import("../../../test/test-utils").waitFor;
let AdminOverviewPage: typeof import("../OverviewPage").default;
let adminOverviewText: typeof import("../../../resources/tr/admin").adminOverviewText;

describe.skipIf(!backendUp)("AdminOverviewPage (real backend)", () => {
  let token = "";

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    ({ render, screen, waitFor } = await import("../../../test/test-utils"));
    AdminOverviewPage = (await import("../OverviewPage")).default;
    ({ adminOverviewText } = await import("../../../resources/tr/admin"));
    token = await loginAsAdmin();
  });

  beforeEach(() => {
    sessionStorage.setItem("access_token", token);
  });

  it("renders the main heading", () => {
    render(<AdminOverviewPage />);
    expect(screen.getByText(adminOverviewText.heading)).toBeInTheDocument();
  });

  it("renders the description subtitle", () => {
    render(<AdminOverviewPage />);
    expect(screen.getByText(adminOverviewText.description)).toBeInTheDocument();
  });

  it("renders all four KPI card labels", () => {
    render(<AdminOverviewPage />);
    expect(
      screen.getByText(adminOverviewText.cards.totalTrips),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminOverviewText.cards.activeVehicles),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminOverviewText.cards.systemStatus),
    ).toBeInTheDocument();
    expect(
      screen.getByText(adminOverviewText.cards.database),
    ).toBeInTheDocument();
  });

  it("shows real dashboard stats after loading (cold-start test DB: 0 trips)", async () => {
    render(<AdminOverviewPage />);
    await waitFor(
      () => {
        const zeros = screen.getAllByText("0");
        expect(zeros.length).toBeGreaterThanOrEqual(1);
      },
      { timeout: 10000 },
    );
  });

  it('shows "Sağlıklı" for the real backend health status', async () => {
    render(<AdminOverviewPage />);
    await waitFor(
      () => {
        const saglikliEls = screen.getAllByText("Sağlıklı");
        expect(saglikliEls.length).toBeGreaterThanOrEqual(1);
      },
      { timeout: 10000 },
    );
  }, 15000);

  it("renders TelegramOnayPanel placeholder", () => {
    render(<AdminOverviewPage />);
    expect(screen.getByTestId("telegram-onay-panel")).toBeInTheDocument();
  });

  it("shows empty trend message (real backend: no consumption data seeded)", async () => {
    render(<AdminOverviewPage />);
    await waitFor(
      () => {
        expect(
          screen.getByText(adminOverviewText.consumptionTrend.empty),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
  });

  it("renders Operasyonel Sağlık Özeti section title", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.operationalHealth.title),
      ).toBeInTheDocument();
    });
  });

  it("renders Devre Kesiciler label with 0 circuit breakers", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.operationalHealth.circuitBreakers),
      ).toBeInTheDocument();
    });
  });

  it("renders Son Yedekleme label", async () => {
    render(<AdminOverviewPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminOverviewText.operationalHealth.lastBackup),
      ).toBeInTheDocument();
    });
  });
});
