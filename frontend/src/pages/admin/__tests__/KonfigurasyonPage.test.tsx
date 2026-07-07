import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import { execSync } from "node:child_process";
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
// So this file seeds its own fixture rows in beforeAll, directly over psql
// stdin (`INSERT ... ON CONFLICT (anahtar) DO NOTHING` — idempotent, safe
// on a dirty DB), then normalises ANOMALY_Z_THRESHOLD back to 2.5 through
// the real PUT endpoint (which also invalidates the Redis config cache —
// a raw-SQL UPDATE would leave `configs:all` stale for up to 1 hour).
// Connection defaults match the CI vitest job (postgres:postgres @
// localhost:5432/lojinext_vitest, see .github/workflows/ci.yml "Create
// vitest DB + migrate"); override locally with REAL_BACKEND_PSQL, e.g.
//   REAL_BACKEND_PSQL="docker exec -i lojinext-db-1 psql -U lojinext_user -d lojinext_ci_b"
const PSQL_CMD =
  process.env.REAL_BACKEND_PSQL ||
  // CI'ın herkese açık dummy postgres servisi — gerçek secret değil.
  "psql postgresql://postgres:postgres@localhost:5432/lojinext_vitest"; // pragma: allowlist secret

function seedConfigRows(): void {
  // DO UPDATE (DO NOTHING değil): migration 0041 bu anahtarlardan ikisini
  // KENDİ açıklama/yeniden_baslat değerleriyle zaten seed'liyor; DO NOTHING
  // ile testin assert ettiği fixture metinleri hiç yazılmıyor ve testler
  // migration'lı her DB'de düşüyordu (CI run 28873564005'te canlı). Test,
  // kendi fixture durumunu DAYATMALI ki migration içeriği serbestçe
  // evrilebilsin.
  const sql = `
    INSERT INTO sistem_konfig
      (anahtar, deger, tip, birim, min_deger, max_deger, grup, aciklama, yeniden_baslat)
    VALUES
      ('ANOMALY_Z_THRESHOLD', '2.5'::jsonb, 'float', 'σ', 1, 5,
       'anomali', 'Anomali tespiti icin Z-skoru esigi', false),
      ('VEHICLE_AGE_DEGRADATION_RATE', '0.01'::jsonb, 'float', NULL, NULL, NULL,
       'ml', 'Arac yasi basina yillik tuketim artis orani', true),
      ('LOG_LEVEL', '"INFO"'::jsonb, 'string', NULL, NULL, NULL,
       'sistem', 'Uygulama log seviyesi', false)
    ON CONFLICT (anahtar) DO UPDATE SET
      deger = EXCLUDED.deger,
      tip = EXCLUDED.tip,
      birim = EXCLUDED.birim,
      min_deger = EXCLUDED.min_deger,
      max_deger = EXCLUDED.max_deger,
      grup = EXCLUDED.grup,
      aciklama = EXCLUDED.aciklama,
      yeniden_baslat = EXCLUDED.yeniden_baslat;
  `;
  execSync(`${PSQL_CMD} -v ON_ERROR_STOP=1`, { input: sql });
}
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
      seedConfigRows();
      // Normalise the mutated key through the REAL endpoint: guarantees
      // deger=2.5 even if a previous crashed run left 3.0 behind, and
      // invalidates the Redis "configs:all" cache so the page reads the
      // seeded rows instead of a stale cached list.
      await axios.put(
        `${REAL_BACKEND_URL}/admin/config/ANOMALY_Z_THRESHOLD`,
        { value: 2.5, reason: "test seed baseline" },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    }, 30000);

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
