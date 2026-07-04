/**
 * 0-mock epiği: usePageViewTracking.test.tsx'in mock'lu senaryosuna ek
 * olarak, gerçek backend'e karşı çalışan bir sürüm. `recordPageView`
 * mock'lanmıyor — gerçek POST /analytics/page-view çağrısı yapılır (hook
 * fire-and-forget olduğu için başarı/başarısızlık UI'a yansımaz). Gerçekten
 * kaydedildiğini GET /admin/analytics/page-views ile benzersiz bir route
 * adı arayarak doğruluyoruz.
 *
 * Orijinal mock'lu dosya (usePageViewTracking.test.tsx) korunuyor: basit,
 * mock-çağrı-argümanı doğrulaması hâlâ hızlı ve faydalı.
 */
import { describe, expect, it, vi, beforeAll, afterAll } from "vitest";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import {
  isRealBackendReachable,
  loginAsAdmin,
  REAL_BACKEND_ORIGIN,
} from "../../test/real-backend";

const backendUp = await isRealBackendReachable();

describe.skipIf(!backendUp)("usePageViewTracking (real backend)", () => {
  let renderHook: typeof import("@testing-library/react").renderHook;
  let waitFor: typeof import("../../test/test-utils").waitFor;
  let usePageViewTracking: typeof import("../usePageViewTracking").usePageViewTracking;
  let authToken: string;

  beforeAll(async () => {
    vi.stubEnv("VITE_API_URL", REAL_BACKEND_ORIGIN);
    authToken = await loginAsAdmin();
    sessionStorage.setItem("access_token", authToken);
    ({ renderHook } = await import("@testing-library/react"));
    ({ waitFor } = await import("../../test/test-utils"));
    ({ usePageViewTracking } = await import("../usePageViewTracking"));
  }, 20000);

  afterAll(() => {
    vi.unstubAllEnvs();
  });

  it("records a real page-view that shows up in the backend's own analytics", async () => {
    sessionStorage.setItem("access_token", authToken);
    const route = `/real-backend-test-${Date.now()}`;

    renderHook(() => usePageViewTracking(), {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <MemoryRouter
          initialEntries={[route]}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          {children}
        </MemoryRouter>
      ),
    });

    await waitFor(
      async () => {
        const resp = await fetch(
          `${REAL_BACKEND_ORIGIN}/api/v1/admin/analytics/page-views?days=1`,
          { headers: { Authorization: `Bearer ${authToken}` } },
        );
        const data = await resp.json();
        const allRoutes = [...data.top_routes, ...data.bottom_routes];
        expect(allRoutes.some((r: any) => r.route === route)).toBe(true);
      },
      { timeout: 10000 },
    );
  }, 15000);
});
