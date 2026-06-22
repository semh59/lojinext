import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "../../test/test-utils";
import { AuthProvider, useAuth } from "../AuthContext";

vi.mock("../../services/api/auth-service");

import { authApi, tokenStorage } from "../../services/api/auth-service";

function TestComponent() {
  const auth = useAuth();
  return (
    <div>
      <div data-testid="is-authenticated">
        {auth.isAuthenticated ? "authenticated" : "not-authenticated"}
      </div>
      <div data-testid="user-name">{auth.user?.full_name || "no-user"}</div>
      <div data-testid="user-role">{auth.user?.role || "no-role"}</div>
      <div data-testid="is-loading">
        {auth.isLoading ? "loading" : "loaded"}
      </div>
      <button
        onClick={() => auth.login("user@test.com", "password")}
        data-testid="login-btn"
      >
        Login
      </button>
      <button onClick={() => auth.logout()} data-testid="logout-btn">
        Logout
      </button>
      <div data-testid="has-perm">
        {auth.hasPermission("sefer:read") ? "yes" : "no"}
      </div>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (tokenStorage.get as any).mockReturnValue(null);
    (authApi.getMe as any).mockResolvedValue({
      id: 1,
      email: "user@test.com",
      ad_soyad: "Test User",
      rol: { ad: "user" },
      aktif: true,
    });
    (authApi.login as any).mockResolvedValue({
      access_token: "token123",
    });
    (authApi.logout as any).mockResolvedValue({});
  });

  it("initializes as unauthenticated", async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-loading")).toHaveTextContent("loaded");
    });

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent(
      "not-authenticated",
    );
  });

  it("restores session from stored token", async () => {
    (tokenStorage.get as any).mockReturnValue("stored");

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-authenticated")).toHaveTextContent(
        "authenticated",
      );
    });

    expect(authApi.getMe).toHaveBeenCalled();
  });

  it("logs in user successfully", async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-loading")).toHaveTextContent("loaded");
    });

    screen.getByTestId("login-btn").click();

    await waitFor(() => {
      expect(screen.getByTestId("is-authenticated")).toHaveTextContent(
        "authenticated",
      );
    });

    expect(authApi.login).toHaveBeenCalledWith("user@test.com", "password");
    expect(tokenStorage.set).toHaveBeenCalledWith("token123");
  });

  it("logs out user", async () => {
    (tokenStorage.get as any).mockReturnValue("token");

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-authenticated")).toHaveTextContent(
        "authenticated",
      );
    });

    screen.getByTestId("logout-btn").click();

    await waitFor(() => {
      expect(tokenStorage.remove).toHaveBeenCalled();
    });
  });

  it("grants sefer:read for user role", async () => {
    (tokenStorage.get as any).mockReturnValue("token");

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("has-perm")).toHaveTextContent("yes");
    });
  });

  it("denies permissions for unauthenticated user", async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-loading")).toHaveTextContent("loaded");
    });

    expect(screen.getByTestId("has-perm")).toHaveTextContent("no");
  });

  it("grants all permissions for admin", async () => {
    (tokenStorage.get as any).mockReturnValue("token");
    (authApi.getMe as any).mockResolvedValue({
      id: 2,
      email: "admin@test.com",
      rol: { ad: "admin" },
      aktif: true,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("has-perm")).toHaveTextContent("yes");
    });

    expect(screen.getByTestId("user-role")).toHaveTextContent("admin");
  });

  it("grants all permissions for wildcard (*) role", async () => {
    // rol_yetkiler={"*":true} → backend require_yetki "*"i kabul eder; frontend de
    // her spesifik yetkiyi vermeli (aksi halde wildcard rolü kilitlenir).
    (tokenStorage.get as any).mockReturnValue("token");
    (authApi.getMe as any).mockResolvedValue({
      id: 3,
      email: "super@test.com",
      rol: { ad: "super_rol", yetkiler: { "*": true } },
      aktif: true,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("has-perm")).toHaveTextContent("yes");
    });
  });

  it("normalizes role names", async () => {
    (tokenStorage.get as any).mockReturnValue("token");
    (authApi.getMe as any).mockResolvedValue({
      id: 3,
      email: "test@test.com",
      rol: { ad: "SuperAdmin" },
      aktif: true,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("user-role")).toHaveTextContent("super_admin");
    });
  });

  it("maps user data from backend fields", async () => {
    (tokenStorage.get as any).mockReturnValue("token");
    (authApi.getMe as any).mockResolvedValue({
      id: 4,
      kullanici_adi: "test@example.com",
      ad_soyad: "John Doe",
      rol: { ad: "user" },
      aktif: true,
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("user-name")).toHaveTextContent("John Doe");
    });
  });
});
