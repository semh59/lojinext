import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "../../test/test-utils";
import ProfilePage from "../ProfilePage";

// Mock axiosInstance
vi.mock("../../services/api/axios-instance", () => ({
  default: {
    patch: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}));

// Mock usePageTitle
vi.mock("../../hooks/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

// Mock PushNotificationToggle to simplify
vi.mock("../../components/profile/PushNotificationToggle", () => ({
  PushNotificationToggle: () => (
    <div data-testid="push-notification-toggle">Push Toggle</div>
  ),
}));

// Mock sonner toast
vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock AuthContext to provide a user
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      username: "test@example.com",
      email: "test@example.com",
      full_name: "Ahmet Yılmaz",
      role: "admin",
      is_active: true,
      last_login: "2026-06-01T10:00:00",
      created_at: "2025-01-01T00:00:00",
      son_giris_ip: "192.168.1.1",
    },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    error: null,
    hasPermission: () => true,
  }),
  AuthProvider: ({ children }: any) => <>{children}</>,
}));

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page heading", () => {
    render(<ProfilePage />);
    expect(screen.getByText("Profilim")).toBeInTheDocument();
  });

  it("renders user name and email in identity hero", () => {
    render(<ProfilePage />);
    expect(screen.getByText("Ahmet Yılmaz")).toBeInTheDocument();
    // email appears in the profile info
    expect(
      screen.getAllByText("test@example.com").length,
    ).toBeGreaterThanOrEqual(1);
  });

  it("renders role badge", () => {
    render(<ProfilePage />);
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("renders user initials in avatar", () => {
    render(<ProfilePage />);
    expect(screen.getByText("AY")).toBeInTheDocument();
  });

  it("renders push notification toggle", () => {
    render(<ProfilePage />);
    expect(screen.getByTestId("push-notification-toggle")).toBeInTheDocument();
  });

  it("renders profile info form card", () => {
    render(<ProfilePage />);
    expect(screen.getByText("Profil Bilgileri")).toBeInTheDocument();
    expect(
      screen.getByText("Ad soyad bilginizi güncelleyin"),
    ).toBeInTheDocument();
  });

  it("profile form has email (readonly) and ad_soyad input", () => {
    render(<ProfilePage />);
    const emailInput = screen.getByDisplayValue("test@example.com");
    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute("readOnly");

    const adSoyadInput = screen.getByDisplayValue("Ahmet Yılmaz");
    expect(adSoyadInput).toBeInTheDocument();
  });

  it("renders change password form card", () => {
    render(<ProfilePage />);
    expect(screen.getByText("Şifre Değiştir")).toBeInTheDocument();
    expect(screen.getByText("Şifremi Güncelle")).toBeInTheDocument();
  });

  it("profile form save button calls axiosInstance.patch on submit", async () => {
    const axiosInstance = await import("../../services/api/axios-instance");
    render(<ProfilePage />);
    const saveBtn = screen.getByText("Kaydet");
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(axiosInstance.default.patch).toHaveBeenCalledWith(
        "/users/me",
        expect.objectContaining({ ad_soyad: "Ahmet Yılmaz" }),
      );
    });
  });

  it("shows validation error when ad_soyad is too short", async () => {
    render(<ProfilePage />);
    const adSoyadInput = screen.getByDisplayValue("Ahmet Yılmaz");
    fireEvent.change(adSoyadInput, { target: { value: "X" } });
    fireEvent.click(screen.getByText("Kaydet"));
    await waitFor(() => {
      expect(
        screen.getByText("İsim en az 2 karakter olmalıdır."),
      ).toBeInTheDocument();
    });
  });

  it("password toggle button toggles visibility", () => {
    render(<ProfilePage />);
    const toggleBtns = screen.getAllByRole("button", {
      name: /Şifreyi göster/i,
    });
    expect(toggleBtns.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(toggleBtns[0]);
    const hideBtns = screen.getAllByRole("button", {
      name: /Şifreyi gizle/i,
    });
    expect(hideBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("shows password strength bar when new password is typed", async () => {
    render(<ProfilePage />);
    // Three password inputs share the same placeholder; pick the new-password one by id.
    const newPwInput = screen
      .getAllByPlaceholderText("••••••••")
      .find(
        (el) => (el as HTMLInputElement).id === "new_password",
      ) as HTMLElement;
    fireEvent.change(newPwInput, { target: { value: "Test1234" } });
    await waitFor(() => {
      expect(screen.getByText(/Şifre gücü:/)).toBeInTheDocument();
    });
  });

  it("shows son_giris_ip when user has it", () => {
    render(<ProfilePage />);
    expect(screen.getByText("192.168.1.1")).toBeInTheDocument();
  });
});
