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
 *
 * KÖK NEDEN (2026-07-05 teşhis): "admin" kullanıcı adı backend'in
 * SUPER_ADMIN_USERNAME (default "admin") ile eşleşiyor — `POST /auth/token`
 * bu durumda genel 5 req/s bucket'ına EK olarak çok daha sıkı, IP-scoped
 * bir bucket'tan da geçiyor: `super_admin_login:{ip}`, 3 deneme / 300 sn
 * (app/api/v1/endpoints/auth.py, brute-force koruması — kasıtlı güvenlik
 * davranışı, bug değil). Bu dosyanın ESKİ hali 3 test içinde 3 AYRI gerçek
 * `fetch(/auth/token)` çağrısı yapıyordu; aynı 5 dakikalık pencerede aynı
 * IP'den çalışan başka bir real-backend test dosyası (ör. ProfilePage,
 * KullanicilarPage — ikisi de `loginAsAdmin()` üzerinden aynı bucket'ı
 * paylaşıyor) veya art arda koşumlar bucket'ı tüketiyor: token isteği
 * sessizce 429 ile reddediliyor, `authApi.login`/raw fetch bunu generic
 * "Login failed" Error'a çeviriyor, ve "is-authenticated" hep "no" kalıyor.
 * Kanıt: `curl` ile aynı endpoint'e ardışık istek → dördüncüsü
 * `{"error":{"code":"HTTP_429",...}}` döndü.
 * Fix (test-tarafı): sadece "renders...login UI flow" senaryosu (test 1,
 * `auth.login()` üzerinden GERÇEK login akışını test ediyor) taze bir
 * `POST /auth/token` tüketir; session-restore ve logout senaryoları (test
 * 2 ve 3) artık `real-backend.ts`'teki disk-cache'li `loginAsAdmin()`'i
 * kullanıyor — bu ikisi zaten "var olan bir token ile ne olur" davranışını
 * test ediyor, login endpoint'ini yeniden tüketmelerine gerek yok. Bu,
 * projede zaten kurulu olan bucket-tasarrufu deseniyle (real-backend.ts
 * TOKEN_CACHE_FILE) tutarlı. Prod kodda değişiklik YOK.
 */
import { describe, it, expect, vi, beforeAll } from "vitest";
import {
  REAL_BACKEND_URL,
  isRealBackendReachable,
  loginAsAdmin,
  loginFreshUncached,
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
          onClick={() => {
            // Mirrors the real LoginPage's onSubmit (try/catch around
            // `login()`, see src/pages/LoginPage.tsx) — without this, a
            // rejected login (e.g. transient 429 from the strict
            // super-admin rate limiter) surfaces as an "Unhandled
            // Rejection" that crashes the whole vitest run instead of
            // failing just this one test's assertions.
            auth.login(ADMIN_USER, ADMIN_PASSWORD).catch(() => {});
          }}
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

    // Reuse a cached real token (see file-header root-cause note) rather
    // than hitting the strict super-admin login bucket again — this test
    // exercises "already logged in on reload" (/auth/me restore), not the
    // login endpoint itself.
    const token = await loginAsAdmin();
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

    // Deliberately NOT loginAsAdmin() here: /auth/logout blacklists the
    // token server-side (see app/api/v1/endpoints/auth.py). loginAsAdmin()
    // returns a token from a disk cache SHARED with every other
    // real-backend test file in this slice — blacklisting a shared token
    // mid-run breaks whichever sibling file is concurrently relying on it
    // (observed empirically: this test 401-ing another file's requests
    // when all 4 files in this slice ran together). A dedicated,
    // never-cached token avoids that entirely.
    const token = await loginFreshUncached();
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
