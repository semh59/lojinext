import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminMaintenanceText } from "../../../resources/tr/admin";
import { maintenancePredictionsText } from "../../../resources/tr/maintenancePredictions";

// Mock notification context — not wrapped by test-utils' AllTheProviders,
// same as every other converted admin page.
vi.mock("../../../context/NotificationContext", () => ({
  useNotify: () => ({ notify: vi.fn() }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// Heavy sub-components unrelated to this page's own queries — kept as
// structural stubs (their own real-backend tests exist elsewhere).
vi.mock("../../../components/admin/maintenance/PredictionsTable", () => ({
  PredictionsTable: () => (
    <div data-testid="predictions-table">PredictionsTable</div>
  ),
}));
vi.mock("../../../components/admin/maintenance/MaintenanceCalendar", () => ({
  MaintenanceCalendar: () => (
    <div data-testid="maintenance-calendar">MaintenanceCalendar</div>
  ),
}));

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let waitFor: typeof import("../../../test/test-utils").waitFor;
let fireEvent: typeof import("../../../test/test-utils").fireEvent;
let AdminMaintenancePage: typeof import("../BakimPage").default;

describe.skipIf(!backendUp)(
  "AdminMaintenancePage / BakimPage (real backend)",
  () => {
    let token = "";
    let vehicleId = 0;

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
      ({ render, screen, waitFor, fireEvent } = await import(
        "../../../test/test-utils"
      ));
      AdminMaintenancePage = (await import("../BakimPage")).default;

      token = await loginAsAdmin();
      const authHeaders = { Authorization: `Bearer ${token}` };

      const plaka = `34BM${Date.now().toString().slice(-4)}`;
      const vehicleResp = await axios.post(
        `${REAL_BACKEND_URL}/vehicles/`,
        { plaka, marka: "Bakım Test Marka" },
        { headers: authHeaders },
      );
      vehicleId = vehicleResp.data.id;
    });

    it("renders page heading, description and tabs", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminMaintenancePage />);
      expect(
        screen.getByText(adminMaintenanceText.heading),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminMaintenanceText.description),
      ).toBeInTheDocument();
      expect(
        screen.getByText(maintenancePredictionsText.tabs.history),
      ).toBeInTheDocument();
      expect(
        screen.getByText(maintenancePredictionsText.tabs.list),
      ).toBeInTheDocument();
      expect(
        screen.getByText(maintenancePredictionsText.tabs.calendar),
      ).toBeInTheDocument();
    });

    it("shows history tab content by default (section title visible)", () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminMaintenancePage />);
      expect(
        screen.getByText(adminMaintenanceText.sectionTitle),
      ).toBeInTheDocument();
    });

    it("shows empty state when there are no open alerts (cold-start test DB)", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminMaintenancePage />);
      await waitFor(
        () => {
          expect(
            screen.getByText(adminMaintenanceText.empty),
          ).toBeInTheDocument();
        },
        { timeout: 10000 },
      );
    });

    it("switches to predictions tab and shows PredictionsTable", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminMaintenancePage />);
      const predictionsTab = screen.getByText(
        maintenancePredictionsText.tabs.list,
      );
      fireEvent.click(predictionsTab);
      await waitFor(() => {
        expect(screen.getByTestId("predictions-table")).toBeInTheDocument();
      });
      expect(
        screen.queryByText(adminMaintenanceText.sectionTitle),
      ).not.toBeInTheDocument();
    });

    it("switches to calendar tab and shows MaintenanceCalendar", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminMaintenancePage />);
      const calendarTab = screen.getByText(
        maintenancePredictionsText.tabs.calendar,
      );
      fireEvent.click(calendarTab);
      await waitFor(() => {
        expect(screen.getByTestId("maintenance-calendar")).toBeInTheDocument();
      });
    });

    describe("with real seeded maintenance alerts", () => {
      let bakimId1 = 0;
      let bakimId2 = 0;

      beforeAll(async () => {
        const authHeaders = { Authorization: `Bearer ${token}` };
        const create = async (body: Record<string, unknown>) => {
          const resp = await axios.post(
            `${REAL_BACKEND_URL}/admin/maintenance/`,
            { arac_id: vehicleId, maliyet: 100, detaylar: "test", ...body },
            { headers: authHeaders },
          );
          return resp.data.id as number;
        };
        // get_upcoming_maintenance only returns bakim_tarihi >= now (backend
        // design, see app/tests/unit/test_coverage_boost.py) — every real
        // alert is UPCOMING, never OVERDUE. Seed two future-dated records.
        bakimId1 = await create({
          bakim_tipi: "PERIYODIK",
          km_bilgisi: 150000,
          bakim_tarihi: "2027-08-01T00:00:00Z",
        });
        bakimId2 = await create({
          bakim_tipi: "ARIZA",
          km_bilgisi: 160000,
          bakim_tarihi: "2027-09-01T00:00:00Z",
        });
      });

      afterAll(async () => {
        // Leave the shared test DB clean regardless of which assertions ran —
        // otherwise these UPCOMING (year 2027) alerts would linger and break
        // every other admin test file's "empty state" assumption.
        const authHeaders = { Authorization: `Bearer ${token}` };
        for (const id of [bakimId1, bakimId2]) {
          if (!id) continue;
          try {
            await axios.patch(
              `${REAL_BACKEND_URL}/admin/maintenance/${id}/complete`,
              {},
              { headers: authHeaders },
            );
          } catch {
            // already completed by the test itself — fine.
          }
        }
      });

      it("shows the seeded alerts with correct vehicle id, type and UPCOMING badge", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminMaintenancePage />);
        await waitFor(
          () => {
            const vehicleCells = screen.getAllByText(
              `${adminMaintenanceText.vehiclePrefix} #${vehicleId}`,
            );
            expect(vehicleCells.length).toBeGreaterThanOrEqual(2);
          },
          { timeout: 10000 },
        );
        expect(screen.getByText("Periyodik")).toBeInTheDocument();
        expect(screen.getByText("Arıza")).toBeInTheDocument();
        // Regression check: alert.vade_durumu (backend contract) must map to
        // the "Yaklaşıyor" badge — previously read the nonexistent
        // alert.durum field and always rendered the default badge instead.
        const upcomingBadges = screen.getAllByText(
          adminMaintenanceText.statusLabels.upcoming,
        );
        expect(upcomingBadges.length).toBeGreaterThanOrEqual(2);
      }, 15000);

      it("renders table headers", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminMaintenancePage />);
        await waitFor(() =>
          expect(screen.getByText("Periyodik")).toBeInTheDocument(),
        );
        expect(
          screen.getByText(adminMaintenanceText.headers.vehicle),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminMaintenanceText.headers.maintenanceType),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminMaintenanceText.headers.status),
        ).toBeInTheDocument();
      });

      it("marks an alert complete when the complete button is clicked (real mutation)", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminMaintenancePage />);
        await waitFor(() =>
          expect(screen.getByText("Periyodik")).toBeInTheDocument(),
        );
        const completeBtns = screen.getAllByText(
          adminMaintenanceText.completeAction,
        );
        fireEvent.click(completeBtns[0]);

        // The row for the completed alert (Periyodik) disappears once the
        // mutation succeeds and the query is invalidated + refetched; the
        // other seeded alert (Arıza) stays.
        await waitFor(
          () => {
            expect(screen.queryByText("Periyodik")).not.toBeInTheDocument();
          },
          { timeout: 10000 },
        );
        expect(screen.getByText("Arıza")).toBeInTheDocument();

        const resp = await axios.get(
          `${REAL_BACKEND_URL}/admin/maintenance/alerts`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        const remainingIds = resp.data.map((a: { id: number }) => a.id);
        expect(remainingIds).not.toContain(bakimId1);
        expect(remainingIds).toContain(bakimId2);
      });
    });
  },
);
