import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { fireEvent, render, screen, waitFor } from "../../test/test-utils";
import LoginPage from "../LoginPage";

// AuthContext mock — login, logout ve isAuthenticated kontrolü
const mockLogin = vi.fn();
vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({
    login: mockLogin,
    isAuthenticated: false,
    isLoading: false,
    user: null,
    logout: vi.fn(),
    error: null,
    hasPermission: () => false,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

// Stable component references — if the Proxy returns a new function each render,
// React treats it as a different component type and unmounts/remounts, breaking
// DOM node references held in tests.
const _motionCache: Record<string, React.FC<any>> = {};
vi.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get: (_t, key: string) => {
        if (!_motionCache[key]) {
          _motionCache[key] = ({
            children,
            initial,
            animate,
            exit,
            transition,
            whileHover,
            whileTap,
            layout,
            ...props
          }: any) => {
            const Tag = key as keyof JSX.IntrinsicElements;
            return <Tag {...props}>{children}</Tag>;
          };
        }
        return _motionCache[key];
      },
    },
  ),
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

vi.mock("../../components/common/LojiNextLogo", () => ({
  LojiNextLogo: () => <div data-testid="logo">LojiNext</div>,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    mockLogin.mockReset();
  });

  it("username ve şifre alanı render edilir", () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText(/e-posta/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("••••••••")).toBeInTheDocument();
  });

  it("boş form submit edilince validasyon hatası gösterilir", async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /sisteme giriş/i }));
    await waitFor(() => {
      expect(screen.getByText(/kullanıcı adı/i)).toBeInTheDocument();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("başarılı girişte login() çağrılır", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    render(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText(/e-posta/i), {
      target: { value: "admin@lojinext.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), {
      target: { value: "Parola123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sisteme giriş/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith(
        "admin@lojinext.com",
        "Parola123!",
      );
    });
  });

  it("hatalı girişte hata mesajı gösterilir", async () => {
    mockLogin.mockRejectedValueOnce(
      new Error("Kullanıcı adı veya şifre hatalı."),
    );
    render(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText(/e-posta/i), {
      target: { value: "yanlis@lojinext.com" },
    });
    fireEvent.change(screen.getByPlaceholderText("••••••••"), {
      target: { value: "yanlis" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sisteme giriş/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/kullanıcı adı veya şifre hatalı/i),
      ).toBeInTheDocument();
    });
  });

  it("şifre görünürlük toggle'ı çalışır", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    const passwordInput = screen.getByPlaceholderText("••••••••");
    expect(passwordInput).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: /şifreyi göster/i }));
    expect(passwordInput).toHaveAttribute("type", "text");

    await user.click(screen.getByRole("button", { name: /şifreyi gizle/i }));
    expect(passwordInput).toHaveAttribute("type", "password");
  });
});
