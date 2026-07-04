import { beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminNotificationsText } from "../../../resources/tr/admin";

// Modal — passthrough stub matching the original test's intent (structural
// only, avoids the heavy portal/animation implementation of the real Modal).
vi.mock("../../../components/ui/Modal", () => ({
  Modal: ({ isOpen, children, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

// sonner toast — UI-lib side effect, not part of the backend contract.
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

const backendUp = await isRealBackendReachable();

let render: typeof import("../../../test/test-utils").render;
let screen: typeof import("../../../test/test-utils").screen;
let waitFor: typeof import("../../../test/test-utils").waitFor;
let fireEvent: typeof import("../../../test/test-utils").fireEvent;
let AdminNotificationsPage: typeof import("../BildirimlerPage").default;

describe.skipIf(!backendUp)(
  "AdminNotificationsPage / BildirimlerPage (real backend)",
  () => {
    let token = "";
    let roleId1 = 0;
    let roleId2 = 0;
    const suffix = Date.now();

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
      ({ render, screen, waitFor, fireEvent } = await import(
        "../../../test/test-utils"
      ));
      AdminNotificationsPage = (await import("../BildirimlerPage")).default;

      token = await loginAsAdmin();
      const headers = { Authorization: `Bearer ${token}` };

      const role1 = await axios.post(
        `${REAL_BACKEND_URL}/admin/roles/`,
        { ad: `notif-role-a-${suffix}`, yetkiler: { sefer_goruntule: true } },
        { headers },
      );
      roleId1 = role1.data.id;
      const role2 = await axios.post(
        `${REAL_BACKEND_URL}/admin/roles/`,
        { ad: `notif-role-b-${suffix}`, yetkiler: { sefer_goruntule: true } },
        { headers },
      );
      roleId2 = role2.data.id;
    });

    it("renders page heading, description, add-rule button and section title", () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminNotificationsPage />);
      expect(
        screen.getByText(adminNotificationsText.heading),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminNotificationsText.description),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminNotificationsText.addRule),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminNotificationsText.sectionTitle),
      ).toBeInTheDocument();
    });

    it("opens modal when add rule button clicked, with olay-tipi input and channel toggles", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminNotificationsPage />);
      fireEvent.click(screen.getByText(adminNotificationsText.addRule));
      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
        expect(screen.getByText("Yeni Bildirim Kuralı")).toBeInTheDocument();
      });
      expect(screen.getByPlaceholderText(/FUEL_ANOMALY/)).toBeInTheDocument();
      expect(
        screen.getAllByRole("button", { name: "EMAIL" }).length,
      ).toBeGreaterThan(0);
    });

    it("shows form validation error when submitting with no olay_tipi", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminNotificationsPage />);
      fireEvent.click(screen.getByText(adminNotificationsText.addRule));
      await waitFor(() => screen.getByRole("dialog"));
      const submitBtn = screen.getByRole("button", { name: "Oluştur" });
      fireEvent.click(submitBtn);
      await waitFor(() => {
        expect(screen.getByText("Olay tipi zorunludur")).toBeInTheDocument();
      });
    });

    describe("with real seeded notification rules", () => {
      const eventType1 = `FUEL_ANOMALY_${suffix}`;
      const eventType2 = `TRIP_DELAY_${suffix}`;

      beforeAll(async () => {
        const headers = { Authorization: `Bearer ${token}` };
        await axios.post(
          `${REAL_BACKEND_URL}/admin/notifications/rules`,
          {
            olay_tipi: eventType1,
            kanallar: ["EMAIL", "PUSH"],
            alici_rol_id: roleId1,
            aktif: true,
          },
          { headers },
        );
        await axios.post(
          `${REAL_BACKEND_URL}/admin/notifications/rules`,
          {
            olay_tipi: eventType2,
            kanallar: ["SMS"],
            alici_rol_id: roleId2,
            aktif: false,
          },
          { headers },
        );
      });

      it("shows notification rules after loading, with channel badges", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminNotificationsPage />);
        await waitFor(
          () => {
            expect(screen.getByText(eventType1)).toBeInTheDocument();
            expect(screen.getByText(eventType2)).toBeInTheDocument();
          },
          { timeout: 10000 },
        );
        expect(screen.getAllByText("EMAIL").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("PUSH").length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText("SMS").length).toBeGreaterThanOrEqual(1);
      });

      it("shows active/passive status badges and role prefix", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminNotificationsPage />);
        await waitFor(
          () => expect(screen.getByText(eventType1)).toBeInTheDocument(),
          { timeout: 10000 },
        );
        // The shared test DB has no DELETE endpoint for notification rules,
        // so rules created by earlier runs of this file accumulate — use
        // getAllByText (>=1) rather than asserting a single match.
        expect(
          screen.getAllByText(adminNotificationsText.statuses.active).length,
        ).toBeGreaterThanOrEqual(1);
        expect(
          screen.getAllByText(adminNotificationsText.statuses.passive).length,
        ).toBeGreaterThanOrEqual(1);
        expect(
          screen.getByText(`${adminNotificationsText.rolePrefix} #${roleId1}`),
        ).toBeInTheDocument();
      });

      it("shows dash for missing template (create endpoint never stores sablon_icerik)", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminNotificationsPage />);
        await waitFor(
          () => expect(screen.getByText(eventType1)).toBeInTheDocument(),
          { timeout: 10000 },
        );
        const cells = screen.getAllByText("-");
        expect(cells.length).toBeGreaterThan(0);
      });

      it("renders table headers", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminNotificationsPage />);
        await waitFor(
          () => expect(screen.getByText(eventType1)).toBeInTheDocument(),
          { timeout: 10000 },
        );
        expect(
          screen.getByText(adminNotificationsText.headers.eventType),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminNotificationsText.headers.channels),
        ).toBeInTheDocument();
        expect(
          screen.getByText(adminNotificationsText.headers.status),
        ).toBeInTheDocument();
      });

      it("creates a new rule through the modal (real mutation)", async () => {
        sessionStorage.setItem("access_token", token);
        render(<AdminNotificationsPage />);
        await waitFor(
          () => expect(screen.getByText(eventType1)).toBeInTheDocument(),
          { timeout: 10000 },
        );

        fireEvent.click(screen.getByText(adminNotificationsText.addRule));
        await waitFor(() => screen.getByRole("dialog"));

        const newEventType = `NEW_RULE_${suffix}`;
        fireEvent.change(screen.getByPlaceholderText(/FUEL_ANOMALY/), {
          target: { value: newEventType },
        });
        fireEvent.click(screen.getAllByRole("button", { name: "EMAIL" })[0]);
        fireEvent.change(screen.getByRole("combobox"), {
          target: { value: String(roleId1) },
        });
        fireEvent.click(screen.getByRole("button", { name: "Oluştur" }));

        await waitFor(
          () => {
            expect(screen.getByText(newEventType)).toBeInTheDocument();
          },
          { timeout: 10000 },
        );
      }, 15000);
    });
  },
);
