import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../../test/test-utils";
import KullanicilarPage from "../KullanicilarPage";
import { adminUsersText } from "../../../resources/tr/admin";

// Mock admin-service
vi.mock("../../../api/admin", () => ({
  adminUsersApi: {
    getAll: vi.fn(),
    create: vi.fn().mockResolvedValue({
      id: 99,
      email: "new@test.com",
      ad_soyad: "Yeni Kullanici",
      aktif: true,
    }),
    update: vi.fn().mockResolvedValue({
      id: 1,
      email: "test@test.com",
      ad_soyad: "Test User",
      aktif: true,
    }),
    delete: vi.fn().mockResolvedValue(undefined),
  },
  adminRolesApi: {
    getAll: vi.fn().mockResolvedValue([
      { id: 1, ad: "admin", yetkiler: {} },
      { id: 2, ad: "user", yetkiler: {} },
    ]),
  },
}));

// Mock usePageTitle
vi.mock("../../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// Mock ErrorBoundary
vi.mock("../../../components/common/ErrorBoundary", () => ({
  default: ({ children }: any) => <>{children}</>,
}));

// Mock UserRolePanel to simplify form testing
vi.mock("../../../components/admin/UserRolePanel", () => ({
  UserRolePanel: ({ onSubmit, onClose, modalMode, formError }: any) => (
    <div data-testid="user-role-panel">
      {formError && <p data-testid="form-error">{formError}</p>}
      <span data-testid="modal-mode">{modalMode}</span>
      <button onClick={onSubmit} data-testid="panel-submit">
        Kaydet
      </button>
      <button onClick={onClose} data-testid="panel-close">
        Kapat
      </button>
    </div>
  ),
}));

// Mock Modal
vi.mock("../../../components/ui/Modal", () => ({
  Modal: ({ isOpen, children, title }: any) =>
    isOpen ? (
      <div role="dialog" aria-label={title}>
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

// Mock sonner
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const MOCK_USERS = [
  {
    id: 1,
    email: "admin@loji.com",
    ad_soyad: "Admin Kullanici",
    aktif: true,
    rol_id: 1,
    son_giris: "2026-06-01T10:00:00",
    rol: { id: 1, ad: "admin", yetkiler: {} },
  },
  {
    id: 2,
    email: "user@loji.com",
    ad_soyad: "Normal Kullanici",
    aktif: false,
    rol_id: 2,
    son_giris: null,
    rol: { id: 2, ad: "user", yetkiler: {} },
  },
];

describe("KullanicilarPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { adminUsersApi } = await import("../../../api/admin");
    (adminUsersApi.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK_USERS,
    );
  });

  it("renders page heading", async () => {
    render(<KullanicilarPage />);
    expect(screen.getByText(adminUsersText.heading)).toBeInTheDocument();
  });

  it("renders add user button", async () => {
    render(<KullanicilarPage />);
    expect(screen.getByText(adminUsersText.addUser)).toBeInTheDocument();
  });

  it("shows user list after loading", async () => {
    render(<KullanicilarPage />);
    await waitFor(() => {
      expect(screen.getByText("admin@loji.com")).toBeInTheDocument();
      expect(screen.getByText("user@loji.com")).toBeInTheDocument();
    });
  });

  it("shows user full names", async () => {
    render(<KullanicilarPage />);
    await waitFor(() => {
      expect(screen.getByText("Admin Kullanici")).toBeInTheDocument();
      expect(screen.getByText("Normal Kullanici")).toBeInTheDocument();
    });
  });

  it("shows active/passive status badges", async () => {
    render(<KullanicilarPage />);
    await waitFor(() => {
      expect(
        screen.getByText(adminUsersText.statuses.active),
      ).toBeInTheDocument();
      expect(
        screen.getByText(adminUsersText.statuses.passive),
      ).toBeInTheDocument();
    });
  });

  it("shows empty state when no users", async () => {
    const { adminUsersApi } = await import("../../../api/admin");
    (adminUsersApi.getAll as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<KullanicilarPage />);
    await waitFor(() => {
      expect(screen.getByText(adminUsersText.empty)).toBeInTheDocument();
    });
  });

  it("opens create modal when add user button clicked", async () => {
    render(<KullanicilarPage />);
    const addBtn = screen.getByText(adminUsersText.addUser);
    fireEvent.click(addBtn);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText("Yeni Kullanıcı Oluştur")).toBeInTheDocument();
    });
  });

  it("modal mode is 'create' when adding new user", async () => {
    render(<KullanicilarPage />);
    fireEvent.click(screen.getByText(adminUsersText.addUser));
    await waitFor(() => {
      expect(screen.getByTestId("modal-mode")).toHaveTextContent("create");
    });
  });

  it("opens edit modal when edit button clicked", async () => {
    render(<KullanicilarPage />);
    await waitFor(() =>
      expect(screen.getByText("admin@loji.com")).toBeInTheDocument(),
    );
    const editBtns = screen.getAllByRole("button", {
      name: adminUsersText.actions.edit,
    });
    fireEvent.click(editBtns[0]);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByTestId("modal-mode")).toHaveTextContent("edit");
    });
  });

  it("opens delete confirmation dialog when delete button clicked", async () => {
    render(<KullanicilarPage />);
    await waitFor(() =>
      expect(screen.getByText("admin@loji.com")).toBeInTheDocument(),
    );
    const deleteBtns = screen.getAllByRole("button", { name: "Sil" });
    fireEvent.click(deleteBtns[0]);
    await waitFor(() => {
      expect(screen.getByText("Kullanıcıyı Sil")).toBeInTheDocument();
    });
  });

  it("calls delete API when confirmed", async () => {
    const { adminUsersApi } = await import("../../../api/admin");
    render(<KullanicilarPage />);
    await waitFor(() =>
      expect(screen.getByText("admin@loji.com")).toBeInTheDocument(),
    );
    const deleteBtns = screen.getAllByRole("button", { name: "Sil" });
    fireEvent.click(deleteBtns[0]);
    await waitFor(() =>
      expect(screen.getByText("Evet, Sil")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Evet, Sil"));
    // The delete flow fires the mutation (mutationFn = adminUsersApi.delete).
    // React Query forwards the variable internally; assert the call happened.
    await waitFor(() => {
      expect(adminUsersApi.delete).toHaveBeenCalledTimes(1);
    });
  });

  it("shows loading state initially", async () => {
    const { adminUsersApi } = await import("../../../api/admin");
    (adminUsersApi.getAll as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise(() => {}),
    );
    render(<KullanicilarPage />);
    expect(screen.getByText(adminUsersText.loading)).toBeInTheDocument();
  });
});
