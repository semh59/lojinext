import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import axios from "axios";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_URL,
} from "../../../test/real-backend";
import { adminUsersText } from "../../../resources/tr/admin";

// Mock ErrorBoundary — passthrough, not part of the backend contract.
vi.mock("../../../components/common/ErrorBoundary", () => ({
  default: ({ children }: any) => <>{children}</>,
}));

// Modal — passthrough stub (same convention as every other converted admin
// page); the real UserRolePanel form underneath is NOT mocked, so create/
// edit exercise the actual component + real HTTP calls.
vi.mock("../../../components/ui/Modal", () => ({
  Modal: ({ isOpen, children, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

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
let KullanicilarPage: typeof import("../KullanicilarPage").default;

describe.skipIf(!backendUp)("KullanicilarPage (real backend)", () => {
  let token = "";
  let roleId = 0;
  const suffix = Date.now();
  const createdUserIds: number[] = [];

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
    ({ render, screen, waitFor, fireEvent } = await import(
      "../../../test/test-utils"
    ));
    KullanicilarPage = (await import("../KullanicilarPage")).default;

    token = await loginAsAdmin();
    const headers = { Authorization: `Bearer ${token}` };
    const role = await axios.post(
      `${REAL_BACKEND_URL}/admin/roles/`,
      {
        ad: `kullanici-test-role-${suffix}`,
        yetkiler: { sefer_goruntule: true },
      },
      { headers },
    );
    roleId = role.data.id;
  });

  afterAll(async () => {
    const headers = { Authorization: `Bearer ${token}` };
    for (const id of createdUserIds) {
      try {
        await axios.delete(`${REAL_BACKEND_URL}/admin/users/${id}`, {
          headers,
        });
      } catch {
        // already deleted by the test itself — fine.
      }
    }
  });

  it("renders page heading and add-user button", () => {
    sessionStorage.setItem("access_token", token);
    render(<KullanicilarPage />);
    expect(screen.getByText(adminUsersText.heading)).toBeInTheDocument();
    expect(screen.getByText(adminUsersText.addUser)).toBeInTheDocument();
  });

  it("opens create modal in 'create' mode when add user button clicked", async () => {
    sessionStorage.setItem("access_token", token);
    render(<KullanicilarPage />);
    fireEvent.click(screen.getByText(adminUsersText.addUser));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("creates a real user through the form (real mutation)", async () => {
    sessionStorage.setItem("access_token", token);
    render(<KullanicilarPage />);
    fireEvent.click(screen.getByText(adminUsersText.addUser));
    await waitFor(() => screen.getByRole("dialog"));

    const email = `kull-test-${suffix}@example.com`;
    fireEvent.change(screen.getByPlaceholderText("user@company.com"), {
      target: { value: email },
    });
    fireEvent.change(screen.getByPlaceholderText("John Smith"), {
      target: { value: "Test Kullanici" },
    });
    fireEvent.change(screen.getByPlaceholderText(/8/), {
      target: { value: "TestPass123!" },
    });

    // The roles query fetches on mount (no `enabled` gate) — wait for the
    // seeded role's real <option> to actually be in the DOM before
    // selecting it. Setting a <select>'s value to one with no matching
    // <option> is silently ignored by the DOM, which previously produced a
    // false negative here (rol_id stayed "", submit silently no-opped on
    // the "role required" validation with the modal still open).
    const roleName = `kullanici-test-role-${suffix}`;
    await waitFor(() => {
      expect(
        screen.getByRole("option", { name: roleName }),
      ).toBeInTheDocument();
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: String(roleId) },
    });

    fireEvent.click(screen.getByRole("button", { name: /Oluştur|Create/ }));

    await waitFor(
      () => {
        expect(screen.getByText(email)).toBeInTheDocument();
      },
      { timeout: 10000 },
    );

    const resp = await axios.get(`${REAL_BACKEND_URL}/admin/users/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const created = resp.data.find((u: { email: string }) => u.email === email);
    expect(created).toBeTruthy();
    createdUserIds.push(created.id);
  }, 15000);

  describe("with the seeded real user", () => {
    it("shows the user in the list with full name and active status", async () => {
      sessionStorage.setItem("access_token", token);
      render(<KullanicilarPage />);
      await waitFor(
        () => {
          expect(screen.getByText("Test Kullanici")).toBeInTheDocument();
        },
        { timeout: 10000 },
      );
      expect(
        screen.getAllByText(adminUsersText.statuses.active).length,
      ).toBeGreaterThanOrEqual(1);
    });

    it("opens edit modal in 'edit' mode when edit button clicked", async () => {
      sessionStorage.setItem("access_token", token);
      render(<KullanicilarPage />);
      await waitFor(
        () => expect(screen.getByText("Test Kullanici")).toBeInTheDocument(),
        { timeout: 10000 },
      );
      const editBtns = screen.getAllByRole("button", {
        name: adminUsersText.actions.edit,
      });
      fireEvent.click(editBtns[0]);
      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
      });
      // Edit form is pre-filled from the real user record.
      const emailInput = screen.getByPlaceholderText(
        "user@company.com",
      ) as HTMLInputElement;
      expect(emailInput.value).toContain(`kull-test-${suffix}`);
    });

    it("opens delete confirmation and calls the real DELETE endpoint", async () => {
      sessionStorage.setItem("access_token", token);
      // Create a disposable second user just for this destructive test so
      // the "shows the user" / "opens edit modal" tests above (which run
      // first) keep seeing the original seeded user.
      const headers = { Authorization: `Bearer ${token}` };
      const disposableEmail = `kull-test-disposable-${suffix}@example.com`;
      const created = await axios.post(
        `${REAL_BACKEND_URL}/admin/users/`,
        {
          email: disposableEmail,
          ad_soyad: "Disposable User",
          rol_id: roleId,
          sifre: "TestPass123!",
        },
        { headers },
      );
      const disposableId = created.data.id as number;

      render(<KullanicilarPage />);
      await waitFor(
        () => expect(screen.getByText("Disposable User")).toBeInTheDocument(),
        { timeout: 10000 },
      );
      const row = screen.getByText("Disposable User").closest("tr")!;
      const deleteBtn = row.querySelector(
        'button[aria-label="Sil"]',
      ) as HTMLElement;
      fireEvent.click(deleteBtn);
      await waitFor(() => {
        expect(screen.getByText("Kullanıcıyı Sil")).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText("Evet, Sil"));

      await waitFor(
        () => {
          expect(screen.queryByText("Disposable User")).not.toBeInTheDocument();
        },
        { timeout: 10000 },
      );

      const resp = await axios.get(`${REAL_BACKEND_URL}/admin/users/`, {
        headers,
      });
      expect(
        resp.data.find((u: { id: number }) => u.id === disposableId),
      ).toBeUndefined();
    }, 15000);
  });
});
