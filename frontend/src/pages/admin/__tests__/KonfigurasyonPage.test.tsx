import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminConfigurationText } from "../../../resources/tr/admin";

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
let within: typeof import("../../../test/test-utils").within;
let AdminConfigurationPage: typeof import("../KonfigurasyonPage").default;

// Row order from GET /admin/config is not guaranteed stable (no ORDER BY
// in the backend query) — never assume "ANOMALY_Z_THRESHOLD" is inputs[0].
// Locate its row by the key label, then scope queries to that row only.
function getConfigRow(anahtar: string): HTMLElement {
  const label = screen.getByText(anahtar);
  const row = label.closest(".grid") as HTMLElement | null;
  if (!row) throw new Error(`config row for ${anahtar} not found`);
  return row;
}

// The `sistem_konfig` table has NO create endpoint (only GET /admin/config
// and PUT /admin/config/{key} — see app/api/v1/endpoints/admin_config.py).
// Rows must exist in the DB already; there is no HTTP way to seed them.
// Seeded once, directly in the shared throwaway Postgres (tierf_slice3_pg),
// via `docker exec ... psql ... INSERT ... ON CONFLICT (anahtar) DO
// NOTHING` — idempotent across repeated test runs, matching the fixed
// keys/values this file asserts against (ANOMALY_Z_THRESHOLD=2.5,
// VEHICLE_AGE_DEGRADATION_RATE=0.01 restart-required, LOG_LEVEL="INFO").
describe.skipIf(!backendUp)(
  "AdminConfigurationPage / KonfigurasyonPage (real backend)",
  () => {
    let token = "";

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
      ({ render, screen, waitFor, fireEvent, within } = await import(
        "../../../test/test-utils"
      ));
      AdminConfigurationPage = (await import("../KonfigurasyonPage")).default;
      token = await loginAsAdmin();
    });

    afterAll(async () => {
      // Restore the mutated key so re-runs of this file (and any other
      // file reading this shared config row) see the fixture's baseline.
      await axios.put(
        `${REAL_BACKEND_URL}/admin/config/ANOMALY_Z_THRESHOLD`,
        { value: 2.5, reason: "test reset" },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    });

    it("renders page heading and description after data loads", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () => {
          expect(
            screen.getByText(adminConfigurationText.heading),
          ).toBeInTheDocument();
          expect(
            screen.getByText(adminConfigurationText.description),
          ).toBeInTheDocument();
        },
        { timeout: 10000 },
      );
    });

    it("renders config keys, descriptions and unit label after loading", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () => {
          expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument();
          expect(
            screen.getByText("VEHICLE_AGE_DEGRADATION_RATE"),
          ).toBeInTheDocument();
          expect(screen.getByText("LOG_LEVEL")).toBeInTheDocument();
        },
        { timeout: 10000 },
      );
      expect(
        screen.getByText("Anomali tespiti icin Z-skoru esigi"),
      ).toBeInTheDocument();
      expect(screen.getByText("σ")).toBeInTheDocument();
    });

    it("shows group section headers with suffix", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () => {
          expect(screen.getAllByText(/ayarları/i).length).toBeGreaterThan(0);
        },
        { timeout: 10000 },
      );
    });

    it("renders 'yeniden başlat' badge for configs that need restart", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () => {
          const reloadBadges = screen.getAllByText(
            adminConfigurationText.reloadRequired,
          );
          expect(reloadBadges.length).toBeGreaterThan(0);
        },
        { timeout: 10000 },
      );
    });

    it("renders save buttons for each config (disabled until changed)", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () =>
          expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument(),
        { timeout: 10000 },
      );
      const saveBtns = screen.getAllByRole("button", {
        name: adminConfigurationText.actions.save,
      });
      expect(saveBtns.length).toBeGreaterThanOrEqual(3);

      const row = within(getConfigRow("ANOMALY_Z_THRESHOLD"));
      await waitFor(() => {
        expect(
          row.getByRole("button", {
            name: adminConfigurationText.actions.save,
          }),
        ).toBeDisabled();
      });
    });

    it("save button becomes enabled when value is changed", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () =>
          expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument(),
        { timeout: 10000 },
      );
      const row = within(getConfigRow("ANOMALY_Z_THRESHOLD"));
      fireEvent.change(
        row.getByPlaceholderText(adminConfigurationText.valuePlaceholder),
        { target: { value: "3.0" } },
      );
      await waitFor(() => {
        expect(
          row.getByRole("button", {
            name: adminConfigurationText.actions.save,
          }),
        ).not.toBeDisabled();
      });
    });

    it("saves a real config change through PUT /admin/config/{key}", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminConfigurationPage />);
      await waitFor(
        () =>
          expect(screen.getByText("ANOMALY_Z_THRESHOLD")).toBeInTheDocument(),
        { timeout: 10000 },
      );
      const row = within(getConfigRow("ANOMALY_Z_THRESHOLD"));
      const input = row.getByPlaceholderText(
        adminConfigurationText.valuePlaceholder,
      );
      fireEvent.change(input, { target: { value: "3.0" } });
      const saveBtn = row.getByRole("button", {
        name: adminConfigurationText.actions.save,
      });
      await waitFor(() => expect(saveBtn).not.toBeDisabled());
      fireEvent.click(saveBtn);

      // handleSave never resets localValues on its own — the input would
      // keep showing "3" even if the PUT silently failed (onError doesn't
      // touch localValues), so checking the input's displayed value alone
      // is not proof of a successful round-trip. Poll the real endpoint
      // directly instead.
      await waitFor(
        async () => {
          const resp = await axios.get(`${REAL_BACKEND_URL}/admin/config`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const updated = resp.data.find(
            (c: { anahtar: string }) => c.anahtar === "ANOMALY_Z_THRESHOLD",
          );
          expect(updated.deger).toBe(3.0);
        },
        { timeout: 10000 },
      );
    }, 15000);
  },
);
