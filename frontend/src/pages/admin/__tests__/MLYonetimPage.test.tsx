import { beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminMlText } from "../../../resources/tr/admin";

// Mock notification context — not wrapped by test-utils' AllTheProviders.
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let waitFor: typeof import("../../../test/test-utils").waitFor;
let fireEvent: typeof import("../../../test/test-utils").fireEvent;
let AdminModelManagementPage: typeof import("../MLYonetimPage").default;

describe.skipIf(!backendUp)(
  "AdminModelManagementPage / MLYonetimPage (real backend)",
  () => {
    let token = "";
    let vehicleId = 0;
    // The vehicles LIST endpoint (used by vehicleService.getAll(), which
    // this page's selector reads) formats plaka with spaces ("34ML1234"
    // -> "34 ML 1234"), but POST /vehicles/'s own create response does
    // NOT apply the same formatting — an existing inconsistency between
    // endpoints, out of scope here. Match on the unique digit suffix only
    // so the assertion doesn't depend on which formatting convention is
    // in effect.
    const plakaSuffix = Date.now().toString().slice(-4);

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
      ({ render, screen, waitFor, fireEvent } = await import(
        "../../../test/test-utils"
      ));
      AdminModelManagementPage = (await import("../MLYonetimPage")).default;

      token = await loginAsAdmin();
      const headers = { Authorization: `Bearer ${token}` };
      const vehicleResp = await axios.post(
        `${REAL_BACKEND_URL}/vehicles/`,
        { plaka: `34ML${plakaSuffix}`, marka: "ML Test Marka" },
        { headers },
      );
      vehicleId = vehicleResp.data.id;
    });

    it("renders page heading, description and start-training button", () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminModelManagementPage />);
      expect(screen.getByText(adminMlText.heading)).toBeInTheDocument();
      expect(screen.getByText(adminMlText.description)).toBeInTheDocument();
      expect(screen.getByText(adminMlText.startTraining)).toBeInTheDocument();
    });

    it("shows the seeded real vehicle in the selector", async () => {
      sessionStorage.setItem("access_token", token);
      // Retry-with-re-render (FleetInsights deseniyle aynı): sayfanın tek
      // GET /vehicles/ isteği transient bir 500 yerse (2026-07-07 CI
      // koşumunda yaşandı; testlerin QueryClient'ı retry:false) seçici boş
      // kalır. Taze render yeni istek atar; KALICI bir 500 iki denemede de
      // düşer — maskelenmez.
      const ATTEMPTS = 2;
      for (let attempt = 1; attempt <= ATTEMPTS; attempt += 1) {
        const view = render(<AdminModelManagementPage />);
        try {
          await waitFor(
            () => {
              expect(
                screen.getByText((content) => content.includes(plakaSuffix)),
              ).toBeInTheDocument();
            },
            { timeout: 10000 },
          );
          return;
        } catch (err) {
          view.unmount();
          if (attempt === ATTEMPTS) throw err;
        }
      }
    }, 30000);

    it("renders training-queue table title and stat cards", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminModelManagementPage />);
      expect(screen.getByText(adminMlText.table.title)).toBeInTheDocument();
      expect(
        screen.getByText(adminMlText.cards.totalTasks),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminMlText.cards.runningTasks),
      ).toBeInTheDocument();
    });

    it("triggers a real training task and shows it in the queue with the correct badge/date (real mutation)", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminModelManagementPage />);
      await waitFor(
        () => {
          expect(
            screen.getByText((content) => content.includes(plakaSuffix)),
          ).toBeInTheDocument();
        },
        { timeout: 10000 },
      );

      const select = screen.getByRole("combobox") as HTMLSelectElement;
      fireEvent.change(select, { target: { value: String(vehicleId) } });

      fireEvent.click(screen.getByText(adminMlText.startTraining));

      await waitFor(
        () => {
          expect(
            screen.getByText(
              `${adminMlText.table.vehiclePrefix} #${vehicleId}`,
            ),
          ).toBeInTheDocument();
        },
        { timeout: 10000 },
      );

      // Regression check: the real backend's durum enum is uppercase
      // ("WAITING") — the badge must still render it (previously the
      // component only matched lowercase "completed"/"running"/"failed"
      // literals, so a real WAITING/RUNNING/COMPLETED task always fell
      // through to the default badge silently).
      // The queue accumulates WAITING rows across repeated test runs
      // (no delete endpoint) — assert presence, not a single match.
      expect(screen.getAllByText("WAITING").length).toBeGreaterThanOrEqual(1);

      // Regression check: real backend sends `olusturma`, not
      // `created_at` — previously `new Date(undefined)` rendered
      // "Invalid Date".
      expect(screen.queryByText("Invalid Date")).not.toBeInTheDocument();
    }, 15000);
  },
);
