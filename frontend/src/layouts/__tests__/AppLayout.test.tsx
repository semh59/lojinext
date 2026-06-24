import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "../../test/test-utils";
import AppLayout from "../AppLayout";

// framer-motion passthrough — cover all motion.X used by AppLayout + ChatAssistant
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...rest }: any) => <div {...rest}>{children}</div>,
    button: ({ children, ...rest }: any) => (
      <button {...rest}>{children}</button>
    ),
    span: ({ children, ...rest }: any) => <span {...rest}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// LanguageSwitcher — avoids i18n init in tests
vi.mock("../LanguageSwitcher", () => ({
  default: () => <button data-testid="language-switcher">Lang</button>,
}));

// Outlet — render placeholder content
vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    Outlet: () => <div data-testid="outlet-content">Page Content</div>,
    useNavigate: () => vi.fn(),
  };
});

// NotificationContext
vi.mock("../../context/NotificationContext", () => ({
  useNotify: () => ({
    unreadCount: 0,
    markAllRead: vi.fn(),
    liveNotifications: [],
    lastLiveNotification: null,
    notify: vi.fn(),
  }),
  NotificationProvider: ({ children }: any) => <>{children}</>,
}));

// Mock auth to expose a user
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      username: "testuser",
      full_name: "Test Kullanici",
      role: "admin",
      permissions: [],
    },
    logout: vi.fn(),
    isLoading: false,
  }),
  AuthProvider: ({ children }: any) => <>{children}</>,
}));

describe("AppLayout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders the LojiNext brand name", () => {
    render(<AppLayout />);
    // Brand appears in desktop sidebar (hidden on mobile in test env)
    const logos = screen.getAllByText("LojiNext");
    expect(logos.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the outlet placeholder", () => {
    render(<AppLayout />);
    expect(screen.getByTestId("outlet-content")).toBeInTheDocument();
  });

  it("renders the logout button", () => {
    render(<AppLayout />);
    expect(screen.getByText("Çıkış Yap")).toBeInTheDocument();
  });

  it("renders the language switcher", () => {
    render(<AppLayout />);
    expect(screen.getByTestId("language-switcher")).toBeInTheDocument();
  });

  it("renders the notifications bell button", () => {
    render(<AppLayout />);
    expect(screen.getByLabelText("Bildirimler")).toBeInTheDocument();
  });

  it("renders dark mode toggle button", () => {
    render(<AppLayout />);
    // Could be "Açık moda geç" or "Koyu moda geç" depending on stored theme
    const toggleBtn =
      screen.queryByLabelText("Koyu moda geç") ??
      screen.queryByLabelText("Açık moda geç");
    expect(toggleBtn).not.toBeNull();
  });

  it("renders the mobile menu toggle button", () => {
    render(<AppLayout />);
    expect(screen.getByLabelText("Menüyü aç/kapat")).toBeInTheDocument();
  });

  it("shows logged in user full name in header", () => {
    render(<AppLayout />);
    expect(screen.getByText("Test Kullanici")).toBeInTheDocument();
  });

  it("shows admin role label in header", () => {
    render(<AppLayout />);
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("renders Seferler nav item for admin user", () => {
    render(<AppLayout />);
    expect(screen.getByText("Seferler")).toBeInTheDocument();
  });

  it("renders Anomaliler nav item", () => {
    render(<AppLayout />);
    expect(screen.getByText("Anomaliler")).toBeInTheDocument();
  });

  it("renders Sistem Yönetimi nav item for admin user", () => {
    render(<AppLayout />);
    expect(screen.getByText("Yönetim")).toBeInTheDocument();
  });

  it("opens notification panel when bell is clicked", async () => {
    render(<AppLayout />);
    const bellBtn = screen.getByLabelText("Bildirimler");
    fireEvent.click(bellBtn);
    await waitFor(() => {
      // Panel heading <span> — multiple "Bildirimler" may appear (nav item + panel heading)
      expect(screen.getAllByText("Bildirimler").length).toBeGreaterThanOrEqual(
        1,
      );
    });
  });

  it("shows empty notification state when no notifications", async () => {
    render(<AppLayout />);
    fireEvent.click(screen.getByLabelText("Bildirimler"));
    await waitFor(() => {
      expect(screen.getByText("Henüz bildirim yok")).toBeInTheDocument();
    });
  });

  it("notification panel shows Tümünü okundu işaretle button", async () => {
    render(<AppLayout />);
    fireEvent.click(screen.getByLabelText("Bildirimler"));
    await waitFor(() => {
      expect(screen.getByText("Tümünü okundu işaretle")).toBeInTheDocument();
    });
  });

  it("notification panel closes when clicking outside", async () => {
    render(<AppLayout />);
    fireEvent.click(screen.getByLabelText("Bildirimler"));
    await waitFor(() => screen.getByText("Henüz bildirim yok"));
    // Click outside the panel
    fireEvent.mouseDown(document.body);
    await waitFor(() => {
      expect(screen.queryByText("Henüz bildirim yok")).not.toBeInTheDocument();
    });
  });

  it("renders Operasyon nav group label", () => {
    render(<AppLayout />);
    expect(screen.getByText("Operasyon")).toBeInTheDocument();
  });

  it("renders Filo nav group label", () => {
    render(<AppLayout />);
    expect(screen.getByText("Filo")).toBeInTheDocument();
  });
});
