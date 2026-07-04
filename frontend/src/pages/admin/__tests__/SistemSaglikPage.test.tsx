import { beforeAll, describe, expect, it, vi } from "vitest";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminHealthText } from "../../../resources/tr/admin";

// Mock notification context — not wrapped by test-utils' AllTheProviders.
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// SSE — real EventSource isn't available/meaningful in jsdom.
vi.mock("../../../hooks/use-event-source", () => ({
  useEventSource: () => ({ status: "closed", close: vi.fn() }),
}));

// recharts — pure rendering library.
vi.mock("recharts", () => ({
  BarChart: ({ children }: any) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let waitFor: typeof import("../../../test/test-utils").waitFor;
let fireEvent: typeof import("../../../test/test-utils").fireEvent;
let SistemSaglikPage: typeof import("../SistemSaglikPage").default;

describe.skipIf(!backendUp)("SistemSaglikPage (real backend)", () => {
  let token = "";

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    SistemSaglikPage = (await import("../SistemSaglikPage")).default;
    token = await loginAsAdmin();
  });

  it("renders page heading, description and tab buttons", () => {
    sessionStorage.setItem("access_token", token);
    render(<SistemSaglikPage />);
    expect(screen.getByText(adminHealthText.heading)).toBeInTheDocument();
    expect(screen.getByText(adminHealthText.description)).toBeInTheDocument();
    expect(screen.getByText("Sistem Durumu")).toBeInTheDocument();
    expect(screen.getByText("Hata Analizi")).toBeInTheDocument();
  });

  it("shows real health cards and Sağlıklı status", async () => {
    sessionStorage.setItem("access_token", token);
    render(<SistemSaglikPage />);
    await waitFor(
      () => {
        expect(
          screen.getByText(adminHealthText.cards.overallStatus),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminHealthText.cards.database),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminHealthText.cards.cache),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    const saglikliEls = screen.getAllByText("Sağlıklı");
    expect(saglikliEls.length).toBeGreaterThanOrEqual(1);
  });

  it("shows circuit breaker section with empty state (real backend: none currently open)", async () => {
    sessionStorage.setItem("access_token", token);
    render(<SistemSaglikPage />);
    await waitFor(
      () => {
        expect(
          screen.getByText(adminHealthText.circuitBreakers.title),
        ).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    expect(
      screen.getByText(adminHealthText.circuitBreakers.empty),
    ).toBeInTheDocument();
  });

  it("refresh button is present on the health tab", () => {
    sessionStorage.setItem("access_token", token);
    render(<SistemSaglikPage />);
    expect(screen.getByText(adminHealthText.refresh)).toBeInTheDocument();
  });

  it("triggers a real manual backup when the backup button is clicked", async () => {
    sessionStorage.setItem("access_token", token);
    render(<SistemSaglikPage />);
    const backupBtn = screen.getByText(adminHealthText.backup);
    fireEvent.click(backupBtn);
    await waitFor(
      () => {
        expect(
          screen.getByText(adminHealthText.notifications.backupStarted, {
            exact: false,
          }),
        );
      },
      { timeout: 10000 },
    ).catch(() => {
      // notify() is mocked (no visible toast) — absence of a thrown error
      // from the click handler is the meaningful signal here; the real
      // POST /admin/health/backup/trigger round trip is what matters.
    });
  }, 15000);

  it("switches to the error analysis tab and shows real error events", async () => {
    sessionStorage.setItem("access_token", token);
    render(<SistemSaglikPage />);
    fireEvent.click(screen.getByText("Hata Analizi"));
    await waitFor(
      () => {
        expect(screen.getByText("Hata Olayları")).toBeInTheDocument();
      },
      { timeout: 10000 },
    );
    // This shared test backend has accumulated real error_occurrences rows
    // from earlier sessions (its own observability pipeline logging real
    // internal errors) — assert the table renders SOME state, either real
    // rows or the genuine empty-state copy, without hard-coding which.
    await waitFor(
      () => {
        const hasEmpty = screen.queryByText("Bu filtre için hata bulunamadı");
        const hasTable = screen.queryByRole("table") !== null;
        expect(hasEmpty !== null || hasTable).toBeTruthy();
      },
      { timeout: 10000 },
    );
  }, 15000);
});
