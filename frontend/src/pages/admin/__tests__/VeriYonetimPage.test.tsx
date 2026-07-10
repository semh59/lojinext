import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { execSync } from "node:child_process";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminDataManagementText } from "../../../resources/tr/admin";

// Regression test for a real bug: mapImportStatus() compared job.durum
// against "tamamlandi"/"hata"/"geri_alindi", but the backend
// (IceriAktarimGecmisi / import_service.py) writes "COMPLETED" /
// "COMPLETED_WITH_ERRORS" / "ROLLED_BACK" — no case ever matched, so
// every job's badge silently showed the default "İşleniyor" regardless
// of its real status. Fixed to match the real wire values.

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
let within: typeof import("../../../test/test-utils").within;
let AdminDataManagementPage: typeof import("../VeriYonetimPage").default;

// iceri_aktarim_gecmisi has no admin create endpoint (only GET history +
// POST rollback) — same seeding-gap pattern as sistem_konfig in
// KonfigurasyonPage.test.tsx, so rows are seeded directly over psql.
const PSQL_CMD =
  process.env.REAL_BACKEND_PSQL ||
  "psql postgresql://postgres:postgres@localhost:5432/lojinext_vitest"; // pragma: allowlist secret

const MARKER = "vitest-veriyonetim-regression";

function seedImportRows(): void {
  const sql = `
    DELETE FROM iceri_aktarim_gecmisi WHERE dosya_adi LIKE '${MARKER}%';
    INSERT INTO iceri_aktarim_gecmisi
      (dosya_adi, aktarim_tipi, durum, toplam_kayit, basarili_kayit, hatali_kayit)
    VALUES
      ('${MARKER}-completed.xlsx', 'arac', 'COMPLETED', 10, 10, 0),
      ('${MARKER}-with-errors.xlsx', 'surucu', 'COMPLETED_WITH_ERRORS', 10, 7, 3),
      ('${MARKER}-rolled-back.xlsx', 'sefer', 'ROLLED_BACK', 5, 5, 0);
  `;
  execSync(`${PSQL_CMD} -v ON_ERROR_STOP=1`, { input: sql });
}

function cleanupImportRows(): void {
  execSync(`${PSQL_CMD} -v ON_ERROR_STOP=1`, {
    input: `DELETE FROM iceri_aktarim_gecmisi WHERE dosya_adi LIKE '${MARKER}%';`,
  });
}

describe.skipIf(!backendUp)(
  "AdminDataManagementPage / VeriYonetimPage (real backend)",
  () => {
    let token = "";

    beforeAll(async () => {
      vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
      ({ render, screen, waitFor, within } = await import(
        "../../../test/test-utils"
      ));
      AdminDataManagementPage = (await import("../VeriYonetimPage")).default;
      token = await loginAsAdmin();
      seedImportRows();
    }, 30000);

    afterAll(() => {
      cleanupImportRows();
    });

    it("maps COMPLETED/COMPLETED_WITH_ERRORS/ROLLED_BACK to their real badges, not the default", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminDataManagementPage />);

      await waitFor(
        () => {
          expect(
            screen.getByText(`${MARKER}-completed.xlsx`),
          ).toBeInTheDocument();
        },
        { timeout: 10000 },
      );

      const completedRow = screen
        .getByText(`${MARKER}-completed.xlsx`)
        .closest("tr") as HTMLElement;
      expect(
        within(completedRow).getByText(
          adminDataManagementText.statusLabels.completed,
        ),
      ).toBeInTheDocument();

      const erroredRow = screen
        .getByText(`${MARKER}-with-errors.xlsx`)
        .closest("tr") as HTMLElement;
      expect(
        within(erroredRow).getByText(
          adminDataManagementText.statusLabels.error,
        ),
      ).toBeInTheDocument();

      const rolledBackRow = screen
        .getByText(`${MARKER}-rolled-back.xlsx`)
        .closest("tr") as HTMLElement;
      expect(
        within(rolledBackRow).getByText(
          adminDataManagementText.statusLabels.rolledBack,
        ),
      ).toBeInTheDocument();

      // None of the 3 seeded rows should show the generic default badge —
      // that was the bug (every row fell through to it regardless of durum).
      expect(
        within(completedRow).queryByText(
          adminDataManagementText.statusLabels.default,
        ),
      ).not.toBeInTheDocument();
      expect(
        within(erroredRow).queryByText(
          adminDataManagementText.statusLabels.default,
        ),
      ).not.toBeInTheDocument();
      expect(
        within(rolledBackRow).queryByText(
          adminDataManagementText.statusLabels.default,
        ),
      ).not.toBeInTheDocument();
    });

    it("disables the rollback button only for an already-rolled-back job", async () => {
      sessionStorage.setItem("access_token", token);
      render(<AdminDataManagementPage />);

      await waitFor(() =>
        expect(
          screen.getByText(`${MARKER}-completed.xlsx`),
        ).toBeInTheDocument(),
      );

      const completedRow = screen
        .getByText(`${MARKER}-completed.xlsx`)
        .closest("tr") as HTMLElement;
      expect(
        within(completedRow).getByRole("button", {
          name: adminDataManagementText.rollbackAction,
        }),
      ).not.toBeDisabled();

      const rolledBackRow = screen
        .getByText(`${MARKER}-rolled-back.xlsx`)
        .closest("tr") as HTMLElement;
      expect(
        within(rolledBackRow).getByRole("button", {
          name: adminDataManagementText.rollbackAction,
        }),
      ).toBeDisabled();
    });
  },
);
