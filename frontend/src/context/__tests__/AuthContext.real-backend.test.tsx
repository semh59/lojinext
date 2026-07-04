/**
 * 0-mock epiği: AuthContext.test.tsx'in mock'lu senaryolarına ek olarak,
 * gerçek backend'e karşı çalışan bir sürüm. Gerçek bir login round-trip
 * (POST /auth/token), gerçek /auth/me çekme ve gerçek logout (POST
 * /auth/logout) test edilir.
 *
 * authApi.login ve axiosInstance (getMe/logout) VITE_API_URL'i "/api/v1"
 * dahil beklediği için (relative path'ler prefix İÇERMİYOR — bkz.
 * auth-service.ts: `fetch(\`${API_BASE}/auth/token\`)`), burada
 * REAL_BACKEND_ORIGIN değil REAL_BACKEND_URL (origin + /api/v1) kullanılıyor.
 * Bu, orval-üretimi client'ların kullandığı diğer dosyalardan (REAL_BACKEND_ORIGIN)
 * FARKLI bir base-URL konvansiyonu.
 *
 * Orijinal mock'lu dosya (AuthContext.test.tsx) korunuyor: generic-message-
 * on-401 güvenlik davranışı, farklı rol/permission şekilleri (wildcard,
 * normalize, alan eşleme) gibi hassas hata-enjeksiyonu senaryoları gerçek
 * backend'e karşı pratik olarak tetiklenemez/kontrol edilemez (tek bir
 * gerçek super_admin kullanıcısı var, farklı rollerle kullanıcı oluşturmak
 * bu testin kapsamını aşar).
 */
import { describe, it, expect, vi, beforeAll } from "vitest";
import {
  REAL_BACKEND_URL,
  isRealBackendReachable,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("AuthContext (real backend)", () => {
  let render: typeof import("../../test/test-utils").render;
  let screen: typeof import("../../test/test-utils").screen;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let AuthProvider: typeof import("../AuthContext").AuthProvider;
  let useAuth: typeof import("../AuthContext").useAuth;

  const ADMIN_USER = process.env.REAL_BACKEND_ADMIN_USER || "admin";
  const ADMIN_PASSWORD =
    process.env.REAL_BACKEND_ADMIN_PASSWORD || "faz2_test_admin_pw";

  function TestComponent() {
    const auth = useAuth();
    // "yes"/"no" rather than "authenticated"/"not-authenticated" — jest-dom's
    // toHaveTextContent does a SUBSTRING match, and "not-authenticated"
    // contains "authenticated" as a substring, which trivially (and
    // incorrectly) satisfies a toHaveTextContent("authenticated") assertion
    // even while still logged out. Discovered while wiring this file up
    // against the real backend — a bug in the test, not in AuthContext.
    return (
      <div>
        <div data-testid="is-authenticated">
          {auth.isAuthenticated ? "yes" : "no"}
        </div>
        <div data-testid="user-role">{auth.user?.role || "no-role"}</div>
        <div data-testid="is-loading">
          {auth.isLoading ? "loading" : "loaded"}
        </div>
        <button
          onClick={() => auth.login(ADMIN_USER, ADMIN_PASSWORD)}
          data-testid="login-btn"
        >
          Login
        </button>
        <button onClick={() => auth.logout()} data-testid="logout-btn">
          Logout
        </button>
      </div>
    );
  }

  beforeAll(() => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_URL);
  });

  it("logs in against the real backend and exposes the super_admin role", async () => {
    sessionStorage.removeItem("access_token");
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ AuthProvider, useAuth } = await import("../AuthContext"));

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(
      () => {
        expect(screen.getByTestId("is-loading")).toHaveTextContent("loaded");
      },
      { timeout: 10000 },
    );
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("no");

    screen.getByTestId("login-btn").click();

    await waitFor(
      () => {
        expect(screen.getByTestId("is-authenticated")).toHaveTextContent("yes");
      },
      { timeout: 10000 },
    );
    expect(screen.getByTestId("user-role")).toHaveTextContent("super_admin");
    expect(sessionStorage.getItem("access_token")).toBeTruthy();
  }, 15000);

  it("restores session from a real stored token via /auth/me", async () => {
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ AuthProvider, useAuth } = await import("../AuthContext"));

    // Real login round-trip via fetch to get a fresh valid token, then
    // simulate the "already logged in on reload" scenario.
    const params = new URLSearchParams();
    params.set("username", ADMIN_USER);
    params.set("password", ADMIN_PASSWORD);
    const resp = await fetch(`${REAL_BACKEND_URL}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params,
    });
    const { access_token: token } = await resp.json();
    sessionStorage.setItem("access_token", token);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(
      () => {
        expect(screen.getByTestId("is-authenticated")).toHaveTextContent("yes");
      },
      { timeout: 10000 },
    );
    expect(screen.getByTestId("user-role")).toHaveTextContent("super_admin");
  }, 15000);

  it("logs out and clears the real access token, with a real /auth/logout call", async () => {
    ({ render, screen, waitFor } = await import("../../test/test-utils"));
    ({ AuthProvider, useAuth } = await import("../AuthContext"));

    const params = new URLSearchParams();
    params.set("username", ADMIN_USER);
    params.set("password", ADMIN_PASSWORD);
    const resp = await fetch(`${REAL_BACKEND_URL}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: params,
    });
    const { access_token: token } = await resp.json();
    sessionStorage.setItem("access_token", token);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>,
    );

    await waitFor(
      () => {
        expect(screen.getByTestId("is-authenticated")).toHaveTextContent("yes");
      },
      { timeout: 10000 },
    );

    screen.getByTestId("logout-btn").click();

    await waitFor(
      () => {
        expect(screen.getByTestId("is-authenticated")).toHaveTextContent("no");
      },
      { timeout: 10000 },
    );
    expect(sessionStorage.getItem("access_token")).toBeNull();
  }, 15000);
});
